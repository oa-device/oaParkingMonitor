"""
AWS Upload Service for Batch Detection Upload
Professional edge device service for efficient cloud synchronization
"""

import asyncio
import logging
import os
import time
from typing import Optional, List, Dict, Any

import httpx

from ..storage.edge_storage import EdgeStorage
from ..models.edge import Detection, CentralApiConfig


class AwsUploadService:
    """
    AWS batch upload service for parking detections

    Features:
    - 1-minute batch uploads (configurable interval)
    - Exponential backoff retry logic
    - Authentication header management
    - Upload success/failure tracking
    - Resilient to network failures
    """

    def __init__(self, edge_storage: EdgeStorage, config: Optional[CentralApiConfig] = None):
        """
        Initialize AWS upload service

        Args:
            edge_storage: Local storage instance for detections
            config: Central API configuration (if None, loads from env)
        """
        self.logger = logging.getLogger(__name__)
        self.edge_storage = edge_storage

        # Load configuration
        if config and config.enabled:
            self.config = config
        else:
            # Load from environment variables
            self.config = self._load_config_from_env()

        # Upload state
        self.running = False
        self.upload_task: Optional[asyncio.Task] = None

        # Statistics
        self.stats = {
            "total_uploads": 0,
            "successful_uploads": 0,
            "failed_uploads": 0,
            "last_upload_time": None,
            "last_successful_upload": None,
            "consecutive_failures": 0,
            "total_detections_uploaded": 0
        }

        # HTTP client
        self.client: Optional[httpx.AsyncClient] = None

        self.logger.info(f"AWS Upload Service initialized - Enabled: {self.config.enabled}")
        if self.config.enabled:
            self.logger.info(f"Upload interval: {self.config.submissionInterval}s, Batch size: {self.config.batchSize}")

    def _load_config_from_env(self) -> CentralApiConfig:
        """Load configuration from environment variables"""
        return CentralApiConfig(
            enabled=os.getenv("CENTRAL_API_ENABLED", "false").lower() == "true",
            endpoint=os.getenv("CENTRAL_API_URL", ""),
            apiKey=os.getenv("API_KEY", ""),
            secretKey=os.getenv("SECRET_KEY", ""),
            batchSize=int(os.getenv("BATCH_SIZE", "100")),
            submissionInterval=int(os.getenv("SUBMISSION_INTERVAL", "60"))
        )

    async def start_upload_loop(self):
        """Start the background upload loop"""
        if not self.config.enabled:
            self.logger.info("AWS upload disabled - skipping upload loop")
            return

        if not self.config.endpoint:
            self.logger.warning("No AWS endpoint configured - upload loop disabled")
            return

        try:
            self.running = True

            # Initialize HTTP client
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),  # 30 second timeout
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "oaParkingMonitor/2.0.0"
                }
            )

            # Start upload loop
            self.upload_task = asyncio.create_task(self._upload_loop())

            self.logger.info("AWS upload loop started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start upload loop: {e}")
            self.running = False
            raise

    async def stop_upload_loop(self):
        """Stop the upload loop and cleanup"""
        try:
            self.logger.info("Stopping AWS upload loop...")
            self.running = False

            # Cancel upload task
            if self.upload_task:
                self.upload_task.cancel()
                try:
                    await self.upload_task
                except asyncio.CancelledError:
                    pass

            # Close HTTP client
            if self.client:
                await self.client.aclose()
                self.client = None

            self.logger.info("AWS upload loop stopped successfully")

        except Exception as e:
            self.logger.error(f"Error stopping upload loop: {e}")

    async def _upload_loop(self):
        """Main upload loop - runs every submission interval"""
        while self.running:
            try:
                # Wait for next upload interval
                await asyncio.sleep(self.config.submissionInterval)

                # Get unuploaded detections
                unuploaded = await self.edge_storage.get_unuploaded_detections(
                    limit=self.config.batchSize
                )

                if not unuploaded:
                    self.logger.debug("No unuploaded detections found")
                    continue

                # Upload batch
                await self._upload_batch(unuploaded)

            except asyncio.CancelledError:
                self.logger.info("Upload loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in upload loop: {e}")
                # Continue running even if individual upload fails
                await asyncio.sleep(5)  # Brief pause before retrying

    async def _upload_batch(self, detections: List[Detection]):
        """
        Upload a batch of detections to AWS

        Args:
            detections: List of detections to upload
        """
        batch_size = len(detections)
        self.logger.info(f"Uploading batch of {batch_size} detections")

        try:
            # Prepare batch payload (matching CTO API format)
            # Exclude 'uploaded' field as it's not part of CTO API schema
            payload = [detection.model_dump(exclude={'uploaded'}) for detection in detections]

            # Upload with retry logic
            customer_id = detections[0].customerId if detections else "019949CE-8A59-7016-8498-7DE5E32D7B9D"
            success = await self._post_to_aws_with_retry(payload, customer_id)

            if success:
                # Mark detections as uploaded
                detection_ids = [d.id for d in detections]
                await self.edge_storage.mark_as_uploaded(detection_ids)

                # Update statistics
                self.stats["successful_uploads"] += 1
                self.stats["consecutive_failures"] = 0
                self.stats["last_successful_upload"] = time.time()
                self.stats["total_detections_uploaded"] += batch_size

                self.logger.info(f"Successfully uploaded batch of {batch_size} detections")

            else:
                # Upload failed
                self.stats["failed_uploads"] += 1
                self.stats["consecutive_failures"] += 1

                self.logger.error(f"Failed to upload batch of {batch_size} detections")

            # Update common statistics
            self.stats["total_uploads"] += 1
            self.stats["last_upload_time"] = time.time()

        except Exception as e:
            self.logger.error(f"Error uploading batch: {e}")
            self.stats["failed_uploads"] += 1
            self.stats["consecutive_failures"] += 1

    async def _post_to_aws_with_retry(self, payload: List[Dict[str, Any]], customer_id: str) -> bool:
        """
        POST to AWS with exponential backoff retry

        Args:
            payload: List of detection objects to send
            customer_id: Customer ID for authentication header

        Returns:
            True if successful, False if all retries failed
        """
        max_retries = 3
        base_delay = 1  # Start with 1 second delay

        for attempt in range(max_retries):
            try:
                # Prepare headers (following CTO API requirements)
                headers = {
                    "x-customer-id": customer_id,
                    "x-api-key": self.config.apiKey,
                    "x-secret-key": self.config.secretKey
                }

                # Make POST request
                response = await self.client.post(
                    f"{self.config.endpoint}/detections",
                    json=payload,
                    headers=headers
                )

                if response.status_code in [200, 201]:
                    self.logger.debug(f"AWS upload successful (HTTP {response.status_code})")
                    return True

                elif response.status_code in [400, 401, 403]:
                    # Client errors - don't retry
                    self.logger.error(f"AWS upload failed with client error {response.status_code}: {response.text}")
                    return False

                else:
                    # Server errors or other issues - retry
                    self.logger.warning(f"AWS upload failed with status {response.status_code} (attempt {attempt + 1}/{max_retries})")

                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # Exponential backoff
                        await asyncio.sleep(delay)
                        continue

                    return False

            except httpx.TimeoutException:
                self.logger.warning(f"AWS upload timeout (attempt {attempt + 1}/{max_retries})")
            except httpx.ConnectError:
                self.logger.warning(f"AWS connection error (attempt {attempt + 1}/{max_retries})")
            except Exception as e:
                self.logger.error(f"Unexpected error during AWS upload (attempt {attempt + 1}/{max_retries}): {e}")

            # Wait before retry (except on last attempt)
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)

        return False

    def get_upload_stats(self) -> Dict[str, Any]:
        """Get upload statistics for monitoring"""
        current_time = time.time()

        # Calculate time since last upload
        time_since_last = None
        if self.stats["last_upload_time"]:
            time_since_last = current_time - self.stats["last_upload_time"]

        # Calculate time since last successful upload
        time_since_success = None
        if self.stats["last_successful_upload"]:
            time_since_success = current_time - self.stats["last_successful_upload"]

        # Calculate success rate
        success_rate = 0.0
        if self.stats["total_uploads"] > 0:
            success_rate = self.stats["successful_uploads"] / self.stats["total_uploads"]

        return {
            **self.stats,
            "enabled": self.config.enabled,
            "endpoint": self.config.endpoint if self.config.enabled else None,
            "submission_interval": self.config.submissionInterval,
            "batch_size": self.config.batchSize,
            "time_since_last_upload": time_since_last,
            "time_since_last_success": time_since_success,
            "success_rate": round(success_rate, 3),
            "is_healthy": self.stats["consecutive_failures"] < 3
        }

    def is_running(self) -> bool:
        """Check if upload service is running"""
        return self.running and (self.upload_task is not None and not self.upload_task.done())