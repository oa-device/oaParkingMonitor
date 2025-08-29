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
    """Manages parking monitor configuration with environment-based loading"""
    
    def __init__(self, config_dir: Optional[Path] = None, environment: Optional[str] = None):
        if config_dir is None:
            # Use project-relative config directory
            project_root = Path(__file__).parent.parent
            config_dir = project_root / "config"
        
        self.config_dir = config_dir
        self.environment = environment or self._detect_environment()
        
        # Determine config file based on environment
        self.config_file = self._get_config_file()
        self._config: Optional[Dict[str, Any]] = None
        self._parsed_config: Optional['ParkingConfig'] = None
    
    def _detect_environment(self) -> str:
        """Detect environment from environment variables or default to staging"""
        import os
        
        # Check environment variable first
        env = os.getenv('PARKING_MONITOR_ENV', os.getenv('ENVIRONMENT', ''))
        
        if env.lower() in ['production', 'prod']:
            return 'production'
        elif env.lower() in ['preprod', 'pre-prod', 'preproduction']:
            return 'preprod'
        elif env.lower() in ['staging', 'stage', 'dev', 'development']:
            return 'staging'
        
        # Default to staging for development
        return 'staging'
    
    def _get_config_file(self) -> Path:
        """Get config file path for current environment"""
        return self.config_dir / f"{self.environment}.yaml"
    
    def _load_yaml_with_inheritance(self, config_path: Path) -> Dict[str, Any]:
        """Load YAML file with extends support"""
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Handle inheritance via 'extends' key
        if 'extends' in config_data:
            parent_file = config_data.pop('extends')
            parent_path = self.config_dir / parent_file
            
            # Load parent configuration
            parent_config = self._load_yaml_with_inheritance(parent_path)
            
            # Deep merge parent and current config
            merged_config = self._deep_merge(parent_config, config_data)
            return merged_config
        
        return config_data
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries, with override taking precedence"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _inject_environment_variables(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Inject environment variables into configuration"""
        import os
        
        # Environment variable mappings
        env_mappings = {
            'PARKING_MONITOR_PORT': ['service', 'port'],
            'PARKING_MONITOR_LOG_LEVEL': ['service', 'log_level'],
            'PARKING_MONITOR_MODEL_PATH': ['detection', 'model_path'],
            'PARKING_MONITOR_CONFIDENCE': ['detection', 'confidence_threshold'],
            'PARKING_MONITOR_CAMERA_SOURCE': ['camera', 'source'],
            'PARKING_MONITOR_DEBUG': ['development', 'debug_api_enabled'],
            'TAILSCALE_SUBNET': ['api', 'cors_origins'],
        }
        
        result = config.copy()
        
        for env_var, config_path in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                # Navigate to the nested config location
                current = result
                for key in config_path[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                
                # Set the value with appropriate type conversion
                final_key = config_path[-1]
                if final_key == 'port':
                    current[final_key] = int(env_value)
                elif final_key == 'confidence_threshold':
                    current[final_key] = float(env_value)
                elif final_key in ['debug_api_enabled']:
                    current[final_key] = env_value.lower() in ['true', '1', 'yes', 'on']
                elif final_key == 'cors_origins' and env_var == 'TAILSCALE_SUBNET':
                    # Special handling for Tailscale subnet
                    subnet_base = env_value.split('/')[0]
                    cors_entry = f"http://{subnet_base}:*"
                    if cors_entry not in current.get(final_key, []):
                        current.setdefault(final_key, []).append(cors_entry)
                else:
                    current[final_key] = env_value
        
        return result
    
    @property
    def config(self) -> 'ParkingConfig':
        """Get current configuration, loading if necessary"""
        if self._parsed_config is None:
            self.load_config()
        return self._parsed_config
    
    def load_config(self) -> 'ParkingConfig':
        """Load configuration from environment-specific file"""
        try:
            # Load YAML configuration with inheritance
            config_data = self._load_yaml_with_inheritance(self.config_file)
            
            # Inject environment variables
            config_data = self._inject_environment_variables(config_data)
            
            # Store raw config for debugging
            self._config = config_data
            
            # Convert to legacy ParkingConfig format for backward compatibility
            legacy_config = self._convert_to_legacy_format(config_data)
            self._parsed_config = ParkingConfig(**legacy_config)
            
        except Exception as e:
            print(f"Warning: Failed to load config from {self.config_file}: {e}")
            print("Falling back to default configuration")
            # Fallback to default configuration
            self._parsed_config = ParkingConfig.default()
            self._config = {}
        
        return self._parsed_config
    
    def _convert_to_legacy_format(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert new YAML format to legacy ParkingConfig format"""
        # Map new format to legacy format
        legacy_config = {
            'api_port': config_data.get('service', {}).get('port', 9091),
            'debug': config_data.get('development', {}).get('debug_api_enabled', False),
        }
        
        # Detection configuration
        detection_config = config_data.get('detection', {})
        legacy_config['detection'] = {
            'confidence_threshold': detection_config.get('confidence_threshold', 0.5),
            'model_path': detection_config.get('model_path', 'models/yolo11m.pt'),
            'processing_fps': detection_config.get('target_fps', 10),
            'vehicle_classes': ["car", "truck", "bus", "motorcycle"]  # Default classes
        }
        
        # Video configuration
        camera_config = config_data.get('camera', {})
        legacy_config['video'] = {
            'source_path': str(camera_config.get('source', 0)),
            'rotation_enabled': camera_config.get('rotation', {}).get('enabled', True),
            'rotation_videos': camera_config.get('rotation', {}).get('videos', ["current.mp4"]),
            'rotation_interval': camera_config.get('rotation', {}).get('interval_seconds', 300)
        }
        
        # Parking spaces configuration
        zones = config_data.get('parking_zones', {}).get('zones', [])
        spaces = []
        for i, zone in enumerate(zones):
            if 'coordinates' in zone:
                coords = zone['coordinates']
                if len(coords) >= 2:
                    x = coords[0][0] if len(coords[0]) >= 2 else 100
                    y = coords[0][1] if len(coords[0]) >= 2 else 200
                    width = coords[1][0] - x if len(coords) >= 2 else 180
                    height = coords[2][1] - y if len(coords) >= 3 else 120
                    
                    spaces.append({
                        'space_id': i,
                        'x': x,
                        'y': y,
                        'width': width,
                        'height': height,
                        'label': zone.get('name', f'Space {i+1}')
                    })
        
        # If no zones, create default spaces
        if not spaces:
            spaces = [
                {
                    'space_id': i,
                    'x': 100 + (i * 200),
                    'y': 200,
                    'width': 180,
                    'height': 120,
                    'label': f'Space {i+1}'
                }
                for i in range(4)
            ]
        
        legacy_config['spaces'] = spaces
        
        return legacy_config
    
    def get_raw_config(self) -> Dict[str, Any]:
        """Get raw configuration data (new format)"""
        if self._config is None:
            self.load_config()
        return self._config
    
    def get_environment(self) -> str:
        """Get current environment"""
        return self.environment
    
    def save_config(self) -> None:
        """Save current configuration to file (legacy compatibility)"""
        if self._parsed_config:
            self._parsed_config.save_to_file(self.config_file)
    
    def update_spaces(self, spaces: List[Dict[str, Any]]) -> None:
        """Update parking space configuration (legacy compatibility)"""
        new_spaces = [ParkingSpaceConfig(**space) for space in spaces]
        self.config.spaces = new_spaces
        self.save_config()
    
    def get_spaces(self) -> List[ParkingSpaceConfig]:
        """Get parking space configurations (legacy compatibility)"""
        return self.config.spaces
    
    def reset_to_default(self) -> None:
        """Reset configuration to default values (legacy compatibility)"""
        self._parsed_config = ParkingConfig.default()
        self._config = {}
        self.save_config()