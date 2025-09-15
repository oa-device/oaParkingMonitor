"""
Edge device data models for simplified API
Models matching central API with camelCase field names
"""

import time
import uuid
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


def generate_uuid7() -> str:
    """Generate UUIDv7 for time-ordered unique identifiers"""
    return str(uuid.uuid7())


def get_epoch_ms() -> int:
    """Get current timestamp in milliseconds"""
    return int(time.time() * 1000)


# Core Detection Model
class Detection(BaseModel):
    """Detection data model matching central API format"""
    id: Optional[str] = Field(default_factory=generate_uuid7, description="Auto-generated if not provided")
    ts: int = Field(default_factory=get_epoch_ms, description="Detection timestamp in milliseconds")
    customerId: Optional[str] = Field(None, description="Customer ID - auto-filled from header")
    siteId: str = Field(..., description="Site identifier")
    zoneId: str = Field(..., description="Zone identifier")
    cameraId: str = Field(..., description="Camera identifier")
    totalSpaces: int = Field(..., description="Total parking spaces")
    occupiedSpaces: int = Field(..., description="Number of occupied spaces")
    uploaded: bool = Field(default=False, description="Upload status flag")


# Deployment Configuration
class DeploymentConfig(BaseModel):
    """Deployment identifiers for edge device"""
    customerId: str = Field(..., description="Customer identifier")
    siteId: str = Field(..., description="Site identifier")
    zoneId: str = Field(..., description="Zone identifier")
    cameraId: str = Field(..., description="Camera identifier")


class DeviceConfig(BaseModel):
    """Device metadata configuration"""
    physicalCameraId: str = Field(default="/dev/video0", description="Physical camera device")
    modelPath: str = Field(default="models/yolo11m.pt", description="AI model file path")
    modelVersion: str = Field(default="1.2.3", description="Model version")
    snapshotInterval: int = Field(default=5, description="Detection interval in seconds")
    totalSpaces: int = Field(default=50, description="Total parking spaces")


class VersionInfo(BaseModel):
    """Version and deployment information"""
    software: str = Field(default="2.0.0", description="Software version")
    deployed: str = Field(..., description="Deployment timestamp ISO format")
    hostname: str = Field(..., description="Device hostname")


class CentralApiConfig(BaseModel):
    """Central API configuration for batch upload"""
    enabled: bool = Field(default=False, description="Enable direct upload")
    endpoint: str = Field(default="", description="Central API URL")
    apiKey: str = Field(default="", description="API key")
    secretKey: str = Field(default="", description="Secret key")
    batchSize: int = Field(default=100, description="Upload batch size")
    submissionInterval: int = Field(default=60, description="Upload interval in seconds")


class EdgeConfig(BaseModel):
    """Complete edge device configuration"""
    deployment: DeploymentConfig
    device: DeviceConfig
    version: VersionInfo
    centralApi: Optional[CentralApiConfig] = None


# API Response Models
class HealthResponse(BaseModel):
    """Minimal health check response - exactly 2 fields per TODO.md"""
    status: str = Field(default="ok", description="Health status")
    ts: int = Field(default_factory=get_epoch_ms, description="Response timestamp")


class ErrorResponse(BaseModel):
    """Unified error response model"""
    error: str = Field(..., description="Error type or category")
    message: str = Field(..., description="Detailed error message")
    ts: int = Field(default_factory=get_epoch_ms, description="Error timestamp")


class OperationResponse(BaseModel):
    """Standard operation success response"""
    status: str = Field(..., description="Operation status")
    message: str = Field(..., description="Operation result message")
    ts: int = Field(default_factory=get_epoch_ms, description="Operation timestamp")


class DetectionSnapshot(BaseModel):
    """Current parking state snapshot"""
    ts: int = Field(default_factory=get_epoch_ms, description="Snapshot timestamp")
    totalSpaces: int = Field(..., description="Total parking spaces")
    occupiedSpaces: int = Field(..., description="Currently occupied spaces")


class DetectionBatch(BaseModel):
    """Batch detection response"""
    detections: List[Detection] = Field(..., description="List of detections")
    total: int = Field(..., description="Total detections returned")
    fromTs: Optional[int] = Field(None, description="Start timestamp filter")
    toTs: Optional[int] = Field(None, description="End timestamp filter")


class ConfigResponse(BaseModel):
    """Configuration response - matches TODO.md structure exactly"""
    deployment: DeploymentConfig = Field(..., description="Deployment identifiers")
    device: DeviceConfig = Field(..., description="Device metadata configuration")
    version: VersionInfo = Field(..., description="Version and deployment information")


class ConfigUpdateRequest(BaseModel):
    """Configuration update request"""
    apiKey: str = Field(..., description="API key for authentication")
    deployment: DeploymentConfig


# Camera Debug Models
class CameraStatus(BaseModel):
    """Camera status for debugging - matches TODO.md format"""
    connected: bool = Field(..., description="Camera connection status")
    fps: Optional[float] = Field(None, description="Frames per second")
    resolution: Optional[str] = Field(None, description="Camera resolution")
    autofocus: Optional[bool] = Field(None, description="Autofocus enabled")
    lastFrameTs: int = Field(default_factory=get_epoch_ms, description="Last frame timestamp")
    status: str = Field(..., description="Overall camera health status")


class CameraRestartRequest(BaseModel):
    """Camera restart request"""
    apiKey: str = Field(..., description="API key for authentication")
    reason: str = Field(default="Manual restart requested", description="Restart reason")


# Batch Upload Models
class UploadBatch(BaseModel):
    """Batch for central API upload"""
    detections: List[Detection] = Field(..., description="Detections to upload")
    headers: Dict[str, str] = Field(..., description="HTTP headers")


class UploadStatus(BaseModel):
    """Upload operation status"""
    success: bool = Field(..., description="Upload success")
    uploadedCount: int = Field(..., description="Number of detections uploaded")
    failedCount: int = Field(default=0, description="Number of failed uploads")
    error: Optional[str] = Field(None, description="Error message if failed")
    timestamp: int = Field(default_factory=get_epoch_ms, description="Operation timestamp")