"""
Core Configuration Models
Pydantic models for parking monitor configuration with validation
"""

from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import time
from pydantic import BaseModel, Field, field_validator, model_validator

from .enums import DetectionDifficulty, LogLevel

# Import shared models
from ..models.shared import (
    CameraSettings,
    ImageEnhancement,
    ProcessingSettings,
    APISettings,
    VideoSource,
)


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


# Shared models imported above - no longer defined here

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
                "detection_difficulty": zone.detection_difficulty.value if hasattr(zone.detection_difficulty, "value") else zone.detection_difficulty,
                "occupied": zone.occupied,
                "confidence": zone.confidence,
                "last_detection": zone.last_detection
            }
            for zone in self.parking_zones
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for API responses using DataAccessor"""
        from ..services.data_accessor import DataAccessor
        
        # Use DataAccessor for automatic flattening
        accessor = DataAccessor(self)
        return accessor.get_data(format_type="flat", include_metadata=False)