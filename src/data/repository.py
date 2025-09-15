"""
Data Repository Pattern
Provides clean data access interface for the application
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import (
    DetectionSnapshot,
    VehicleDetection,
    ParkingZone,
    OccupancyHistory,
    SystemMetrics
)


class DataRepository:
    """Repository for all data operations"""
    
    def __init__(self, session: AsyncSession):
        """Initialize repository with database session"""
        self.session = session
        self.logger = logging.getLogger(__name__)
    
    # ============= Detection Snapshot Operations =============
    
    async def save_detection_snapshot(self, 
                                     snapshot_data: Dict[str, Any]) -> DetectionSnapshot:
        """Save a complete detection snapshot with all related data"""
        try:
            # Create snapshot
            snapshot = DetectionSnapshot(
                timestamp=datetime.utcnow(),
                epoch_time=snapshot_data.get("epoch_time", datetime.utcnow().timestamp()),
                frame_path=snapshot_data.get("frame_path"),
                total_occupied=snapshot_data.get("total_occupied", 0),
                total_vacant=snapshot_data.get("total_vacant", 0),
                processing_time=snapshot_data.get("processing_time", 0.0),
                detection_method=snapshot_data.get("detection_method", "multi_scale"),
                confidence_avg=snapshot_data.get("confidence_avg", 0.0),
                stable_detections=snapshot_data.get("stable_detections", 0),
                temporal_smoothing_applied=snapshot_data.get("temporal_smoothing", False)
            )
            
            self.session.add(snapshot)
            await self.session.flush()  # Get ID for relationships
            
            # Save vehicle detections
            for detection in snapshot_data.get("detections", []):
                vehicle = VehicleDetection(
                    snapshot_id=snapshot.id,
                    zone_id=detection.get("zone_id"),
                    bbox_x=detection["bbox"][0],
                    bbox_y=detection["bbox"][1],
                    bbox_width=detection["bbox"][2] - detection["bbox"][0],
                    bbox_height=detection["bbox"][3] - detection["bbox"][1],
                    confidence=detection["confidence"],
                    vehicle_type=detection.get("vehicle_type", "vehicle"),
                    tracked_id=detection.get("tracked_id"),
                    is_ghost=detection.get("is_ghost", False),
                    multi_scale_confirmed=detection.get("multi_scale_confirmed", False),
                    detection_scales=detection.get("detection_scales", 1),
                    tracked_duration=detection.get("tracked_duration", 0.0),
                    stable_frames=detection.get("stable_frames", 0)
                )
                self.session.add(vehicle)
            
            # Save zone occupancy history
            for zone_status in snapshot_data.get("zones_status", []):
                history = OccupancyHistory(
                    zone_id=zone_status["id"],
                    snapshot_id=snapshot.id,
                    timestamp=datetime.utcnow(),
                    epoch_time=snapshot_data.get("epoch_time", datetime.utcnow().timestamp()),
                    occupied=zone_status["occupied"],
                    confidence=zone_status["confidence"],
                    detection_count=zone_status.get("detection_count", 0),
                    detection_method=zone_status.get("detection_method", "unknown"),
                    stable_frames=zone_status.get("stable_frames", 0),
                    temporal_smoothed=zone_status.get("temporal_smoothed", False)
                )
                self.session.add(history)
                
                # Update zone current state
                await self.update_zone_state(
                    zone_status["id"],
                    zone_status["occupied"],
                    zone_status["confidence"]
                )
            
            await self.session.commit()
            self.logger.debug(f"Saved snapshot with {len(snapshot_data.get('detections', []))} detections")
            return snapshot
            
        except Exception as e:
            await self.session.rollback()
            self.logger.error(f"Failed to save detection snapshot: {e}")
            raise
    
    async def get_latest_snapshot(self) -> Optional[DetectionSnapshot]:
        """Get the most recent detection snapshot"""
        result = await self.session.execute(
            select(DetectionSnapshot)
            .options(selectinload(DetectionSnapshot.vehicle_detections))
            .options(selectinload(DetectionSnapshot.zone_statuses))
            .order_by(desc(DetectionSnapshot.timestamp))
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def get_snapshots_range(self, 
                                 start_time: datetime, 
                                 end_time: datetime) -> List[DetectionSnapshot]:
        """Get snapshots within a time range"""
        result = await self.session.execute(
            select(DetectionSnapshot)
            .where(and_(
                DetectionSnapshot.timestamp >= start_time,
                DetectionSnapshot.timestamp <= end_time
            ))
            .order_by(DetectionSnapshot.timestamp)
        )
        return result.scalars().all()
    
    # ============= Zone Operations =============
    
    async def update_zone_state(self, 
                               zone_id: int, 
                               occupied: bool, 
                               confidence: float):
        """Update current state of a parking zone"""
        zone = await self.session.get(ParkingZone, zone_id)
        if zone:
            # Check if state changed
            if zone.current_occupied != occupied:
                zone.last_state_change = datetime.utcnow()
            
            zone.current_occupied = occupied
            zone.current_confidence = confidence
            zone.total_detections += 1
            
            # Update running average confidence
            if zone.avg_confidence == 0:
                zone.avg_confidence = confidence
            else:
                zone.avg_confidence = (zone.avg_confidence * 0.9 + confidence * 0.1)
            
            # Update occupancy time if occupied
            if occupied and zone.last_state_change:
                duration = (datetime.utcnow() - zone.last_state_change).total_seconds()
                zone.total_occupancy_time += duration
    
    async def get_all_zones(self) -> List[ParkingZone]:
        """Get all parking zones with current state"""
        result = await self.session.execute(
            select(ParkingZone).order_by(ParkingZone.id)
        )
        return result.scalars().all()
    
    async def get_zone_history(self, 
                              zone_id: int, 
                              hours: int = 24) -> List[OccupancyHistory]:
        """Get occupancy history for a specific zone"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        result = await self.session.execute(
            select(OccupancyHistory)
            .where(and_(
                OccupancyHistory.zone_id == zone_id,
                OccupancyHistory.timestamp >= cutoff
            ))
            .order_by(OccupancyHistory.timestamp)
        )
        return result.scalars().all()
    
    async def get_zone_analytics(self, zone_id: int) -> Dict[str, Any]:
        """Get analytics for a specific zone"""
        zone = await self.session.get(ParkingZone, zone_id)
        if not zone:
            return {}
        
        # Get recent history for patterns
        history = await self.get_zone_history(zone_id, hours=24)
        
        # Calculate metrics
        total_samples = len(history)
        occupied_samples = sum(1 for h in history if h.occupied)
        occupancy_rate = occupied_samples / total_samples if total_samples > 0 else 0
        
        # Find longest occupied duration
        max_duration = 0
        current_duration = 0
        for h in history:
            if h.occupied:
                current_duration += 1
            else:
                max_duration = max(max_duration, current_duration)
                current_duration = 0
        
        return {
            "zone_id": zone_id,
            "zone_name": zone.name,
            "current_occupied": zone.current_occupied,
            "current_confidence": zone.current_confidence,
            "24h_occupancy_rate": occupancy_rate,
            "total_occupancy_time": zone.total_occupancy_time,
            "avg_confidence": zone.avg_confidence,
            "stability_score": zone.stability_score,
            "max_continuous_occupancy": max_duration * 5,  # Convert to seconds (5s intervals)
            "last_state_change": zone.last_state_change.isoformat() if zone.last_state_change else None
        }
    
    # ============= System Metrics Operations =============
    
    async def save_system_metrics(self, metrics: Dict[str, Any]):
        """Save system performance metrics"""
        try:
            metric = SystemMetrics(
                timestamp=datetime.utcnow(),
                epoch_time=datetime.utcnow().timestamp(),
                fps=metrics.get("fps", 0.0),
                memory_usage_mb=metrics.get("memory_usage_mb", 0.0),
                cpu_usage_percent=metrics.get("cpu_usage_percent", 0.0),
                detection_latency_ms=metrics.get("detection_latency_ms", 0.0),
                total_frames_processed=metrics.get("total_frames", 0),
                total_vehicles_detected=metrics.get("vehicles_detected", 0),
                multi_scale_detections=metrics.get("multi_scale_detections", 0),
                temporal_corrections=metrics.get("temporal_corrections", 0),
                model_loaded=metrics.get("model_loaded", False),
                device_type=metrics.get("device_type", "cpu"),
                inference_count=metrics.get("inference_count", 0),
                avg_inference_time=metrics.get("avg_inference_time", 0.0),
                metadata=metrics.get("metadata", {})
            )
            
            self.session.add(metric)
            await self.session.commit()
            
        except Exception as e:
            await self.session.rollback()
            self.logger.error(f"Failed to save system metrics: {e}")
    
    async def get_system_metrics(self, hours: int = 1) -> List[SystemMetrics]:
        """Get recent system metrics"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        result = await self.session.execute(
            select(SystemMetrics)
            .where(SystemMetrics.timestamp >= cutoff)
            .order_by(desc(SystemMetrics.timestamp))
        )
        return result.scalars().all()
    
    # ============= Analytics Operations =============
    
    async def get_occupancy_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Get occupancy trends over time"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        # Get snapshots in time range
        snapshots = await self.get_snapshots_range(cutoff, datetime.utcnow())
        
        if not snapshots:
            return {"error": "No data available"}
        
        # Calculate trends
        timestamps = []
        occupancy_rates = []
        occupied_counts = []
        
        for snapshot in snapshots:
            timestamps.append(snapshot.timestamp.isoformat())
            occupancy_rates.append(snapshot.occupancy_rate)
            occupied_counts.append(snapshot.total_occupied)
        
        return {
            "timestamps": timestamps,
            "occupancy_rates": occupancy_rates,
            "occupied_counts": occupied_counts,
            "avg_occupancy": sum(occupancy_rates) / len(occupancy_rates),
            "peak_occupancy": max(occupied_counts),
            "min_occupancy": min(occupied_counts)
        }
    
    async def get_zone_performance(self) -> List[Dict[str, Any]]:
        """Get performance metrics for all zones"""
        zones = await self.get_all_zones()
        
        performance = []
        for zone in zones:
            analytics = await self.get_zone_analytics(zone.id)
            performance.append({
                "zone_id": zone.id,
                "zone_name": zone.name,
                "difficulty": zone.detection_difficulty,
                "current_occupied": zone.current_occupied,
                "24h_occupancy_rate": analytics.get("24h_occupancy_rate", 0),
                "avg_confidence": zone.avg_confidence,
                "stability_score": zone.stability_score
            })
        
        return performance
    
    async def export_data(self, 
                         start_time: datetime, 
                         end_time: datetime, 
                         format: str = "json") -> Any:
        """Export data in specified format"""
        snapshots = await self.get_snapshots_range(start_time, end_time)
        
        if format == "json":
            data = []
            for snapshot in snapshots:
                data.append({
                    "timestamp": snapshot.timestamp.isoformat(),
                    "epoch_time": snapshot.epoch_time,
                    "total_occupied": snapshot.total_occupied,
                    "total_vacant": snapshot.total_vacant,
                    "occupancy_rate": snapshot.occupancy_rate,
                    "detections": len(snapshot.vehicle_detections),
                    "processing_time": snapshot.processing_time
                })
            return json.dumps(data, indent=2)
        
        elif format == "csv":
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow([
                "timestamp", "epoch_time", "total_occupied", 
                "total_vacant", "occupancy_rate", "detections", "processing_time"
            ])
            
            # Data rows
            for snapshot in snapshots:
                writer.writerow([
                    snapshot.timestamp.isoformat(),
                    snapshot.epoch_time,
                    snapshot.total_occupied,
                    snapshot.total_vacant,
                    snapshot.occupancy_rate,
                    len(snapshot.vehicle_detections),
                    snapshot.processing_time
                ])
            
            return output.getvalue()
        
        else:
            raise ValueError(f"Unsupported export format: {format}")