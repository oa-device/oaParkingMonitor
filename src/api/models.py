"""
API Models for oaParkingMonitor
Centralized Pydantic models for all API requests and responses
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


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


# Camera Control Models
class CameraResolutionSettings(BaseModel):
    """Camera resolution and frame rate settings"""
    width: int = Field(default=1920, ge=640, le=3840, description="Camera width resolution")
    height: int = Field(default=1080, ge=480, le=2160, description="Camera height resolution")
    fps: int = Field(default=30, ge=1, le=60, description="Camera frame rate")


class CameraExposureSettings(BaseModel):
    """Camera exposure control settings"""
    mode: str = Field(default="manual", description="Exposure mode: 'auto' or 'manual'")
    value: float = Field(default=0.25, ge=0.0, le=1.0, description="Manual exposure value (0-1)")


class CameraImageQuality(BaseModel):
    """Camera image quality parameters"""
    gain: float = Field(default=0.3, ge=0.0, le=1.0, description="Camera gain (0-1)")
    brightness: float = Field(default=0.4, ge=0.0, le=1.0, description="Camera brightness (0-1)")
    contrast: float = Field(default=0.6, ge=0.0, le=1.0, description="Camera contrast (0-1)")
    saturation: float = Field(default=0.5, ge=0.0, le=1.0, description="Camera saturation (0-1)")
    sharpness: float = Field(default=0.6, ge=0.0, le=1.0, description="Camera sharpness (0-1)")


class CameraFocusSettings(BaseModel):
    """Camera focus and white balance settings"""
    autofocus: bool = Field(default=True, description="Enable automatic focus")
    white_balance: str = Field(default="auto", description="White balance mode: 'auto' or 'manual'")
    white_balance_value: float = Field(default=-1.0, ge=-1.0, le=1.0, description="Manual white balance value")


class CameraEnhancementSettings(BaseModel):
    """Image enhancement and processing settings"""
    auto_enhance: bool = Field(default=True, description="Enable automatic image enhancement")
    gamma_correction: float = Field(default=0.8, ge=0.5, le=2.0, description="Gamma correction factor")
    histogram_equalization: bool = Field(default=False, description="Enable histogram equalization")
    clahe_enabled: bool = Field(default=True, description="Enable CLAHE contrast enhancement")
    clahe_clip_limit: float = Field(default=3.0, ge=1.0, le=6.0, description="CLAHE clip limit")
    clahe_tile_grid_size: int = Field(default=8, ge=4, le=16, description="CLAHE tile grid size")


class CameraMiscSettings(BaseModel):
    """Miscellaneous camera settings"""
    mirror: bool = Field(default=False, description="Mirror camera image horizontally")
    warmup_frames: int = Field(default=10, ge=1, le=50, description="Number of warmup frames")
    buffer_size: int = Field(default=1, ge=1, le=10, description="Camera buffer size")


class CameraSettingsRequest(BaseModel):
    """Request model for updating camera settings"""
    resolution: Optional[CameraResolutionSettings] = Field(None, description="Resolution settings")
    exposure: Optional[CameraExposureSettings] = Field(None, description="Exposure settings")
    image_quality: Optional[CameraImageQuality] = Field(None, description="Image quality settings")
    focus: Optional[CameraFocusSettings] = Field(None, description="Focus settings")
    enhancement: Optional[CameraEnhancementSettings] = Field(None, description="Enhancement settings")
    misc: Optional[CameraMiscSettings] = Field(None, description="Miscellaneous settings")


class CameraSettingsResponse(BaseModel):
    """Response model for camera settings"""
    camera_settings: Dict = Field(..., description="Current camera settings grouped by category")
    is_camera_device: bool = Field(..., description="Whether using a camera device or video file")
    device_initialized: bool = Field(..., description="Whether the camera device is initialized")
    server_time_epoch: float = Field(..., description="Server timestamp")


class CameraPresetInfo(BaseModel):
    """Information about a camera preset"""
    name: str = Field(..., description="Preset display name")
    description: str = Field(..., description="Preset description")
    settings: Dict = Field(..., description="Preset camera settings")


class CameraPresetsResponse(BaseModel):
    """Response model for available camera presets"""
    presets: Dict[str, CameraPresetInfo] = Field(..., description="Available camera presets")
    current_preset: str = Field(..., description="Currently active preset name")
    server_time_epoch: float = Field(..., description="Server timestamp")


class CameraOperationResponse(BaseModel):
    """Response model for camera operations (apply/reset)"""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Operation result message")
    applied_at: Optional[str] = Field(None, description="Timestamp when settings were applied")
    preset: Optional[str] = Field(None, description="Preset name if applicable")
    error: Optional[str] = Field(None, description="Error message if operation failed")


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
    device: str = Field(..., description="Processing device (cpu/cuda/mps)")
    total_zones: int = Field(..., description="Total parking zones configured")


class ConfigResponse(BaseModel):
    """Configuration response model"""
    configuration: Dict[str, Any] = Field(..., description="Current configuration")
    metadata: Dict[str, Any] = Field(..., description="Configuration metadata")