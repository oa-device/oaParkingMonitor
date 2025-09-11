"""
Preset Loading System
Handles loading and applying camera presets from presets.yaml
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class PresetLoader:
    """Handles loading and applying camera presets"""
    
    @staticmethod
    def load_presets(presets_file: Optional[str] = None) -> Dict[str, Any]:
        """Load presets from YAML file"""
        
        if not presets_file:
            # Default presets path
            presets_file = Path(__file__).parent.parent.parent / "config" / "presets.yaml"
        else:
            presets_file = Path(presets_file)
        
        try:
            if not presets_file.exists():
                logger.warning(f"Presets file not found: {presets_file}")
                return {}
            
            with open(presets_file, 'r') as f:
                presets = yaml.safe_load(f)
            
            if not isinstance(presets, dict):
                logger.error("Presets file must contain a dictionary")
                return {}
            
            logger.info(f"Loaded {len(presets)} presets from {presets_file}")
            return presets
            
        except Exception as e:
            logger.error(f"Failed to load presets from {presets_file}: {e}")
            return {}
    
    @staticmethod
    def get_preset_settings(preset_name: str, presets: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Get settings for a specific preset"""
        
        if presets is None:
            presets = PresetLoader.load_presets()
        
        if preset_name not in presets:
            logger.warning(f"Preset '{preset_name}' not found")
            return None
        
        preset = presets[preset_name]
        if not isinstance(preset, dict) or 'settings' not in preset:
            logger.error(f"Invalid preset format for '{preset_name}'")
            return None
        
        return preset['settings']
    
    @staticmethod
    def apply_preset_to_config(config, preset_name: str) -> bool:
        """Apply preset settings to configuration object"""
        
        preset_settings = PresetLoader.get_preset_settings(preset_name)
        if not preset_settings:
            return False
        
        try:
            # Apply exposure and image quality settings to camera
            if 'exposure' in preset_settings and 'value' in preset_settings['exposure']:
                config.camera.exposure = preset_settings['exposure']['value']
            
            if 'image_quality' in preset_settings:
                quality = preset_settings['image_quality']
                if 'brightness' in quality:
                    config.camera.brightness = quality['brightness']
                if 'contrast' in quality:
                    config.camera.contrast = quality['contrast']
                if 'saturation' in quality:
                    config.camera.saturation = quality['saturation']
                if 'gain' in quality:
                    config.camera.gain = quality['gain']
            
            # Apply enhancement settings
            if 'enhancement' in preset_settings:
                enhancement = preset_settings['enhancement']
                if 'gamma_correction' in enhancement:
                    config.enhancement.gamma_correction = enhancement['gamma_correction']
                if 'clahe_enabled' in enhancement:
                    config.enhancement.clahe_enabled = enhancement['clahe_enabled']
                if 'clahe_clip_limit' in enhancement:
                    config.enhancement.clahe_clip_limit = enhancement['clahe_clip_limit']
            
            logger.info(f"Applied preset '{preset_name}' to configuration")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply preset '{preset_name}': {e}")
            return False
    
    @staticmethod
    def list_available_presets(presets_file: Optional[str] = None) -> Dict[str, str]:
        """List available presets with their descriptions"""
        
        presets = PresetLoader.load_presets(presets_file)
        result = {}
        
        for name, preset in presets.items():
            if isinstance(preset, dict) and 'description' in preset:
                result[name] = preset['description']
            else:
                result[name] = "No description available"
        
        return result