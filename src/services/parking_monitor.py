"""
Parking Monitor Service
Core business logic for parking detection orchestration
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any

from ..config import ParkingConfig, ConfigManager
from ..detector import MVPParkingDetector


class ParkingMonitorService:
    """
    Core parking monitor service handling detection orchestration
    
    Responsibilities:
    - Service lifecycle management
    - Detection statistics aggregation
    - Configuration management
    - Logging setup
    """
    
    def __init__(self, config_file: Optional[str] = None):
        """Initialize the parking monitor service"""
        # Load configuration using new clean system
        self.config_manager = ConfigManager(config_file)
        self.config = self.config_manager.config
        
        # Initialize detector with clean configuration
        self.detector = MVPParkingDetector()
        self.running = False
        self.start_time = datetime.now()
        
        # Setup logging from configuration
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(f"Service initialized with {self.config.get_total_zones()} parking zones")
        self.logger.info(f"Snapshot interval: {self.config.processing.snapshot_interval}s")
    
    def _setup_logging(self):
        """Setup logging from configuration"""
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler()]
        )
    
    async def start_detection(self):
        """Start parking detection processing"""
        try:
            self.running = True
            self.logger.info("Starting parking detection service...")
            
            # Start detector snapshot loop in background
            detection_task = asyncio.create_task(self.detector.start_snapshot_loop())
            
            self.logger.info("Parking detection service started successfully")
            
        except Exception as e:
            self.logger.error(f"Service startup failed: {e}")
            self.running = False
            raise
    
    async def stop_detection(self):
        """Stop detection processing"""
        try:
            self.logger.info("Stopping parking detection service...")
            self.running = False
            
            await self.detector.stop()
            
            self.logger.info("Parking detection service stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Service shutdown error: {e}")
            raise
    
    async def get_detection_stats(self) -> Dict[str, Any]:
        """Get current detection statistics with enhanced metadata"""
        stats = await self.detector.get_stats()
        
        # Add configuration-based metadata and timestamps
        enhanced_stats = {
            **stats,
            "last_update_epoch": self.config.last_snapshot_epoch,
            "server_time_epoch": time.time(),
            "snapshot_interval": self.config.processing.snapshot_interval,
            "total_zones": self.config.get_total_zones(),
            "easy_zones_count": self.config.get_easy_zones_count(),
            "hard_zones_count": self.config.get_hard_zones_count(),
            "processing_enabled": self.config.processing.processing_enabled
        }
        
        return enhanced_stats
    
    def get_uptime(self) -> float:
        """Get service uptime in seconds"""
        return (datetime.now() - self.start_time).total_seconds()
    
    def get_snapshot_image(self) -> Optional[bytes]:
        """Get last processed snapshot as JPEG bytes"""
        return self.detector.get_last_snapshot_image()
    
    def get_raw_frame_image(self) -> Optional[bytes]:
        """Get current raw frame (without overlays) as JPEG bytes"""
        return self.detector.get_raw_frame_image()
    
    async def get_zones_data(self) -> list:
        """Get parking zones data with current status"""
        return self.config.get_zones_data()
    
    def get_config_data(self) -> Dict[str, Any]:
        """Get configuration data for API responses"""
        return self.config.to_dict()
    
    def get_status_info(self) -> Dict[str, Any]:
        """Get comprehensive status information"""
        config_data = self.get_config_data()
        current_time = time.time()
        
        # Calculate when next snapshot will happen
        time_since_last = current_time - config_data.get("last_snapshot_epoch", 0)
        next_snapshot_in = max(0, config_data.get("snapshot_interval", 5) - time_since_last)
        
        return {
            "processing_enabled": config_data.get("processing_enabled", True),
            "snapshot_interval": config_data.get("snapshot_interval", 5),
            "last_snapshot_epoch": config_data.get("last_snapshot_epoch", 0),
            "server_time_epoch": current_time,
            "uptime_seconds": self.get_uptime(),
            "next_snapshot_in": round(next_snapshot_in, 1),
            "model_loaded": self.detector.stats.get("model_loaded", False),
            "device": self.detector.device,
            "total_zones": config_data.get("total_zones", self.config.get_total_zones()),
            "service_running": self.running
        }
    
    def get_device_info(self) -> Dict[str, Any]:
        """Get device and camera information"""
        return {
            "is_camera_device": self.detector.is_camera_device,
            "device_initialized": self.detector.camera_initialized,
            "processing_device": self.detector.device,
            "video_source": str(self.config.video.source)
        }
    
    def reload_config(self, config_file: Optional[str] = None):
        """Reload configuration from file"""
        try:
            old_interval = self.config.processing.snapshot_interval
            self.config_manager.load_config(config_file)
            self.config = self.config_manager.config
            
            new_interval = self.config.processing.snapshot_interval
            if old_interval != new_interval:
                self.logger.info(f"Snapshot interval changed: {old_interval}s → {new_interval}s")
            
            self.logger.info("Configuration reloaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to reload configuration: {e}")
            return False