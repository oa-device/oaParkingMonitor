"""
Simple configuration management for parking monitor
"""

import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class ParkingSpaceConfig:
    """Configuration for a single parking space"""
    space_id: int
    x: int
    y: int
    width: int
    height: int
    label: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DetectionConfig:
    """Detection configuration settings"""
    confidence_threshold: float = 0.5
    model_path: str = "models/yolo11m.pt"
    vehicle_classes: List[str] = None
    processing_fps: int = 10
    
    def __post_init__(self):
        if self.vehicle_classes is None:
            self.vehicle_classes = ["car", "truck", "bus", "motorcycle"]


@dataclass
class VideoConfig:
    """Video source configuration"""
    source_path: str = ""
    rotation_enabled: bool = True
    rotation_videos: List[str] = None
    rotation_interval: int = 300  # seconds
    
    def __post_init__(self):
        if not self.source_path:
            # Default staging video path
            home = Path.home()
            self.source_path = str(home / "orangead" / "staging-video-feed" / "videos" / "current.mp4")
        
        if self.rotation_videos is None:
            self.rotation_videos = ["current.mp4"]


@dataclass
class ParkingConfig:
    """Main configuration for parking monitor"""
    detection: DetectionConfig
    video: VideoConfig
    spaces: List[ParkingSpaceConfig]
    api_port: int = 9091
    debug: bool = False
    
    def __post_init__(self):
        # Ensure we have detection and video configs
        if not isinstance(self.detection, DetectionConfig):
            self.detection = DetectionConfig(**self.detection) if isinstance(self.detection, dict) else DetectionConfig()
        
        if not isinstance(self.video, VideoConfig):
            self.video = VideoConfig(**self.video) if isinstance(self.video, dict) else VideoConfig()
        
        # Convert space dictionaries to ParkingSpaceConfig objects
        processed_spaces = []
        for space in self.spaces:
            if isinstance(space, dict):
                processed_spaces.append(ParkingSpaceConfig(**space))
            elif isinstance(space, ParkingSpaceConfig):
                processed_spaces.append(space)
        self.spaces = processed_spaces
    
    @classmethod
    def load_from_file(cls, config_path: Path) -> 'ParkingConfig':
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            
            return cls(**config_data)
            
        except Exception as e:
            # Return default configuration if loading fails
            return cls.default()
    
    @classmethod
    def default(cls) -> 'ParkingConfig':
        """Create default configuration"""
        # Default 4 parking spaces layout
        default_spaces = [
            ParkingSpaceConfig(
                space_id=i,
                x=100 + (i * 200),
                y=200,
                width=180,
                height=120,
                label=f"Space {i+1}"
            )
            for i in range(4)
        ]
        
        return cls(
            detection=DetectionConfig(),
            video=VideoConfig(),
            spaces=default_spaces
        )
    
    def save_to_file(self, config_path: Path) -> None:
        """Save configuration to YAML file"""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dictionary for YAML serialization
        config_dict = {
            "detection": asdict(self.detection),
            "video": asdict(self.video),
            "spaces": [space.to_dict() for space in self.spaces],
            "api_port": self.api_port,
            "debug": self.debug
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)


class ConfigManager:
    """Manages parking monitor configuration"""
    
    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            config_dir = Path.home() / "orangead" / "parking-monitor" / "config"
        
        self.config_dir = config_dir
        self.config_file = config_dir / "parking.yaml"
        self._config: Optional[ParkingConfig] = None
    
    @property
    def config(self) -> ParkingConfig:
        """Get current configuration, loading if necessary"""
        if self._config is None:
            self.load_config()
        return self._config
    
    def load_config(self) -> ParkingConfig:
        """Load configuration from file or create default"""
        if self.config_file.exists():
            self._config = ParkingConfig.load_from_file(self.config_file)
        else:
            # Create default configuration
            self._config = ParkingConfig.default()
            self.save_config()
        
        return self._config
    
    def save_config(self) -> None:
        """Save current configuration to file"""
        if self._config:
            self._config.save_to_file(self.config_file)
    
    def update_spaces(self, spaces: List[Dict[str, Any]]) -> None:
        """Update parking space configuration"""
        new_spaces = [ParkingSpaceConfig(**space) for space in spaces]
        self.config.spaces = new_spaces
        self.save_config()
    
    def get_spaces(self) -> List[ParkingSpaceConfig]:
        """Get parking space configurations"""
        return self.config.spaces
    
    def reset_to_default(self) -> None:
        """Reset configuration to default values"""
        self._config = ParkingConfig.default()
        self.save_config()