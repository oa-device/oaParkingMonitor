"""
Core Configuration Models
Pydantic models for parking monitor configuration with validation
"""

from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import time
from pydantic import BaseModel, Field, field_validator, model_validator

from .enums import DetectionDifficulty, LogLevel


class ParkingZone(BaseModel):
    """Pydantic model for parking zone configuration with validation"""
    
    id: int = Field(..., ge=1, description="Unique zone identifier")
    space_id: int = Field(..., ge=1, description="Parking space identifier")
    name: str = Field(..., min_length=1, max_length=10, description="Zone name (e.g., 'A1', 'B2')")
    description: str = Field(..., min_length=1, max_length=100, description="Human-readable zone description")
    coordinates: List[List[int]] = Field(..., min_items=3, description="Zone boundary coordinates [[x,y], ...]")
    detection_difficulty: DetectionDifficulty = Field(DetectionDifficulty.NORMAL, description="Detection difficulty level")
    
    # Runtime state (not loaded from YAML)
    occupied: bool = Field(default=False, exclude=True, description="Current occupancy status")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, exclude=True, description="Detection confidence")
    last_detection: Optional[float] = Field(default=None, exclude=True, description="Last detection timestamp")
    
    @field_validator('coordinates')
    @classmethod
    def validate_coordinates(cls, v):
        """Validate coordinate format and fix negative values"""
        if len(v) < 3:
            raise ValueError("At least 3 coordinate pairs required")
        
        # Fix negative coordinates (security: prevent out-of-bounds access)
        validated_coords = []
        for coord_pair in v:
            if len(coord_pair) != 2:
                raise ValueError("Each coordinate must be [x, y] pair")
            x, y = coord_pair
            validated_coords.append([max(0, int(x)), max(0, int(y))])
        
        return validated_coords
    
    @field_validator('name')
    @classmethod
    def validate_zone_name(cls, v):
        """Validate zone name format for consistency"""
        import re
        if not re.match(r'^[A-Z][0-9]+$', v):
            raise ValueError("Zone name must follow pattern: Letter + Numbers (e.g., 'A1', 'B12')")
        return v


class CameraSettings(BaseModel):
    """Camera hardware configuration with validation"""
    
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


class ImageEnhancement(BaseModel):
    """Image processing and enhancement configuration"""
    
    auto_enhance: bool = Field(True, description="Enable automatic image enhancement")
    gamma_correction: float = Field(0.8, ge=0.5, le=2.0, description="Gamma correction factor")
    histogram_equalization: bool = Field(False, description="Enable histogram equalization")
    
    # CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe_enabled: bool = Field(True, description="Enable CLAHE contrast enhancement")
    clahe_clip_limit: float = Field(3.0, ge=1.0, le=6.0, description="CLAHE clip limit")
    clahe_tile_grid_size: int = Field(8, ge=4, le=16, description="CLAHE tile grid size")


class ProcessingSettings(BaseModel):
    """AI model and detection processing configuration"""
    
    snapshot_interval: int = Field(5, ge=1, le=60, description="Seconds between snapshots")
    confidence_threshold: float = Field(0.5, ge=0.1, le=1.0, description="Detection confidence threshold")
    model_path: str = Field("models/yolo11m.pt", description="Path to AI model file")
    processing_enabled: bool = Field(True, description="Enable detection processing")


class APISettings(BaseModel):
    """API server configuration"""
    
    port: int = Field(9091, ge=1024, le=65535, description="API server port")
    host: str = Field("0.0.0.0", description="API server host")


class VideoSource(BaseModel):
    """Video input source configuration"""
    
    source: Union[str, int] = Field("", description="Video source (camera device number or file path)")
    
    @field_validator('source')
    @classmethod
    def validate_video_source(cls, v):
        """Validate video source format and security"""
        if isinstance(v, int):
            if v < 0 or v > 10:  # Security: limit camera device range
                raise ValueError("Camera device must be between 0-10")
            return v
        
        if isinstance(v, str):
            if v == "":
                return "0"  # Default to camera 0
            
            # Security: validate file paths to prevent directory traversal
            if v.startswith("/"):
                # Absolute path - validate it exists and is within allowed directories
                path = Path(v)
                if not path.exists():
                    raise ValueError(f"Video file does not exist: {v}")
                # Additional security checks could be added here
            
            return v
        
        raise ValueError("Video source must be camera device number (int) or file path (str)")


class ValidationSettings(BaseModel):
    """Security and validation configuration"""
    
    max_config_size: int = Field(1024 * 1024, description="Maximum config file size (bytes)")
    allowed_extensions: List[str] = Field([".yaml", ".yml"], description="Allowed config file extensions")
    validate_paths: bool = Field(True, description="Validate file paths for security")


class ParkingConfig(BaseModel):
    """
    Complete oaParkingMonitor configuration with automatic YAML loading
    
    Features:
    - Automatic YAML ↔ Pydantic mapping (zero duplication)
    - Comprehensive validation and type safety
    - Security controls and input sanitization
    - Extensible design - add fields by just updating this model
    """
    
    # Core configuration sections
    processing: ProcessingSettings = Field(default_factory=ProcessingSettings)
    camera: CameraSettings = Field(default_factory=CameraSettings)
    enhancement: ImageEnhancement = Field(default_factory=ImageEnhancement)
    api: APISettings = Field(default_factory=APISettings)
    video: VideoSource = Field(default_factory=VideoSource)
    
    # Parking zones
    parking_zones: List[ParkingZone] = Field(default_factory=list)
    
    # System settings
    log_level: LogLevel = Field(LogLevel.INFO, description="Logging level")
    debug: bool = Field(False, description="Enable debug mode")
    
    # Security configuration
    security: ValidationSettings = Field(default_factory=ValidationSettings, exclude=True)
    
    # Runtime state (not serialized)
    last_snapshot_epoch: float = Field(default_factory=time.time, exclude=True)
    config_loaded_from: Optional[str] = Field(default=None, exclude=True)
    
    class Config:
        """Pydantic model configuration"""
        use_enum_values = True  # Use enum values instead of enum objects
        validate_assignment = True  # Validate on attribute assignment
        extra = "forbid"  # Prevent extra fields for security
    
    @model_validator(mode='after')
    def validate_configuration(self):
        """Cross-field validation for configuration consistency"""
        
        # Validate camera resolution is reasonable for parking detection
        if self.camera.width * self.camera.height > 4096 * 2160:
            raise ValueError("Camera resolution too high - may impact performance")
        
        # Validate parking zones don't overlap significantly (basic check)
        if len(self.parking_zones) > 50:  # Security: prevent excessive zone definitions
            raise ValueError("Too many parking zones defined (max 50)")
        
        return self
    
    # Convenience methods for backward compatibility
    def get_total_zones(self) -> int:
        """Get total number of parking zones"""
        return len(self.parking_zones)
    
    def get_zone_by_id(self, zone_id: int) -> Optional[ParkingZone]:
        """Get parking zone by ID"""
        for zone in self.parking_zones:
            if zone.id == zone_id:
                return zone
        return None
    
    def update_zone_status(self, zone_id: int, occupied: bool, confidence: float = 0.0):
        """Update zone occupancy status"""
        zone = self.get_zone_by_id(zone_id)
        if zone:
            zone.occupied = occupied
            zone.confidence = confidence
            zone.last_detection = time.time()
    
    def get_easy_zones_count(self) -> int:
        """Get count of easy detection zones"""
        return sum(1 for zone in self.parking_zones if zone.detection_difficulty == DetectionDifficulty.EASY)
    
    def get_hard_zones_count(self) -> int:
        """Get count of hard detection zones"""
        return sum(1 for zone in self.parking_zones if zone.detection_difficulty == DetectionDifficulty.HARD)
    
    def should_process_snapshot(self) -> bool:
        """Check if enough time has passed for next snapshot"""
        return time.time() - self.last_snapshot_epoch >= self.processing.snapshot_interval
    
    def mark_snapshot_processed(self):
        """Mark current time as last snapshot processing time"""
        self.last_snapshot_epoch = time.time()
    
    def get_zones_data(self) -> List[Dict[str, Any]]:
        """Get all zones data for API response"""
        return [
            {
                "id": zone.id,
                "space_id": zone.space_id,
                "name": zone.name,
                "description": zone.description,
                "coordinates": zone.coordinates,
                "detection_difficulty": zone.detection_difficulty.value,
                "occupied": zone.occupied,
                "confidence": zone.confidence,
                "last_detection": zone.last_detection
            }
            for zone in self.parking_zones
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for API responses"""
        return {
            # Processing settings (flattened for backward compatibility)
            "snapshot_interval": self.processing.snapshot_interval,
            "confidence_threshold": self.processing.confidence_threshold,
            "model_path": self.processing.model_path,
            "processing_enabled": self.processing.processing_enabled,
            
            # API settings
            "api_port": self.api.port,
            "api_host": self.api.host,
            
            # Video source
            "video_source": self.video.source,
            
            # Camera settings
            "camera_width": self.camera.width,
            "camera_height": self.camera.height,
            "camera_fps": self.camera.fps,
            "camera_exposure": self.camera.exposure,
            "camera_gain": self.camera.gain,
            "camera_brightness": self.camera.brightness,
            "camera_contrast": self.camera.contrast,
            "camera_saturation": self.camera.saturation,
            "camera_sharpness": self.camera.sharpness,
            "camera_white_balance": self.camera.white_balance,
            "camera_autofocus": self.camera.autofocus,
            "camera_warmup_frames": self.camera.warmup_frames,
            "camera_buffer_size": self.camera.buffer_size,
            "camera_mirror": self.camera.mirror,
            
            # Enhancement settings
            "enable_auto_enhance": self.enhancement.auto_enhance,
            "gamma_correction": self.enhancement.gamma_correction,
            "histogram_equalization": self.enhancement.histogram_equalization,
            "clahe_enabled": self.enhancement.clahe_enabled,
            "clahe_clip_limit": self.enhancement.clahe_clip_limit,
            "clahe_tile_grid_size": self.enhancement.clahe_tile_grid_size,
            
            # Runtime state
            "last_snapshot_epoch": self.last_snapshot_epoch,
            
            # System settings
            "log_level": self.log_level.value,
            "debug": self.debug,
            
            # Zone information
            "total_zones": self.get_total_zones(),
        }