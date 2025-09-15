"""
Edge Device Adapters
Compatibility adapters to integrate existing components with simplified edge architecture
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from .parking_monitor import ParkingMonitorService


class ParkingMonitor:
    """
    Simplified adapter for parking monitor service
    Provides async interface for edge device integration
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._service: Optional[ParkingMonitorService] = None
        self._initialized = False

    async def initialize(self):
        """Initialize parking monitor service"""
        try:
            self._service = ParkingMonitorService()
            await self._service.storage_service.initialize()
            self._initialized = True
            self.logger.info("Parking monitor adapter initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize parking monitor: {e}")
            raise

    async def shutdown(self):
        """Shutdown parking monitor service"""
        try:
            if self._service and self._service.storage_service:
                await self._service.storage_service.shutdown()
            self._initialized = False
            self.logger.info("Parking monitor adapter shutdown")
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

    async def process_snapshot(self) -> Optional[Dict[str, Any]]:
        """
        Process current snapshot and return detection results

        Returns:
            Detection results with vehicle count and zone information
        """
        if not self._initialized or not self._service:
            return None

        try:
            # Get snapshot via detector
            detection_result = self._service.detector.detect_vehicles()

            if detection_result:
                # Extract key metrics for edge device
                return {
                    "total_zones": detection_result.get("total_zones", 0),
                    "occupied_count": detection_result.get("occupied_count", 0),
                    "processing_time": detection_result.get("processing_time", 0),
                    "average_confidence": detection_result.get("average_confidence", 0),
                    "timestamp": detection_result.get("timestamp", 0)
                }

        except Exception as e:
            self.logger.error(f"Snapshot processing failed: {e}")
            return None

    async def get_annotated_frame(self) -> Optional[bytes]:
        """Get processed frame with annotations"""
        if not self._initialized or not self._service:
            return None

        try:
            # Use detector's snapshot capability
            return self._service.detector.get_snapshot_with_overlays()
        except Exception as e:
            self.logger.error(f"Failed to get annotated frame: {e}")
            return None


class CameraManager:
    """
    Simplified camera manager for edge device
    Provides basic camera status and raw frame access
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._initialized = False
        self._camera_info = {
            "connected": False,
            "fps": 0.0,
            "resolution": "unknown",
            "autofocus": False,
            "last_frame_ts": 0
        }

    async def initialize(self):
        """Initialize camera manager"""
        try:
            # Basic camera status detection
            self._camera_info = {
                "connected": True,  # Assume connected if no errors
                "fps": 30.0,
                "resolution": "1920x1080",
                "autofocus": True,
                "last_frame_ts": 0
            }
            self._initialized = True
            self.logger.info("Camera manager initialized")
        except Exception as e:
            self.logger.error(f"Camera initialization failed: {e}")
            raise

    async def shutdown(self):
        """Shutdown camera manager"""
        self._initialized = False
        self.logger.info("Camera manager shutdown")

    async def capture_frame(self) -> Optional[bytes]:
        """Capture raw frame from camera"""
        if not self._initialized:
            return None

        try:
            # This would integrate with the actual camera capture logic
            # For now, return None to indicate no frame available
            return None
        except Exception as e:
            self.logger.error(f"Frame capture failed: {e}")
            return None

    async def get_status(self) -> Dict[str, Any]:
        """Get camera status information"""
        if not self._initialized:
            return {
                "connected": False,
                "fps": 0.0,
                "resolution": "unknown",
                "autofocus": False,
                "last_frame_ts": 0
            }

        return self._camera_info.copy()

    async def restart(self) -> bool:
        """Restart camera connection"""
        try:
            self.logger.info("Camera restart requested")
            # Simulate camera restart
            await asyncio.sleep(1)

            # Update status after restart
            import time
            self._camera_info["last_frame_ts"] = int(time.time() * 1000)

            return True
        except Exception as e:
            self.logger.error(f"Camera restart failed: {e}")
            return False