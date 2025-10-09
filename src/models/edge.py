"""
Edge device data models for simplified API
Models matching central API with camelCase field names
"""

import time
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid_utils import uuid7


def generate_uuid7() -> str:
    """Generate UUIDv7 for time-ordered unique identifiers using uuid-utils"""
    return str(uuid7())


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
    """Batch detection response with pagination support"""
    detections: List[Detection] = Field(..., description="List of detections")
    total: int = Field(..., description="Total detections returned")
    fromTs: Optional[int] = Field(None, description="Start timestamp filter")
    toTs: Optional[int] = Field(None, description="End timestamp filter")
    hasMore: bool = Field(default=False, description="Indicates if more results are available")
    nextFromTs: Optional[int] = Field(None, description="Cursor for next batch (timestamp of oldest detection)")


class ConfigResponse(BaseModel):
    """Configuration response - matches TODO.md structure exactly"""
    deployment: DeploymentConfig = Field(..., description="Deployment identifiers")
    device: DeviceConfig = Field(..., description="Device metadata configuration")
    version: VersionInfo = Field(..., description="Version and deployment information")


class ProcessingConfigUpdate(BaseModel):
    """Runtime processing configuration updates"""
    snapshot_interval: Optional[int] = Field(None, ge=1, le=300, description="Snapshot interval in seconds")
    confidence_threshold: Optional[float] = Field(None, ge=0.1, le=1.0, description="Detection confidence threshold")
    nms_threshold: Optional[float] = Field(None, ge=0.1, le=1.0, description="Non-maximum suppression threshold")
    max_detections: Optional[int] = Field(None, ge=1, le=1000, description="Maximum detections per frame")


class ConfigUpdateRequest(BaseModel):
    """Configuration update request"""
    apiKey: str = Field(..., description="API key for authentication")
    deployment: Optional[DeploymentConfig] = Field(None, description="Deployment configuration updates")
    processing: Optional[ProcessingConfigUpdate] = Field(None, description="Processing configuration updates")


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


class ConfirmUploadRequest(BaseModel):
    """Request to confirm detections have been uploaded to cloud"""
    ids: List[str] = Field(..., description="List of detection IDs to mark as uploaded")


class ConfirmUploadResponse(BaseModel):
    """Response confirming upload status update"""
    success: bool = Field(..., description="Confirmation success")
    confirmedCount: int = Field(..., description="Number of detections confirmed")
    failedIds: List[str] = Field(default_factory=list, description="IDs that failed to confirm")
    timestamp: int = Field(default_factory=get_epoch_ms, description="Confirmation timestamp")


# Delta Update Models
class ZoneChange(BaseModel):
    """Represents a single zone state change for delta updates"""
    zoneId: str = Field(..., description="Zone identifier")
    spaceId: str = Field(..., description="Space identifier")
    name: str = Field(..., description="Zone name")
    previousState: bool = Field(..., description="Previous occupied state")
    currentState: bool = Field(..., description="Current occupied state")
    previousConfidence: float = Field(..., description="Previous confidence score")
    currentConfidence: float = Field(..., description="Current confidence score")
    timestamp: int = Field(..., description="Change timestamp in milliseconds")


class DeltaResponse(BaseModel):
    """Delta update response with only changed zones"""
    changes: List[ZoneChange] = Field(..., description="List of zone changes")
    sinceTimestamp: int = Field(..., description="Requested since timestamp")
    responseTimestamp: int = Field(default_factory=get_epoch_ms, description="Response timestamp")
    totalChanges: int = Field(..., description="Number of changes in response")
    hasMoreChanges: bool = Field(default=False, description="Whether more changes exist beyond retention window")