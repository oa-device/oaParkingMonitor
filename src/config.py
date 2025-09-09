"""
Simplified MVP configuration for oaParkingMonitor
Single configuration class with 6 default parking zones and snapshot processing
"""

import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ParkingZone:
    """Definition of a parking zone with detection coordinates"""
    id: int
    name: str
    coordinates: List[List[int]]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    space_id: int
    description: str
    detection_difficulty: str = "normal"  # "easy", "normal", "hard"
    occupied: bool = False
    confidence: float = 0.0
    last_detection: Optional[float] = None  # epoch timestamp
    
    def __post_init__(self):
        """Validate and fix coordinates"""
        # Fix negative coordinates (set to 0)
        self.coordinates = [[max(0, x), max(0, y)] for x, y in self.coordinates]


@dataclass
class MVPConfig:
    """Simplified MVP configuration for snapshot-based parking detection"""
    
    # Core processing settings
    snapshot_interval: int = 5  # seconds between snapshots
    confidence_threshold: float = 0.5
    model_path: str = "models/yolo11m.pt"
    
    # API settings
    api_port: int = 9091
    api_host: str = "0.0.0.0"
    
    # Video source settings
    video_source: str = ""  # Will be set to default path
    
    # Processing state
    last_snapshot_epoch: float = 0.0
    processing_enabled: bool = True
    
    # Updated 11 parking zones with real coordinates (1920x1080)
    parking_zones: List[ParkingZone] = field(default_factory=lambda: [
        # Main row zones (easy to detect, except A1)
        ParkingZone(
            id=1, space_id=1, name="A1", description="Front left space (partially visible)",
            coordinates=[[308, 306], [151, 296], [151, 561]], detection_difficulty="hard"
        ),
        ParkingZone(
            id=2, space_id=2, name="A2", description="Front row center-left",
            coordinates=[[511, 320], [320, 308], [153, 576], [384, 611]], detection_difficulty="easy"
        ),
        ParkingZone(
            id=3, space_id=3, name="A3", description="Front row center",
            coordinates=[[711, 328], [520, 320], [392, 612], [625, 633]], detection_difficulty="easy"
        ),
        ParkingZone(
            id=4, space_id=4, name="A4", description="Front row center-right",
            coordinates=[[914, 335], [719, 328], [630, 633], [867, 652]], detection_difficulty="easy"
        ),
        ParkingZone(
            id=5, space_id=5, name="A5", description="Front row right-center",
            coordinates=[[1132, 344], [922, 337], [874, 654], [1117, 669]], detection_difficulty="easy"
        ),
        ParkingZone(
            id=6, space_id=6, name="A6", description="Front row right",
            coordinates=[[1354, 354], [1135, 339], [1129, 667], [1383, 674]], detection_difficulty="easy"
        ),
        ParkingZone(
            id=7, space_id=7, name="A7", description="Front row far right",
            coordinates=[[1588, 365], [1361, 349], [1388, 678], [1677, 690]], detection_difficulty="easy"
        ),
        # Back row zones (hard to detect)
        ParkingZone(
            id=8, space_id=8, name="B1", description="Back row left",
            coordinates=[[998, 0], [982, 48], [1142, 65], [1166, 0]], detection_difficulty="hard"
        ),
        ParkingZone(
            id=9, space_id=9, name="B2", description="Back row center-left", 
            coordinates=[[1170, 0], [1151, 64], [1325, 81], [1338, 0]], detection_difficulty="hard"
        ),
        ParkingZone(
            id=10, space_id=10, name="B3", description="Back row center-right",
            coordinates=[[1349, 0], [1330, 84], [1516, 100], [1514, 0]], detection_difficulty="hard"
        ),
        ParkingZone(
            id=11, space_id=11, name="B4", description="Back row right",
            coordinates=[[1523, 3], [1519, 101], [1712, 100], [1689, 5]], detection_difficulty="hard"
        )
    ])
    
    # Logging settings
    log_level: str = "INFO"
    debug: bool = False
    
    def __post_init__(self):
        """Initialize default values and paths"""
        if not self.video_source:
            # Default to camera device 0 for production, staging path only in specific environments
            self.video_source = "0"
        
        # Initialize last snapshot time to current time
        if self.last_snapshot_epoch == 0.0:
            self.last_snapshot_epoch = time.time()
    
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
    
    def get_occupancy_summary(self) -> Dict[str, Any]:
        """Get overall occupancy summary"""
        total_zones = len(self.parking_zones)
        occupied_zones = sum(1 for zone in self.parking_zones if zone.occupied)
        occupancy_rate = occupied_zones / total_zones if total_zones > 0 else 0.0
        
        return {
            "total_zones": total_zones,
            "occupied_zones": occupied_zones,
            "available_zones": total_zones - occupied_zones,
            "occupancy_rate": round(occupancy_rate, 2),
            "last_update": self.last_snapshot_epoch
        }
    
    def get_zones_data(self) -> List[Dict[str, Any]]:
        """Get all zones data for API response"""
        return [
            {
                "id": zone.id,
                "name": zone.name,
                "coordinates": zone.coordinates,
                "occupied": zone.occupied,
                "confidence": zone.confidence,
                "last_detection": zone.last_detection
            }
            for zone in self.parking_zones
        ]
    
    def should_process_snapshot(self) -> bool:
        """Check if enough time has passed for next snapshot"""
        return time.time() - self.last_snapshot_epoch >= self.snapshot_interval
    
    def mark_snapshot_processed(self):
        """Mark current time as last snapshot processing time"""
        self.last_snapshot_epoch = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for API responses"""
        return {
            "snapshot_interval": self.snapshot_interval,
            "confidence_threshold": self.confidence_threshold,
            "model_path": self.model_path,
            "api_port": self.api_port,
            "api_host": self.api_host,
            "video_source": self.video_source,
            "last_snapshot_epoch": self.last_snapshot_epoch,
            "processing_enabled": self.processing_enabled,
            "total_zones": len(self.parking_zones),
            "log_level": self.log_level,
            "debug": self.debug
        }


class MVPConfigManager:
    """Simplified config manager for MVP"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file
        self._config: Optional[MVPConfig] = None
    
    @property 
    def config(self) -> MVPConfig:
        """Get current configuration, creating default if needed"""
        if self._config is None:
            self._config = MVPConfig()
        return self._config
    
    def load_config(self, config_file: Optional[str] = None) -> MVPConfig:
        """Load configuration from file (if provided) or use defaults"""
        if config_file:
            try:
                import yaml
                config_path = Path(config_file)
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        config_data = yaml.safe_load(f)
                    
                    # Extract parking zones separately for proper initialization
                    parking_zones_data = config_data.pop('parking_zones', [])
                    
                    # Create base config without zones
                    self._config = MVPConfig(**config_data)
                    
                    # Update zones if provided
                    if parking_zones_data:
                        self.update_zones(parking_zones_data)
                    
                else:
                    print(f"Config file {config_file} not found, using defaults")
                    self._config = MVPConfig()
            except Exception as e:
                print(f"Error loading config: {e}, using defaults")
                self._config = MVPConfig()
        else:
            self._config = MVPConfig()
        
        return self._config
    
    def save_config(self, config_file: Optional[str] = None) -> bool:
        """Save current configuration to file"""
        if not config_file:
            config_file = self.config_file
        
        if not config_file:
            return False
        
        try:
            import yaml
            config_path = Path(config_file)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert config to dictionary for YAML
            config_dict = {
                "snapshot_interval": self.config.snapshot_interval,
                "confidence_threshold": self.config.confidence_threshold,
                "model_path": self.config.model_path,
                "api_port": self.config.api_port,
                "api_host": self.config.api_host,
                "video_source": self.config.video_source,
                "processing_enabled": self.config.processing_enabled,
                "log_level": self.config.log_level,
                "debug": self.config.debug,
                "parking_zones": [
                    {
                        "id": zone.id,
                        "space_id": zone.space_id,
                        "name": zone.name,
                        "description": zone.description,
                        "coordinates": zone.coordinates,
                        "detection_difficulty": zone.detection_difficulty
                    }
                    for zone in self.config.parking_zones
                ]
            }
            
            with open(config_path, 'w') as f:
                yaml.dump(config_dict, f, default_flow_style=False, indent=2)
            
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        self._config = MVPConfig()
    
    def update_zones(self, zones_data: List[Dict[str, Any]]) -> bool:
        """Update parking zones from dictionary data"""
        try:
            new_zones = []
            for zone_data in zones_data:
                zone = ParkingZone(
                    id=zone_data['id'],
                    space_id=zone_data.get('space_id', zone_data['id']),
                    name=zone_data['name'],
                    description=zone_data.get('description', f"Parking space {zone_data['name']}"),
                    coordinates=zone_data['coordinates'],
                    detection_difficulty=zone_data.get('detection_difficulty', 'normal')
                )
                new_zones.append(zone)
            
            self.config.parking_zones = new_zones
            return True
        except Exception as e:
            print(f"Error updating zones: {e}")
            return False
    
    def get_environment(self) -> str:
        """Get environment for compatibility"""
        return "mvp"


# Legacy compatibility - redirect old classes to new MVP classes
ConfigManager = MVPConfigManager
ParkingConfig = MVPConfig

# For backward compatibility with existing detector code
@dataclass
class ParkingSpaceConfig:
    """Legacy parking space config for backward compatibility"""
    space_id: int
    x: int
    y: int  
    width: int
    height: int
    label: str = ""

@dataclass
class DetectionConfig:
    """Legacy detection config for backward compatibility"""
    confidence_threshold: float = 0.5
    model_path: str = "models/yolo11m.pt"
    processing_fps: int = 10
    vehicle_classes: List[str] = field(default_factory=lambda: ["car", "truck", "bus", "motorcycle"])

@dataclass
class VideoConfig:
    """Legacy video config for backward compatibility"""
    source_path: str = ""
    
    def __post_init__(self):
        if not self.source_path:
            home = Path.home()
            self.source_path = str(home / "orangead" / "staging-video-feed" / "videos" / "current.mp4")