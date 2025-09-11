"""
oaParkingMonitor Configuration Package
Clean, modular configuration system with Pydantic models and automatic YAML mapping

Public API:
    from .config import ParkingConfig, ConfigManager
    from .config import ParkingZone, CameraSettings, ImageEnhancement
    from .config import DetectionDifficulty, LogLevel"""

# Core models and manager (recommended imports)
from .models import (
    ParkingConfig,
    ParkingZone,
    CameraSettings,
    ImageEnhancement,
    ProcessingSettings,
    APISettings,
    VideoSource,
    ValidationSettings,
)

from .manager import ConfigManager

from ..models.enums import DetectionDifficulty, LogLevel

from .validation import ConfigLoader, ConfigSaver, ConfigValidator

# Public API - what users should import
__all__ = [
    # Primary recommended imports
    "ParkingConfig",
    "ConfigManager",
    "ParkingZone",
    "CameraSettings", 
    "ImageEnhancement",
    "ProcessingSettings",
    "APISettings",
    "VideoSource",
    "ValidationSettings",
    
    # Enums
    "DetectionDifficulty",
    "LogLevel",
    
    # Validation utilities (advanced usage)
    "ConfigLoader",
    "ConfigSaver",
    "ConfigValidator",
]

# Package metadata
__version__ = "2.0.0"
__description__ = "Modular configuration system for oaParkingMonitor"