"""
Configuration Manager
Simplified configuration manager using the new Pydantic system
"""

from typing import Optional
from pathlib import Path
import logging

from .models import ParkingConfig
from .validation import ConfigLoader, ConfigSaver
from .preset_loader import PresetLoader


class ConfigManager:
    """
    Simplified configuration manager using the new Pydantic system
    
    Provides:
    - Automatic loading with fallback to defaults
    - Thread-safe configuration access
    - Configuration validation and caching
    """
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file
        self._config: Optional[ParkingConfig] = None
    
    @property
    def config(self) -> ParkingConfig:
        """Get current configuration, loading if needed"""
        if self._config is None:
            self.load_config(self.config_file)
        return self._config
    
    def load_config(self, config_file: Optional[str] = None) -> ParkingConfig:
        """Load configuration from file or use defaults"""
        try:
            if config_file and Path(config_file).exists():
                self._config = ConfigLoader.load_from_yaml_file(config_file)
                logging.info(f"Loaded configuration from {config_file}")
            else:
                # Try default config path
                default_path = Path(__file__).parent.parent.parent / "config" / "mvp.yaml"
                if default_path.exists():
                    self._config = ConfigLoader.load_from_yaml_file(default_path)
                    logging.info(f"Loaded default configuration from {default_path}")
                else:
                    # Use defaults with warning
                    self._config = ParkingConfig()
                    logging.warning("No configuration file found, using defaults")
            
            # Apply preset if specified in configuration
            if self._config.camera.active_preset:
                preset_name = self._config.camera.active_preset
                if PresetLoader.apply_preset_to_config(self._config, preset_name):
                    logging.info(f"Applied camera preset: {preset_name}")
                else:
                    logging.warning(f"Failed to apply camera preset: {preset_name}")
            
            return self._config
            
        except Exception as e:
            logging.error(f"Failed to load configuration: {e}")
            logging.warning("Using default configuration")
            self._config = ParkingConfig()
            return self._config
    
    def save_config(self, config_file: Optional[str] = None) -> bool:
        """Save current configuration to file"""
        if not config_file:
            config_file = self.config_file
        
        if not config_file:
            logging.error("No config file specified for saving")
            return False
        
        try:
            ConfigSaver.save_to_yaml_file(self.config, config_file)
            return True
        except Exception as e:
            logging.error(f"Failed to save configuration: {e}")
            return False
    
    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        self._config = ParkingConfig()
        logging.info("Configuration reset to defaults")
    
    def get_environment(self) -> str:
        """Get environment identifier"""
        return "mvp"


