"""
Storage Service
High-level service for data persistence and retrieval
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    init_database,
    get_async_session,
    DataRetentionPolicy,
    AsyncSessionLocal
)
from .repository import DataRepository


class StorageService:
    """
    Service layer for data storage operations
    Integrates with the parking monitor to persist detection data
    """
    
    def __init__(self):
        """Initialize storage service"""
        self.logger = logging.getLogger(__name__)
        self.repository: Optional[DataRepository] = None
        self.session: Optional[AsyncSession] = None
        self.initialized = False
        
        # Background tasks
        self.cleanup_task: Optional[asyncio.Task] = None
        self.metrics_task: Optional[asyncio.Task] = None
        
        # Cache for performance
        self.zone_cache: Dict[int, Any] = {}
        self.last_snapshot_id: Optional[int] = None
    
    async def initialize(self):
        """Initialize database and start background tasks"""
        try:
            # Initialize database schema
            await init_database()
            
            # Create session and repository
            self.session = AsyncSessionLocal()
            self.repository = DataRepository(self.session)
            
            # Start background tasks
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            self.metrics_task = asyncio.create_task(self._metrics_collection_loop())
            
            self.initialized = True
            self.logger.info("Storage service initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize storage service: {e}")
            raise
    
    async def shutdown(self):
        """Cleanup resources and stop background tasks"""
        try:
            # Cancel background tasks
            if self.cleanup_task:
                self.cleanup_task.cancel()
            if self.metrics_task:
                self.metrics_task.cancel()
            
            # Close database session
            if self.session:
                await self.session.close()
            
            self.initialized = False
            self.logger.info("Storage service shut down successfully")
            
        except Exception as e:
            self.logger.error(f"Error during storage service shutdown: {e}")
    
    async def store_detection_result(self, 
                                    detections: List[Dict[str, Any]], 
                                    zones_status: List[Dict[str, Any]],
                                    processing_time: float,
                                    frame_path: Optional[str] = None) -> bool:
        """
        Store detection results in database
        
        Args:
            detections: List of vehicle detections
            zones_status: List of zone occupancy statuses
            processing_time: Time taken to process the snapshot
            frame_path: Optional path to saved frame image
            
        Returns:
            Success status
        """
        if not self.initialized or not self.repository:
            self.logger.warning("Storage service not initialized")
            return False
        
        try:
            # Calculate aggregated metrics
            total_occupied = sum(1 for zone in zones_status if zone["occupied"])
            total_vacant = len(zones_status) - total_occupied
            occupancy_rate = total_occupied / len(zones_status) if zones_status else 0.0
            
            # Calculate average confidence
            confidences = [d["confidence"] for d in detections if "confidence" in d]
            confidence_avg = sum(confidences) / len(confidences) if confidences else 0.0
            
            # Count stable detections
            stable_detections = sum(
                1 for zone in zones_status 
                if zone.get("stable_frames", 0) > 3
            )
            
            # Check if temporal smoothing was applied
            temporal_smoothing = any(
                zone.get("temporal_smoothed", False) 
                for zone in zones_status
            )
            
            # Prepare snapshot data
            snapshot_data = {
                "epoch_time": time.time(),
                "frame_path": frame_path,
                "total_occupied": total_occupied,
                "total_vacant": total_vacant,
                "occupancy_rate": occupancy_rate,
                "processing_time": processing_time,
                "detection_method": "multi_scale",
                "confidence_avg": confidence_avg,
                "stable_detections": stable_detections,
                "temporal_smoothing": temporal_smoothing,
                "detections": detections,
                "zones_status": zones_status
            }
            
            # Save to database
            snapshot = await self.repository.save_detection_snapshot(snapshot_data)
            self.last_snapshot_id = snapshot.id
            
            # Save JSON snapshot for airport demo
            epoch = int(snapshot_data["epoch_time"])
            self._save_json_snapshot(epoch, snapshot_data)
            
            self.logger.debug(f"Stored snapshot {snapshot.id}: {total_occupied}/{len(zones_status)} occupied")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to store detection result: {e}")
            return False
    
    async def get_current_state(self) -> Dict[str, Any]:
        """Get current parking state from database"""
        if not self.repository:
            return {}
        
        try:
            zones = await self.repository.get_all_zones()
            
            return {
                "zones": [
                    {
                        "id": zone.id,
                        "name": zone.name,
                        "occupied": zone.current_occupied,
                        "confidence": zone.current_confidence,
                        "last_change": zone.last_state_change.isoformat() if zone.last_state_change else None
                    }
                    for zone in zones
                ],
                "total_zones": len(zones),
                "occupied_count": sum(1 for z in zones if z.current_occupied),
                "vacant_count": sum(1 for z in zones if not z.current_occupied),
                "last_update": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get current state: {e}")
            return {}
    
    async def get_zone_history(self, 
                              zone_id: int, 
                              hours: int = 24) -> List[Dict[str, Any]]:
        """Get historical data for a specific zone"""
        if not self.repository:
            return []
        
        try:
            history = await self.repository.get_zone_history(zone_id, hours)
            
            return [
                {
                    "timestamp": h.timestamp.isoformat(),
                    "epoch_time": h.epoch_time,
                    "occupied": h.occupied,
                    "confidence": h.confidence,
                    "detection_count": h.detection_count,
                    "stable_frames": h.stable_frames,
                    "temporal_smoothed": h.temporal_smoothed
                }
                for h in history
            ]
            
        except Exception as e:
            self.logger.error(f"Failed to get zone history: {e}")
            return []
    
    async def get_occupancy_analytics(self, hours: int = 24) -> Dict[str, Any]:
        """Get occupancy analytics and trends"""
        if not self.repository:
            return {}
        
        try:
            # Get occupancy trends
            trends = await self.repository.get_occupancy_trends(hours)
            
            # Get zone performance
            zone_performance = await self.repository.get_zone_performance()
            
            # Get system metrics
            metrics = await self.repository.get_system_metrics(hours=1)
            
            # Calculate additional analytics
            if metrics:
                latest_metric = metrics[0]
                system_health = {
                    "fps": latest_metric.fps,
                    "memory_mb": latest_metric.memory_usage_mb,
                    "detection_latency_ms": latest_metric.detection_latency_ms,
                    "model_loaded": latest_metric.model_loaded,
                    "device": latest_metric.device_type
                }
            else:
                system_health = {}
            
            return {
                "trends": trends,
                "zone_performance": zone_performance,
                "system_health": system_health,
                "analysis_period_hours": hours,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get occupancy analytics: {e}")
            return {}
    
    async def export_data(self, 
                         hours: int = 24, 
                         format: str = "json") -> Any:
        """Export historical data"""
        if not self.repository:
            return None
        
        try:
            start_time = datetime.utcnow() - timedelta(hours=hours)
            end_time = datetime.utcnow()
            
            return await self.repository.export_data(start_time, end_time, format)
            
        except Exception as e:
            self.logger.error(f"Failed to export data: {e}")
            return None
    
    async def save_system_metrics(self, metrics: Dict[str, Any]):
        """Save system performance metrics"""
        if not self.repository:
            return
        
        try:
            await self.repository.save_system_metrics(metrics)
            
        except Exception as e:
            self.logger.error(f"Failed to save system metrics: {e}")
    
    # ============= Background Tasks =============
    
    async def _cleanup_loop(self):
        """Background task for data cleanup - Database + Snapshot files"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                # Clean database records
                if self.session:
                    await DataRetentionPolicy.cleanup_old_data(self.session)
                    self.logger.info("Completed database retention cleanup")
                
                # Clean snapshot files (30-day retention for airport demo)
                from ..utils.paths import get_data_paths
                data_paths = get_data_paths()
                deleted_count = data_paths.cleanup_old_snapshots(days_to_keep=30)
                
                if deleted_count > 0:
                    self.logger.info(f"Cleaned up {deleted_count} old snapshot files")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Cleanup task error: {e}")
    
    async def _metrics_collection_loop(self):
        """Background task for collecting system metrics"""
        while True:
            try:
                await asyncio.sleep(60)  # Collect every minute
                
                # Collect system metrics
                import psutil
                
                metrics = {
                    "memory_usage_mb": psutil.virtual_memory().used / (1024 * 1024),
                    "cpu_usage_percent": psutil.cpu_percent(interval=1),
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Store metrics (will be enhanced with actual detection metrics)
                await self.save_system_metrics(metrics)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Metrics collection error: {e}")
    
    # ============= Cache Management =============
    
    def update_zone_cache(self, zone_id: int, data: Dict[str, Any]):
        """Update zone cache for performance"""
        self.zone_cache[zone_id] = {
            **data,
            "cached_at": time.time()
        }
    
    def get_zone_from_cache(self, zone_id: int) -> Optional[Dict[str, Any]]:
        """Get zone data from cache if fresh"""
        if zone_id in self.zone_cache:
            cached = self.zone_cache[zone_id]
            # Cache valid for 5 seconds
            if time.time() - cached["cached_at"] < 5:
                return cached
        return None
    
    def clear_cache(self):
        """Clear all cached data"""
        self.zone_cache.clear()
        self.last_snapshot_id = None
    
    def _save_json_snapshot(self, epoch: int, snapshot_data: Dict[str, Any]) -> bool:
        """
        Save snapshot data as JSON file for airport demo.
        
        Args:
            epoch: Epoch timestamp for filename
            snapshot_data: Complete snapshot data to save
            
        Returns:
            True if successful
        """
        try:
            # Import at method level to avoid circular imports
            from ..utils.paths import save_snapshot_json
            
            # Create a clean snapshot for JSON export
            json_snapshot = {
                "epoch": epoch,
                "timestamp": snapshot_data.get("epoch_time"),
                "occupancy": {
                    "total_occupied": snapshot_data.get("total_occupied", 0),
                    "total_vacant": snapshot_data.get("total_vacant", 0),
                    "occupancy_rate": snapshot_data.get("occupancy_rate", 0.0),
                    "total_zones": len(snapshot_data.get("zones_status", []))
                },
                "processing": {
                    "processing_time": snapshot_data.get("processing_time", 0.0),
                    "detection_method": snapshot_data.get("detection_method", "multi_scale"),
                    "confidence_avg": snapshot_data.get("confidence_avg", 0.0),
                    "stable_detections": snapshot_data.get("stable_detections", 0),
                    "temporal_smoothing": snapshot_data.get("temporal_smoothing", False)
                },
                "detections": snapshot_data.get("detections", []),
                "zones": snapshot_data.get("zones_status", []),
                "metadata": {
                    "version": "2.0.0",
                    "airport_demo": True,
                    "saved_at": epoch
                }
            }
            
            # Save using centralized path management
            saved = save_snapshot_json(epoch, json_snapshot)
            
            if saved:
                self.logger.debug(f"Saved JSON snapshot for epoch {epoch}")
            else:
                self.logger.warning(f"Failed to save JSON snapshot for epoch {epoch}")
            
            return saved
            
        except Exception as e:
            self.logger.error(f"Error saving JSON snapshot for epoch {epoch}: {e}")
            return False