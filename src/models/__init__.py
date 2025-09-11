"""
Shared Pydantic models for oaParkingMonitor
Provides single source of truth for data models used across API and config
"""

from .shared import (
    # Core models
    CameraSettings,
    ImageEnhancement,
    ProcessingSettings,
    APISettings,
    VideoSource,
)

# Import dynamic models from ModelFactory
from .model_factory import ModelFactory

# Get dynamic models
_dynamic_models = ModelFactory.get_all_camera_models()

# Dynamic camera models
CameraResolutionSettings = _dynamic_models['CameraResolutionSettings']
CameraExposureSettings = _dynamic_models['CameraExposureSettings']
CameraImageQuality = _dynamic_models['CameraImageQuality']
CameraFocusSettings = _dynamic_models['CameraFocusSettings']
CameraEnhancementSettings = _dynamic_models['CameraEnhancementSettings']
CameraMiscSettings = _dynamic_models['CameraMiscSettings']

# Response models
CameraSettingsRequest = _dynamic_models['CameraSettingsRequest']
CameraSettingsResponse = _dynamic_models['CameraSettingsResponse']
CameraPresetInfo = _dynamic_models['CameraPresetInfo']
CameraPresetsResponse = _dynamic_models['CameraPresetsResponse']
CameraOperationResponse = _dynamic_models['CameraOperationResponse']

__all__ = [
    # Camera models
    "CameraSettings",
    "CameraResolutionSettings", 
    "CameraExposureSettings",
    "CameraImageQuality",
    "CameraFocusSettings",
    "CameraEnhancementSettings",
    "CameraMiscSettings",
    
    # Response models
    "CameraSettingsRequest",
    "CameraSettingsResponse", 
    "CameraPresetInfo",
    "CameraPresetsResponse",
    "CameraOperationResponse",
    
    # Core models
    "ImageEnhancement",
    "ProcessingSettings",
    "APISettings", 
    "VideoSource",
]