"""
Shared Pydantic Models for oaParkingMonitor
Single source of truth for all data models used across API and config layers
"""

from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import time
from pydantic import BaseModel, Field, field_validator

from .enums import DetectionDifficulty, LogLevel


# Core Camera Settings Models
class CameraSettings(BaseModel):
    """Unified camera hardware configuration with validation"""
    
    # Resolution and frame rate
    width: int = Field(1920, ge=640, le=3840, description="Camera resolution width")
    height: int = Field(1080, ge=480, le=2160, description="Camera resolution height") 
    fps: int = Field(30, ge=1, le=60, description="Camera frame rate")
    
    # Preset-based configuration
    active_preset: Optional[str] = Field(default=None, description="Active camera preset name")
    
    # Image quality parameters (populated from preset or fallback to defaults)
    exposure: float = Field(0.25, ge=-1.0, le=1.0, description="Manual exposure (-1 for auto)")
    gain: float = Field(0.3, ge=-1.0, le=1.0, description="Camera gain (-1 for auto)")
    brightness: float = Field(0.4, ge=0.0, le=1.0, description="Camera brightness")
    contrast: float = Field(0.6, ge=0.0, le=1.0, description="Camera contrast")
    saturation: float = Field(0.5, ge=0.0, le=1.0, description="Camera saturation")
    
    # Physical camera parameters (not affected by presets)
    sharpness: float = Field(0.6, ge=0.0, le=1.0, description="Camera sharpness")
    white_balance: float = Field(-1.0, ge=-1.0, le=1.0, description="White balance (-1 for auto)")
    
    # Focus and initialization
    autofocus: bool = Field(True, description="Enable autofocus if supported")
    warmup_frames: int = Field(10, ge=1, le=50, description="Warmup frames to discard")
    buffer_size: int = Field(1, ge=1, le=10, description="Camera buffer size")
    mirror: bool = Field(False, description="Mirror camera image horizontally")


class ImageEnhancement(BaseModel):
    """Image enhancement and preprocessing settings"""
    
    auto_enhance: bool = Field(False, description="Enable automatic image enhancement")
    histogram_equalization: bool = Field(False, description="Enable histogram equalization")
    clahe_tile_grid_size: int = Field(8, ge=2, le=16, description="CLAHE tile grid size")
    
    # Enhancement parameters (populated from preset)
    gamma_correction: float = Field(1.0, ge=0.1, le=3.0, description="Gamma correction factor")
    clahe_enabled: bool = Field(False, description="Enable CLAHE (Contrast Limited Adaptive Histogram Equalization)")
    clahe_clip_limit: float = Field(2.0, ge=1.0, le=10.0, description="CLAHE clip limit")


class ProcessingSettings(BaseModel):
    """Processing and detection configuration settings"""
    
    processing_enabled: bool = Field(True, description="Whether processing is enabled")
    confidence_threshold: float = Field(0.5, ge=0.1, le=1.0, description="Detection confidence threshold")
    nms_threshold: float = Field(0.4, ge=0.1, le=1.0, description="Non-maximum suppression threshold")
    snapshot_interval: int = Field(5, ge=1, le=60, description="Snapshot interval in seconds")
    max_detections: int = Field(100, ge=1, le=1000, description="Maximum detections per frame")
    model_path: str = Field("models/yolo11m.pt", description="Path to YOLO model file")


class APISettings(BaseModel):
    """API server configuration settings"""
    
    host: str = Field("0.0.0.0", description="API server host")
    port: int = Field(9091, ge=1024, le=65535, description="API server port")
    debug: bool = Field(False, description="Enable debug mode")
    reload: bool = Field(False, description="Enable auto-reload")


class VideoSource(BaseModel):
    """Video source configuration settings"""
    
    source: str = Field("0", description="Video source (camera index or file path)")
    is_camera: bool = Field(True, description="Whether source is a camera device")
    loop_video: bool = Field(True, description="Loop video playback for files")


# Note: Dynamic models from ModelFactory are not imported here to avoid circular dependency
# They can be imported directly from model_factory when needed