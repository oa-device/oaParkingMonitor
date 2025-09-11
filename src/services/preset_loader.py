"""
Camera Preset Loader Service
Loads and validates camera presets from external YAML configuration
"""

import logging
import yaml
from pathlib import Path
from typing import Dict
from pydantic import ValidationError

from ..models.shared import CameraPresetInfo


class PresetLoader:
    """Loads and validates camera presets from YAML configuration"""
    
    def __init__(self, presets_file: str = "config/presets.yaml"):
        self.presets_file = Path(presets_file)
        self.logger = logging.getLogger(__name__)
        self._presets_cache: Dict[str, CameraPresetInfo] = {}
    
    def load_presets(self) -> Dict[str, CameraPresetInfo]:
        """
        Load camera presets from YAML file with validation
        Returns cached presets if file hasn't changed
        """
        try:
            if not self.presets_file.exists():
                self.logger.warning(f"Presets file not found: {self.presets_file}")
                return self._get_default_presets()
            
            with open(self.presets_file, 'r', encoding='utf-8') as f:
                presets_data = yaml.safe_load(f)
            
            if not isinstance(presets_data, dict):
                raise ValueError("Presets file must contain a YAML dictionary")
            
            # Convert YAML data to CameraPresetInfo objects
            validated_presets = {}
            for preset_key, preset_data in presets_data.items():
                try:
                    preset_info = CameraPresetInfo(
                        name=preset_data['name'],
                        description=preset_data['description'],
                        settings=preset_data['settings']
                    )
                    validated_presets[preset_key] = preset_info
                    
                except (KeyError, ValidationError) as e:
                    self.logger.error(f"Invalid preset '{preset_key}': {e}")
                    continue
            
            if not validated_presets:
                self.logger.warning("No valid presets found, using defaults")
                return self._get_default_presets()
            
            self._presets_cache = validated_presets
            self.logger.info(f"Loaded {len(validated_presets)} camera presets from {self.presets_file}")
            return validated_presets
            
        except yaml.YAMLError as e:
            self.logger.error(f"YAML parsing error in {self.presets_file}: {e}")
            return self._get_default_presets()
        except Exception as e:
            self.logger.error(f"Failed to load presets from {self.presets_file}: {e}")
            return self._get_default_presets()
    
    def _get_default_presets(self) -> Dict[str, CameraPresetInfo]:
        """Fallback default presets for outdoor airport parking environment"""
        return {
            "outdoor_normal": CameraPresetInfo(
                name="Normal Daylight",
                description="Default settings for outdoor airport parking",
                settings={
                    "exposure": {"value": 0.25},
                    "image_quality": {
                        "brightness": 0.4,
                        "contrast": 0.6,
                        "saturation": 0.5,
                        "gain": 0.3
                    },
                    "enhancement": {
                        "gamma_correction": 0.8,
                        "clahe_enabled": True,
                        "clahe_clip_limit": 3.0
                    }
                }
            )
        }
    
    def get_preset(self, preset_name: str) -> CameraPresetInfo:
        """Get a specific preset by name"""
        presets = self.load_presets()
        if preset_name not in presets:
            raise ValueError(f"Preset '{preset_name}' not found. Available: {list(presets.keys())}")
        return presets[preset_name]
    
    def reload_presets(self) -> Dict[str, CameraPresetInfo]:
        """Force reload presets from file (clears cache)"""
        self._presets_cache = {}
        return self.load_presets()