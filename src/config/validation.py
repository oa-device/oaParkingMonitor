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


class ConfigLoader:
    """Handles configuration loading from YAML files using native Pydantic validation"""
    
    @staticmethod
    def load_from_yaml_file(config_path: Union[str, Path]) -> ParkingConfig:
        """
        Load configuration from YAML file with security validation
        
        This method provides:
        - Direct YAML to Pydantic model validation
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
            
            # Use Pydantic native validation - no transformation needed
            config = ParkingConfig.model_validate(yaml_data)
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
        Create configuration from YAML dictionary using native Pydantic validation
        """
        return ParkingConfig.model_validate(yaml_data)


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