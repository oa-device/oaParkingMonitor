"""
Camera Controller Service
Handles camera settings management and presets
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from ..config import ParkingConfig
from ..models.shared import CameraSettings, ImageEnhancement
from ..models import CameraPresetInfo
from ..api.models import CameraSettingsRequest, CameraOperationResponse
from .preset_loader import PresetLoader
from .settings_applicator import SettingsApplicator


class CameraController:
    """
    Camera settings controller with preset management
    
    Responsibilities:
    - Camera settings validation and application
    - Preset management for different lighting conditions
    - Settings conversion between API models and config models
    - Safe defaults and error handling
    """
    
    def __init__(self, config: ParkingConfig, detector):
        self.config = config
        self.detector = detector
        self.logger = logging.getLogger(__name__)
        self.preset_loader = PresetLoader()
        self.settings_applicator = SettingsApplicator()
    
    def get_current_settings(self) -> Dict[str, Any]:
        """Get current camera settings formatted for API response"""
        
        return {
            "resolution": {
                "width": self.config.camera.width,
                "height": self.config.camera.height,
                "fps": self.config.camera.fps
            },
            "exposure": {
                "mode": "manual" if self.config.camera.exposure >= 0 else "auto",
                "value": self.config.camera.exposure
            },
            "image_quality": {
                "gain": self.config.camera.gain,
                "brightness": self.config.camera.brightness,
                "contrast": self.config.camera.contrast,
                "saturation": self.config.camera.saturation,
                "sharpness": self.config.camera.sharpness
            },
            "focus": {
                "autofocus": self.config.camera.autofocus,
                "white_balance": "auto" if self.config.camera.white_balance < 0 else "manual",
                "white_balance_value": self.config.camera.white_balance
            },
            "enhancement": {
                "auto_enhance": self.config.enhancement.auto_enhance,
                "gamma_correction": self.config.enhancement.gamma_correction,
                "histogram_equalization": self.config.enhancement.histogram_equalization,
                "clahe_enabled": self.config.enhancement.clahe_enabled,
                "clahe_clip_limit": self.config.enhancement.clahe_clip_limit,
                "clahe_tile_grid_size": self.config.enhancement.clahe_tile_grid_size
            },
            "misc": {
                "mirror": self.config.camera.mirror,
                "warmup_frames": self.config.camera.warmup_frames,
                "buffer_size": self.config.camera.buffer_size
            }
        }
    
    async def update_settings(self, settings: CameraSettingsRequest) -> CameraOperationResponse:
        """Update camera settings with validation using generic applicator"""
        try:
            # Convert request to dictionary excluding unset fields
            settings_data = settings.model_dump(exclude_unset=True)
            
            # Validate settings structure
            if not self.settings_applicator.validate_settings_structure(settings_data):
                return CameraOperationResponse(
                    success=False,
                    error="Invalid settings structure",
                    message="Settings validation failed"
                )
            
            # Apply settings using generic applicator
            changes_applied = self.settings_applicator.apply_nested_settings(
                target_config=self.config,
                settings_data=settings_data
            )
            
            if not changes_applied:
                return CameraOperationResponse(
                    success=True,
                    message="No changes were needed - settings already at requested values",
                    applied_at=datetime.now().isoformat()
                )
            
            # Apply settings to camera device if needed
            if hasattr(self.detector, 'camera_manager') and hasattr(self.detector.camera_manager, 'cap'):
                await self._reinitialize_camera()
            
            self.logger.info("Camera settings updated successfully using generic applicator")
            return CameraOperationResponse(
                success=True,
                message="Camera settings updated successfully",
                applied_at=datetime.now().isoformat()
            )
            
        except Exception as e:
            self.logger.error(f"Failed to update camera settings: {e}")
            return CameraOperationResponse(
                success=False,
                error=str(e),
                message="Failed to update camera settings"
            )
    
    async def reset_to_defaults(self) -> CameraOperationResponse:
        """Reset camera settings to optimal defaults"""
        try:
            # Reset camera settings to defaults
            self.config.camera = CameraSettings()
            self.config.enhancement = ImageEnhancement()
            
            # Apply settings if camera device
            if hasattr(self.detector, 'camera_manager') and hasattr(self.detector.camera_manager, 'cap'):
                await self._reinitialize_camera()
            
            self.logger.info("Camera settings reset to defaults")
            return CameraOperationResponse(
                success=True,
                message="Camera settings reset to defaults",
                applied_at=datetime.now().isoformat()
            )
            
        except Exception as e:
            self.logger.error(f"Failed to reset camera settings: {e}")
            return CameraOperationResponse(
                success=False,
                error=str(e),
                message="Failed to reset camera settings"
            )
    
    def get_available_presets(self) -> Dict[str, CameraPresetInfo]:
        """Get available camera presets from YAML configuration"""
        return self.preset_loader.load_presets()
    
    async def apply_preset(self, preset_name: str) -> CameraOperationResponse:
        """Apply a camera preset"""
        try:
            presets = self.get_available_presets()
            
            if preset_name not in presets:
                return CameraOperationResponse(
                    success=False,
                    error=f"Preset '{preset_name}' not found. Available: {list(presets.keys())}",
                    message=f"Failed to apply preset: {preset_name}"
                )
            
            # Convert preset settings to CameraSettingsRequest
            preset_settings = presets[preset_name].settings
            settings_request = CameraSettingsRequest.model_validate(preset_settings)
            
            # Apply the settings
            result = await self.update_settings(settings_request)
            
            if result.success:
                return CameraOperationResponse(
                    success=True,
                    message=f"Applied preset: {presets[preset_name].name}",
                    preset=preset_name,
                    applied_at=datetime.now().isoformat()
                )
            else:
                return result
                
        except Exception as e:
            self.logger.error(f"Failed to apply preset {preset_name}: {e}")
            return CameraOperationResponse(
                success=False,
                error=str(e),
                message=f"Failed to apply preset: {preset_name}"
            )
    
    async def _reinitialize_camera(self):
        """Reinitialize camera with updated settings"""
        if hasattr(self.detector, 'camera_manager') and hasattr(self.detector.camera_manager, 'cap'):
            # Stop detector temporarily
            was_running = self.detector.running
            if was_running:
                self.detector.running = False
                await asyncio.sleep(0.5)  # Allow current processing to complete

            # Reinitialize camera with new settings
            if hasattr(self.detector.camera_manager, 'initialize'):
                await self.detector.camera_manager.initialize()

            # Restart detector if it was running
            if was_running:
                self.detector.running = True