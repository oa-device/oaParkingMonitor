"""
Simplified MVP configuration for oaParkingMonitor
Single configuration class with 6 default parking zones and snapshot processing
"""

import logging
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
    
    # Core processing settings - loaded from YAML
    snapshot_interval: int = 5  # Default fallback, overridden by YAML
    confidence_threshold: float = 0.5  # Default fallback, overridden by YAML  
    model_path: str = "models/yolo11m.pt"  # Default fallback, overridden by YAML
    
    # API settings - loaded from YAML
    api_port: int = 9091  # Default fallback, overridden by YAML
    api_host: str = "0.0.0.0"  # Default fallback, overridden by YAML
    
    # Video source settings - loaded from YAML
    video_source: str = ""  # Default fallback, overridden by YAML
    camera_mirror: bool = False  # Default fallback, overridden by YAML
    
    # Camera settings for focus and initialization
    camera_warmup_frames: int = 10  # Number of frames to discard during camera warmup
    camera_autofocus: bool = True  # Enable autofocus if supported
    camera_buffer_size: int = 1  # Camera buffer size to reduce latency
    
    # Processing state
    last_snapshot_epoch: float = 0.0
    processing_enabled: bool = True  # Default fallback, overridden by YAML
    
    # Parking zones loaded from configuration file
    parking_zones: List[ParkingZone] = field(default_factory=list)
    
    # Logging settings - loaded from YAML
    log_level: str = "INFO"  # Default fallback, overridden by YAML
    debug: bool = False  # Default fallback, overridden by YAML
    
    # Internal field to specify custom config path
    _config_path: Optional[str] = field(default=None, init=False)
    
    def __post_init__(self):
        """Initialize configuration from YAML file"""
        # Load configuration from YAML file (overrides defaults)
        self._load_config_from_yaml()
        
        # Set fallback for video_source if still empty after YAML load
        if not self.video_source:
            # Default to camera device 0 for production, staging path only in specific environments
            self.video_source = "0"
        
        # Initialize last snapshot time to current time
        if self.last_snapshot_epoch == 0.0:
            self.last_snapshot_epoch = time.time()
    
    def _load_config_from_yaml(self):
        """Load configuration values and parking zones from config/mvp.yaml or custom path"""
        try:
            import yaml
            # Use custom config path if provided, otherwise use default
            if self._config_path:
                config_path = Path(self._config_path)
            else:
                config_path = Path(__file__).parent.parent / "config" / "mvp.yaml"
            
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config_data = yaml.safe_load(f)
                
                # Load configuration values (override defaults)
                config_mappings = {
                    'snapshot_interval': 'snapshot_interval',
                    'confidence_threshold': 'confidence_threshold', 
                    'model_path': 'model_path',
                    'api_port': 'api_port',
                    'api_host': 'api_host',
                    'video_source': 'video_source',
                    'camera_mirror': 'camera_mirror',
                    'camera_warmup_frames': 'camera_warmup_frames',
                    'camera_autofocus': 'camera_autofocus',
                    'camera_buffer_size': 'camera_buffer_size',
                    'processing_enabled': 'processing_enabled',
                    'log_level': 'log_level',
                    'debug': 'debug'
                }
                
                for yaml_key, attr_name in config_mappings.items():
                    if yaml_key in config_data:
                        setattr(self, attr_name, config_data[yaml_key])
                
                # Load parking zones
                zones_data = config_data.get('parking_zones', [])
                if zones_data:
                    for zone_data in zones_data:
                        zone = ParkingZone(
                            id=zone_data['id'],
                            space_id=zone_data.get('space_id', zone_data['id']),
                            name=zone_data['name'],
                            description=zone_data.get('description', f"Parking space {zone_data['name']}"),
                            coordinates=zone_data['coordinates'],
                            detection_difficulty=zone_data.get('detection_difficulty', 'normal')
                        )
                        self.parking_zones.append(zone)
                    logging.info(f"Loaded configuration with {len(self.parking_zones)} parking zones from {config_path}")
                else:
                    logging.warning(f"No parking zones found in {config_path}")
            else:
                logging.warning(f"Configuration file not found: {config_path}, using defaults")
        except Exception as e:
            logging.error(f"Failed to load configuration: {e}, using defaults")
    
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
    
    def get_total_zones(self) -> int:
        """Get total number of parking zones"""
        return len(self.parking_zones)
    
    def get_a_series_zones(self) -> List[ParkingZone]:
        """Get A-series zones (main row - easy detection)"""
        return [zone for zone in self.parking_zones if zone.name.startswith('A')]
    
    def get_b_series_zones(self) -> List[ParkingZone]:
        """Get B-series zones (back row - hard detection)"""
        return [zone for zone in self.parking_zones if zone.name.startswith('B')]
    
    def get_easy_zones_count(self) -> int:
        """Get count of easy detection zones"""
        return sum(1 for zone in self.parking_zones if zone.detection_difficulty == "easy")
    
    def get_hard_zones_count(self) -> int:
        """Get count of hard detection zones"""
        return sum(1 for zone in self.parking_zones if zone.detection_difficulty == "hard")

    def get_occupancy_summary(self) -> Dict[str, Any]:
        """Get overall occupancy summary"""
        total_zones = self.get_total_zones()
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
            "camera_mirror": self.camera_mirror,
            "last_snapshot_epoch": self.last_snapshot_epoch,
            "processing_enabled": self.processing_enabled,
            "total_zones": self.get_total_zones(),
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
        try:
            self._config = MVPConfig()
            
            # Set custom config path if provided
            if config_file:
                custom_config_path = Path(config_file)
                if custom_config_path.exists():
                    self._config._config_path = config_file
                    # Reload configuration from custom path
                    self._config._load_config_from_yaml()
                    logging.info(f"Loaded configuration from {config_file}")
                else:
                    logging.warning(f"Config file {config_file} not found, using defaults from mvp.yaml")
            else:
                logging.info("Using default configuration from config/mvp.yaml")
                
        except Exception as e:
            logging.error(f"Error loading config: {e}, using defaults")
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
                "camera_mirror": self.config.camera_mirror,
                "camera_warmup_frames": self.config.camera_warmup_frames,
                "camera_autofocus": self.config.camera_autofocus,
                "camera_buffer_size": self.config.camera_buffer_size,
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
            logging.error(f"Error saving config: {e}")
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
            logging.error(f"Error updating zones: {e}")
            return False
    
    def get_environment(self) -> str:
        """Get environment for compatibility"""
        return "mvp"


