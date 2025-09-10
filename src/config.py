"""
Clean Configuration System
Compatibility wrapper for the new modular configuration package
"""

# Import from the new modular configuration package
from .config import (
    MVPConfig,
    MVPConfigManager,
    ParkingZone,
    CameraSettings,
    ImageEnhancement,
    ProcessingSettings,
    APISettings,
    VideoSource,
    DetectionDifficulty,
    LogLevel,
    # New recommended names
    ParkingConfig,
    ConfigManager,
)

# Re-export for compatibility
__all__ = [
    # Backward compatibility
    'MVPConfig',
    'MVPConfigManager', 
    'ParkingZone',
    'CameraSettings',
    'ImageEnhancement',
    'ProcessingSettings',
    'APISettings',
    'VideoSource',
    'DetectionDifficulty',
    'LogLevel',
    # New recommended names
    'ParkingConfig',
    'ConfigManager',
]