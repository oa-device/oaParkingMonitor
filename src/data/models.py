"""
Database Models for Parking Monitor
SQLAlchemy models for persistent data storage
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, AsyncGenerator

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, 
    ForeignKey, JSON, Text, create_engine, Index, text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import relationship, sessionmaker

# Base model
Base = declarative_base()

# Database configuration
DB_PATH = Path.home() / "orangead" / "oaParkingMonitor" / "data" / "parking_monitor.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# Async engine and session
async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_recycle=3600
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class DetectionSnapshot(Base):
    """Represents a snapshot detection at a specific time"""
    __tablename__ = "detection_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    epoch_time = Column(Float, index=True)
    frame_path = Column(String, nullable=True)
    
    # Aggregated metrics
    total_occupied = Column(Integer, default=0)
    total_vacant = Column(Integer, default=0)
    occupancy_rate = Column(Float, default=0.0)
    
    # Processing metrics
    processing_time = Column(Float, default=0.0)
    detection_method = Column(String, default="multi_scale")
    confidence_avg = Column(Float, default=0.0)
    
    # Temporal metrics
    stable_detections = Column(Integer, default=0)
    temporal_smoothing_applied = Column(Boolean, default=False)
    
    # Relationships
    vehicle_detections = relationship("VehicleDetection", back_populates="snapshot", cascade="all, delete-orphan")
    zone_statuses = relationship("OccupancyHistory", back_populates="snapshot", cascade="all, delete-orphan")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_snapshot_timestamp', 'timestamp'),
        Index('idx_snapshot_epoch', 'epoch_time'),
    )


class VehicleDetection(Base):
    """Individual vehicle detection record"""
    __tablename__ = "vehicle_detections"
    
    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("detection_snapshots.id"), index=True)
    zone_id = Column(Integer, ForeignKey("parking_zones.id"), nullable=True, index=True)
    
    # Detection data
    bbox_x = Column(Float)
    bbox_y = Column(Float)
    bbox_width = Column(Float)
    bbox_height = Column(Float)
    confidence = Column(Float)
    
    # Enhanced detection metadata
    vehicle_type = Column(String, default="vehicle")
    tracked_id = Column(String, nullable=True)
    is_ghost = Column(Boolean, default=False)  # Ghost detection for persistence
    multi_scale_confirmed = Column(Boolean, default=False)
    detection_scales = Column(Integer, default=1)
    
    # Temporal tracking
    tracked_duration = Column(Float, default=0.0)
    stable_frames = Column(Integer, default=0)
    
    # Relationships
    snapshot = relationship("DetectionSnapshot", back_populates="vehicle_detections")
    zone = relationship("ParkingZone", back_populates="detections")
    
    # Indexes
    __table_args__ = (
        Index('idx_detection_snapshot', 'snapshot_id'),
        Index('idx_detection_zone', 'zone_id'),
        Index('idx_detection_tracked', 'tracked_id'),
    )


class ParkingZone(Base):
    """Parking zone definition and current state"""
    __tablename__ = "parking_zones"
    
    id = Column(Integer, primary_key=True, index=True)
    space_id = Column(Integer, unique=True, index=True)
    name = Column(String, unique=True)
    description = Column(String)
    
    # Zone geometry
    coordinates = Column(JSON)  # Store as JSON array
    detection_difficulty = Column(String, default="easy")
    
    # Current state (updated in real-time)
    current_occupied = Column(Boolean, default=False)
    current_confidence = Column(Float, default=0.0)
    last_state_change = Column(DateTime, nullable=True)
    
    # Statistics
    total_occupancy_time = Column(Float, default=0.0)  # Total seconds occupied
    total_detections = Column(Integer, default=0)
    avg_confidence = Column(Float, default=0.0)
    stability_score = Column(Float, default=0.0)
    
    # Relationships
    detections = relationship("VehicleDetection", back_populates="zone")
    history = relationship("OccupancyHistory", back_populates="zone", cascade="all, delete-orphan")


class OccupancyHistory(Base):
    """Historical occupancy records for analytics"""
    __tablename__ = "occupancy_history"
    
    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer, ForeignKey("parking_zones.id"), index=True)
    snapshot_id = Column(Integer, ForeignKey("detection_snapshots.id"), index=True)
    
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    epoch_time = Column(Float, index=True)
    
    # Occupancy data
    occupied = Column(Boolean)
    confidence = Column(Float)
    detection_count = Column(Integer, default=0)
    
    # Enhanced metadata
    detection_method = Column(String)  # center, multi_point, iou
    stable_frames = Column(Integer, default=0)
    temporal_smoothed = Column(Boolean, default=False)
    
    # Relationships
    zone = relationship("ParkingZone", back_populates="history")
    snapshot = relationship("DetectionSnapshot", back_populates="zone_statuses")
    
    # Indexes for time-series queries
    __table_args__ = (
        Index('idx_history_zone_time', 'zone_id', 'timestamp'),
        Index('idx_history_snapshot', 'snapshot_id'),
        Index('idx_history_epoch', 'epoch_time'),
    )


class SystemMetrics(Base):
    """System performance and health metrics"""
    __tablename__ = "system_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    epoch_time = Column(Float, index=True)
    
    # Performance metrics
    fps = Column(Float)
    memory_usage_mb = Column(Float)
    cpu_usage_percent = Column(Float)
    detection_latency_ms = Column(Float)
    
    # Detection metrics
    total_frames_processed = Column(Integer)
    total_vehicles_detected = Column(Integer)
    multi_scale_detections = Column(Integer)
    temporal_corrections = Column(Integer)
    
    # Model metrics
    model_loaded = Column(Boolean)
    device_type = Column(String)
    inference_count = Column(Integer)
    avg_inference_time = Column(Float)
    
    # Additional metadata
    extra_metadata = Column(JSON, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_metrics_timestamp', 'timestamp'),
        Index('idx_metrics_epoch', 'epoch_time'),
    )


# Database initialization functions
async def init_database():
    """Initialize database and create tables"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Initialize parking zones from config
    from ..config import ConfigManager
    config_manager = ConfigManager()
    config = config_manager.config
    
    async with AsyncSessionLocal() as session:
        # Check if zones already exist
        existing_zones = await session.execute(
            text("SELECT COUNT(*) FROM parking_zones")
        )
        count = existing_zones.scalar()
        
        if count == 0:
            # Add zones from config
            for zone_config in config.parking_zones:
                zone = ParkingZone(
                    id=zone_config.id,
                    space_id=zone_config.space_id,
                    name=zone_config.name,
                    description=zone_config.description,
                    coordinates=json.dumps(zone_config.coordinates),
                    detection_difficulty=zone_config.detection_difficulty
                )
                session.add(zone)
            
            await session.commit()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Data retention policy
class DataRetentionPolicy:
    """Manages data retention and cleanup"""
    
    DEFAULT_RETENTION_DAYS = 7
    
    @staticmethod
    async def cleanup_old_data(session: AsyncSession, retention_days: int = None):
        """Remove data older than retention period"""
        if retention_days is None:
            retention_days = DataRetentionPolicy.DEFAULT_RETENTION_DAYS
        
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        # Delete old snapshots (cascades to related tables)
        await session.execute(
            text("DELETE FROM detection_snapshots WHERE timestamp < :cutoff"),
            {"cutoff": cutoff_date}
        )
        
        # Delete old metrics
        await session.execute(
            text("DELETE FROM system_metrics WHERE timestamp < :cutoff"),
            {"cutoff": cutoff_date}
        )
        
        await session.commit()


# Export for easy imports
from datetime import timedelta

__all__ = [
    "Base",
    "DetectionSnapshot",
    "VehicleDetection",
    "ParkingZone",
    "OccupancyHistory",
    "SystemMetrics",
    "DataRetentionPolicy",
    "init_database",
    "get_async_session",
    "AsyncSessionLocal"
]