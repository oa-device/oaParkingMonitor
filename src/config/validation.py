"""
Configuration Validation and Transformation Logic
Handles YAML loading, transformation, and validation for parking monitor configuration
"""

from typing import Dict, Any, Union
from pathlib import Path
import logging
import yaml

from .models import ParkingConfig


class ConfigValidator:
    """Handles configuration file validation and security checks"""
    
    @staticmethod
    def validate_file_security(config_path: Path) -> None:
        """Validate configuration file meets security requirements"""
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        if config_path.suffix.lower() not in ['.yaml', '.yml']:
            raise ValueError(f"Invalid config file extension: {config_path.suffix}")
        
        # Check file size for security
        if config_path.stat().st_size > 1024 * 1024:  # 1MB limit
            raise ValueError("Configuration file too large (max 1MB)")


class YamlTransformer:
    """Transforms flat YAML structure to nested Pydantic structure"""
    
    @staticmethod
    def transform_flat_yaml_to_nested(flat_data: dict) -> dict:
        """Transform flat YAML structure to nested Pydantic structure"""
        
        # Mapping from flat YAML keys to nested structure
        processing_fields = {
            'snapshot_interval': 'snapshot_interval',
            'confidence_threshold': 'confidence_threshold', 
            'model_path': 'model_path',
            'processing_enabled': 'processing_enabled'
        }
        
        camera_fields = {
            'camera_width': 'width',
            'camera_height': 'height', 
            'camera_fps': 'fps',
            'camera_exposure': 'exposure',
            'camera_gain': 'gain',
            'camera_brightness': 'brightness',
            'camera_contrast': 'contrast',
            'camera_saturation': 'saturation',
            'camera_sharpness': 'sharpness',
            'camera_white_balance': 'white_balance',
            'camera_autofocus': 'autofocus',
            'camera_warmup_frames': 'warmup_frames',
            'camera_buffer_size': 'buffer_size',
            'camera_mirror': 'mirror'
        }
        
        enhancement_fields = {
            'enable_auto_enhance': 'auto_enhance',
            'gamma_correction': 'gamma_correction',
            'histogram_equalization': 'histogram_equalization',
            'clahe_enabled': 'clahe_enabled',
            'clahe_clip_limit': 'clahe_clip_limit',
            'clahe_tile_grid_size': 'clahe_tile_grid_size'
        }
        
        api_fields = {
            'api_port': 'port',
            'api_host': 'host'
        }
        
        video_fields = {
            'video_source': 'source'
        }
        
        # Build nested structure
        nested = {}
        
        # Process each category
        processing = {}
        for yaml_key, nested_key in processing_fields.items():
            if yaml_key in flat_data:
                processing[nested_key] = flat_data[yaml_key]
        if processing:
            nested['processing'] = processing
        
        camera = {}
        for yaml_key, nested_key in camera_fields.items():
            if yaml_key in flat_data:
                camera[nested_key] = flat_data[yaml_key]
        if camera:
            nested['camera'] = camera
            
        enhancement = {}
        for yaml_key, nested_key in enhancement_fields.items():
            if yaml_key in flat_data:
                enhancement[nested_key] = flat_data[yaml_key]
        if enhancement:
            nested['enhancement'] = enhancement
        
        api = {}
        for yaml_key, nested_key in api_fields.items():
            if yaml_key in flat_data:
                api[nested_key] = flat_data[yaml_key]
        if api:
            nested['api'] = api
            
        video = {}
        for yaml_key, nested_key in video_fields.items():
            if yaml_key in flat_data:
                video[nested_key] = flat_data[yaml_key]
        if video:
            nested['video'] = video
        
        # Copy direct fields
        direct_fields = ['parking_zones', 'log_level', 'debug']
        for field in direct_fields:
            if field in flat_data:
                nested[field] = flat_data[field]
        
        return nested


class ConfigLoader:
    """Handles configuration loading from YAML files"""
    
    @staticmethod
    def load_from_yaml_file(config_path: Union[str, Path]) -> ParkingConfig:
        """
        Load configuration from YAML file with security validation
        
        This method provides:
        - Automatic YAML parsing with type conversion
        - Comprehensive validation 
        - Security checks
        - Error handling with helpful messages
        """
        config_path = Path(config_path)
        
        # Security validation
        ConfigValidator.validate_file_security(config_path)
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)
            
            if not isinstance(yaml_data, dict):
                raise ValueError("Configuration file must contain a YAML dictionary")
            
            # Transform and create configuration
            nested_data = YamlTransformer.transform_flat_yaml_to_nested(yaml_data)
            config = ParkingConfig.model_validate(nested_data)
            config.config_loaded_from = str(config_path)
            
            logging.info(f"Loaded configuration from {config_path} with {len(config.parking_zones)} zones")
            return config
            
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML syntax in {config_path}: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load configuration from {config_path}: {e}")
    
    @staticmethod
    def load_from_yaml_data(yaml_data: dict) -> ParkingConfig:
        """
        Create configuration from YAML dictionary with flat structure mapping
        Maps flat YAML keys to nested Pydantic structure automatically
        """
        # Transform flat YAML structure to nested structure
        nested_data = YamlTransformer.transform_flat_yaml_to_nested(yaml_data)
        return ParkingConfig.model_validate(nested_data)


class ConfigSaver:
    """Handles configuration saving to YAML files"""
    
    @staticmethod
    def save_to_yaml_file(config: ParkingConfig, config_path: Union[str, Path]) -> None:
        """Save configuration to YAML file"""
        config_path = Path(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict, excluding runtime fields
        config_dict = config.dict(exclude={'security', 'last_snapshot_epoch', 'config_loaded_from'})
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2, sort_keys=False)
        
        logging.info(f"Saved configuration to {config_path}")