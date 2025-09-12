"""
API Models for oaParkingMonitor
Centralized Pydantic models for all API requests and responses
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

# Import shared models from models package
from ..models import (
    CameraResolutionSettings,
    CameraExposureSettings,
    CameraImageQuality,
    CameraFocusSettings,
    CameraEnhancementSettings,
    CameraMiscSettings,
    CameraSettingsRequest,
    CameraSettingsResponse,
    CameraPresetInfo,
    CameraPresetsResponse,
    CameraOperationResponse,
)


# Core Response Models
class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    service: str
    version: str
    uptime: float
    timestamp: str


class ErrorResponse(BaseModel):
    """Standard error response model"""
    error: str
    message: str
    timestamp: str
    status_code: int


# Camera Control Models - imported from shared models
# Detection and Status Models
class DetectionResponse(BaseModel):
    """Detection results response model"""
    vehicles_detected: int = Field(..., description="Number of vehicles detected")
    total_spaces: int = Field(..., description="Total parking spaces")
    occupied_spaces: int = Field(..., description="Number of occupied spaces")
    occupancy_rate: float = Field(..., description="Occupancy rate (0.0-1.0)")
    last_detection: Optional[str] = Field(None, description="Last detection timestamp")
    video_source: str = Field(..., description="Current video source")
    processing_fps: float = Field(..., description="Processing frames per second")
    last_update_epoch: float = Field(..., description="Last update timestamp")
    server_time_epoch: float = Field(..., description="Server timestamp")
    snapshot_interval: int = Field(..., description="Snapshot processing interval")
    easy_zones_count: int = Field(..., description="Number of easy detection zones")
    hard_zones_count: int = Field(..., description="Number of hard detection zones")


class ParkingZoneResponse(BaseModel):
    """Single parking zone information"""
    id: int = Field(..., description="Zone ID")
    name: str = Field(..., description="Zone name")
    coordinates: list = Field(..., description="Zone boundary coordinates")
    occupied: bool = Field(..., description="Current occupancy status")
    confidence: float = Field(..., description="Detection confidence")
    last_detection: Optional[float] = Field(None, description="Last detection timestamp")


class ZonesResponse(BaseModel):
    """Parking zones response model"""
    zones: list[ParkingZoneResponse] = Field(..., description="List of parking zones")
    total_zones: int = Field(..., description="Total number of zones")
    server_time_epoch: float = Field(..., description="Server timestamp")


class StatusResponse(BaseModel):
    """System status response model"""
    processing_enabled: bool = Field(..., description="Whether processing is enabled")
    snapshot_interval: int = Field(..., description="Snapshot interval in seconds")
    last_snapshot_epoch: float = Field(..., description="Last snapshot timestamp")
    server_time_epoch: float = Field(..., description="Current server timestamp")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")
    next_snapshot_in: float = Field(..., description="Seconds until next snapshot")
    model_loaded: bool = Field(..., description="Whether AI model is loaded")
    model_name: Optional[str] = Field(None, description="Name of the AI model file")
    device: str = Field(..., description="Processing device (cpu/cuda/mps)")
    total_zones: int = Field(..., description="Total parking zones configured")


class ConfigResponse(BaseModel):
    """Configuration response model"""
    configuration: Dict[str, Any] = Field(..., description="Current configuration")
    metadata: Dict[str, Any] = Field(..., description="Configuration metadata")