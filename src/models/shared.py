"""
Shared Pydantic Models for oaParkingMonitor
Single source of truth for all data models used across API and config layers
"""

from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import time
from pydantic import BaseModel, Field, field_validator

from ..config.enums import DetectionDifficulty, LogLevel


# Core Camera Settings Models
class CameraSettings(BaseModel):
    """Unified camera hardware configuration with validation"""
    
    # Resolution and frame rate
    width: int = Field(1920, ge=640, le=3840, description="Camera resolution width")
    height: int = Field(1080, ge=480, le=2160, description="Camera resolution height") 
    fps: int = Field(30, ge=1, le=60, description="Camera frame rate")
    
    # Exposure and gain
    exposure: float = Field(0.25, ge=-1.0, le=1.0, description="Manual exposure (-1 for auto)")
    gain: float = Field(0.3, ge=-1.0, le=1.0, description="Camera gain (-1 for auto)")
    
    # Image quality parameters
    brightness: float = Field(0.4, ge=0.0, le=1.0, description="Camera brightness")
    contrast: float = Field(0.6, ge=0.0, le=1.0, description="Camera contrast")
    saturation: float = Field(0.5, ge=0.0, le=1.0, description="Camera saturation")
    sharpness: float = Field(0.6, ge=0.0, le=1.0, description="Camera sharpness")
    white_balance: float = Field(-1.0, ge=-1.0, le=1.0, description="White balance (-1 for auto)")
    
    # Focus and initialization
    autofocus: bool = Field(True, description="Enable autofocus if supported")
    warmup_frames: int = Field(10, ge=1, le=50, description="Warmup frames to discard")
    buffer_size: int = Field(1, ge=1, le=10, description="Camera buffer size")
    mirror: bool = Field(False, description="Mirror camera image horizontally")


# Dynamic models created by ModelFactory - no longer duplicated here
from .model_factory import ModelFactory

# Create camera models dynamically to eliminate duplication
_camera_models = ModelFactory.get_all_camera_models()

# Export dynamically created models
CameraResolutionSettings = _camera_models['CameraResolutionSettings']
CameraExposureSettings = _camera_models['CameraExposureSettings'] 
CameraImageQuality = _camera_models['CameraImageQuality']
CameraFocusSettings = _camera_models['CameraFocusSettings']
CameraEnhancementSettings = _camera_models['CameraEnhancementSettings']
CameraMiscSettings = _camera_models['CameraMiscSettings']
CameraSettingsRequest = _camera_models['CameraSettingsRequest']
CameraSettingsResponse = _camera_models['CameraSettingsResponse']
CameraPresetInfo = _camera_models['CameraPresetInfo']
CameraPresetsResponse = _camera_models['CameraPresetsResponse']
CameraOperationResponse = _camera_models['CameraOperationResponse']