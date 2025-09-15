"""
Detection Queue Manager for Edge Device
Handles detection collection, local storage, and batch upload to central API
"""

import asyncio
import logging
import time
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime

from ..models.edge import Detection, DeploymentConfig, EdgeConfig
from ..storage.edge_storage import EdgeStorage
from .edge_adapters import ParkingMonitor, CameraManager


class DetectionQueue:
    """
    Detection Queue Manager
    - Collects detections every 5 seconds
    - Stores locally with uploaded=false flag
    - Batch uploads every 60 seconds with exponential backoff
    """

    def __init__(self, storage: EdgeStorage, config: EdgeConfig):
        """
        Initialize detection queue

        Args:
            storage: Edge storage instance
            config: Edge device configuration
        """
        self.logger = logging.getLogger(__name__)
        self.storage = storage
        self.config = config

        # Services
        self.parking_monitor: Optional[ParkingMonitor] = None
        self.camera_manager: Optional[CameraManager] = None

        # Task management
        self.collection_task: Optional[asyncio.Task] = None
        self.upload_task: Optional[asyncio.Task] = None
        self._running = False

        # Upload configuration
        self.upload_backoff = 1.0  # Initial backoff in seconds
        self.max_backoff = 300.0   # Maximum 5 minutes
        self.backoff_multiplier = 2.0

        # Current state cache
        self._current_state = {
            "totalSpaces": self.config.device.totalSpaces,
            "occupiedSpaces": 0,
            "last_detection_ts": None
        }

    async def start(self):
        """Start detection collection and upload tasks"""
        try:
            # Initialize parking monitor
            self.parking_monitor = ParkingMonitor()
            await self.parking_monitor.initialize()

            # Initialize camera manager
            self.camera_manager = CameraManager()
            await self.camera_manager.initialize()

            # Start tasks
            self._running = True
            self.collection_task = asyncio.create_task(self._collection_loop())
            self.upload_task = asyncio.create_task(self._upload_loop())

            self.logger.info("Detection queue started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start detection queue: {e}")
            raise

    async def stop(self):
        """Stop all tasks and cleanup"""
        try:
            self._running = False

            # Cancel tasks
            if self.collection_task:
                self.collection_task.cancel()
                try:
                    await self.collection_task
                except asyncio.CancelledError:
                    pass

            if self.upload_task:
                self.upload_task.cancel()
                try:
                    await self.upload_task
                except asyncio.CancelledError:
                    pass

            # Cleanup services
            if self.parking_monitor:
                await self.parking_monitor.shutdown()

            if self.camera_manager:
                await self.camera_manager.shutdown()

            self.logger.info("Detection queue stopped successfully")

        except Exception as e:
            self.logger.error(f"Error stopping detection queue: {e}")

    async def _collection_loop(self):
        """Collection loop - runs every 5 seconds"""
        while self._running:
            try:
                # Perform detection
                detection_result = await self._perform_detection()
                if detection_result:
                    # Create detection record
                    detection = Detection(
                        ts=int(time.time() * 1000),
                        customerId=self.config.deployment.customerId,
                        siteId=self.config.deployment.siteId,
                        zoneId=self.config.deployment.zoneId,
                        cameraId=self.config.deployment.cameraId,
                        totalSpaces=detection_result["total_spaces"],
                        occupiedSpaces=detection_result["occupied_spaces"],
                        uploaded=False
                    )

                    # Store locally
                    success = await self.storage.store_detection(detection)
                    if success:
                        # Update current state
                        self._current_state.update({
                            "totalSpaces": detection_result["total_spaces"],
                            "occupiedSpaces": detection_result["occupied_spaces"],
                            "last_detection_ts": detection.ts
                        })

                        self.logger.debug(f"Detection stored: {detection.occupiedSpaces}/{detection.totalSpaces} spaces")
                    else:
                        self.logger.error("Failed to store detection locally")

                # Wait for next collection (5 seconds)
                await asyncio.sleep(self.config.device.snapshotInterval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in collection loop: {e}")
                await asyncio.sleep(5)  # Error recovery delay

    async def _upload_loop(self):
        """Upload loop - runs every 60 seconds"""
        if not self.config.centralApi or not self.config.centralApi.enabled:
            self.logger.info("Central API upload disabled")
            return

        while self._running:
            try:
                # Get unuploaded detections
                detections = await self.storage.get_unuploaded_detections(
                    limit=self.config.centralApi.batchSize
                )

                if detections:
                    success = await self._upload_batch(detections)
                    if success:
                        # Mark as uploaded
                        detection_ids = [d.id for d in detections]
                        await self.storage.mark_as_uploaded(detection_ids)

                        # Reset backoff on success
                        self.upload_backoff = 1.0

                        self.logger.info(f"Uploaded {len(detections)} detections successfully")
                    else:
                        # Increase backoff on failure
                        self._increase_backoff()
                        self.logger.warning(f"Upload failed, backing off for {self.upload_backoff} seconds")

                # Wait for next upload attempt
                await asyncio.sleep(self.config.centralApi.submissionInterval + self.upload_backoff)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in upload loop: {e}")
                self._increase_backoff()
                await asyncio.sleep(self.upload_backoff)

    async def _perform_detection(self) -> Optional[Dict[str, Any]]:
        """Perform vehicle detection on current frame"""
        try:
            if not self.parking_monitor:
                return None

            # Get detection results
            results = await self.parking_monitor.process_snapshot()
            if not results:
                return None

            return {
                "total_spaces": results.get("total_zones", self.config.device.totalSpaces),
                "occupied_spaces": results.get("occupied_count", 0),
                "processing_time": results.get("processing_time", 0),
                "confidence": results.get("average_confidence", 0)
            }

        except Exception as e:
            self.logger.error(f"Detection failed: {e}")
            return None

    async def _upload_batch(self, detections: List[Detection]) -> bool:
        """
        Upload batch of detections to central API

        Args:
            detections: List of detections to upload

        Returns:
            Success status
        """
        try:
            if not self.config.centralApi:
                return False

            # Prepare batch data
            batch_data = []
            for detection in detections:
                data = detection.model_dump()
                # Remove local fields
                data.pop("uploaded", None)
                batch_data.append(data)

            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "x-customer-id": self.config.deployment.customerId,
                "x-api-key": self.config.centralApi.apiKey,
                "x-secret-key": self.config.centralApi.secretKey
            }

            # Upload to central API
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.config.centralApi.endpoint}/detections",
                    json=batch_data,
                    headers=headers
                )

                response.raise_for_status()

                self.logger.debug(f"Upload response: {response.status_code}")
                return True

        except httpx.HTTPError as e:
            self.logger.error(f"HTTP error during upload: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Upload error: {e}")
            return False

    def _increase_backoff(self):
        """Increase backoff delay with exponential backoff"""
        self.upload_backoff = min(self.upload_backoff * self.backoff_multiplier, self.max_backoff)

    async def get_current_state(self) -> Dict[str, Any]:
        """Get current parking detection state"""
        return self._current_state.copy()

    async def get_processed_snapshot(self) -> Optional[bytes]:
        """Get processed frame with detection overlays"""
        try:
            if not self.parking_monitor:
                return None

            return await self.parking_monitor.get_annotated_frame()

        except Exception as e:
            self.logger.error(f"Failed to get processed snapshot: {e}")
            return None

    async def get_raw_frame(self) -> Optional[bytes]:
        """Get raw camera frame"""
        try:
            if not self.camera_manager:
                return None

            return await self.camera_manager.capture_frame()

        except Exception as e:
            self.logger.error(f"Failed to get raw frame: {e}")
            return None

    async def get_camera_status(self) -> Dict[str, Any]:
        """Get camera status information"""
        try:
            if not self.camera_manager:
                return {
                    "connected": False,
                    "fps": 0.0,
                    "resolution": "unknown",
                    "autofocus": False,
                    "last_frame_ts": 0
                }

            return await self.camera_manager.get_status()

        except Exception as e:
            self.logger.error(f"Failed to get camera status: {e}")
            return {"connected": False, "fps": 0.0, "resolution": "unknown", "autofocus": False}

    async def restart_camera(self, reason: str = "Manual restart") -> bool:
        """Restart camera connection"""
        try:
            if not self.camera_manager:
                return False

            self.logger.info(f"Restarting camera: {reason}")
            return await self.camera_manager.restart()

        except Exception as e:
            self.logger.error(f"Camera restart failed: {e}")
            return False

    async def restart_with_new_config(self, deployment_config: DeploymentConfig):
        """Restart detection queue with new deployment configuration"""
        try:
            # Update configuration
            self.config.deployment = deployment_config

            # Update current state with new identifiers
            self._current_state["deployment_updated"] = int(time.time() * 1000)

            self.logger.info("Detection queue restarted with new configuration")

        except Exception as e:
            self.logger.error(f"Failed to restart with new config: {e}")
            raise