"""
Camera Controller Service
Handles camera settings management and presets
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from ..config import ParkingConfig as MVPConfig, CameraSettings, ImageEnhancement
from ..api.models import (
    CameraSettingsRequest, 
    CameraOperationResponse,
    CameraPresetInfo
)


class CameraController:
    """
    Camera settings controller with preset management
    
    Responsibilities:
    - Camera settings validation and application
    - Preset management for different lighting conditions
    - Settings conversion between API models and config models
    - Safe defaults and error handling
    """
    
    def __init__(self, config: MVPConfig, detector):
        self.config = config
        self.detector = detector
        self.logger = logging.getLogger(__name__)
    
    def get_current_settings(self) -> Dict[str, Any]:
        """Get current camera settings formatted for API response"""
        config_data = self.config.to_dict()
        
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
        """Update camera settings with validation"""
        try:
            settings_data = settings.model_dump(exclude_unset=True)
            
            # Update camera settings
            if "resolution" in settings_data:
                res = settings_data["resolution"]
                if "width" in res:
                    self.config.camera.width = int(res["width"])
                if "height" in res:
                    self.config.camera.height = int(res["height"])
                if "fps" in res:
                    self.config.camera.fps = int(res["fps"])
            
            # Update exposure settings
            if "exposure" in settings_data:
                exp = settings_data["exposure"]
                if "value" in exp:
                    self.config.camera.exposure = float(exp["value"])
            
            # Update image quality settings
            if "image_quality" in settings_data:
                iq = settings_data["image_quality"]
                if "gain" in iq:
                    self.config.camera.gain = float(iq["gain"])
                if "brightness" in iq:
                    self.config.camera.brightness = float(iq["brightness"])
                if "contrast" in iq:
                    self.config.camera.contrast = float(iq["contrast"])
                if "saturation" in iq:
                    self.config.camera.saturation = float(iq["saturation"])
                if "sharpness" in iq:
                    self.config.camera.sharpness = float(iq["sharpness"])
            
            # Update focus settings
            if "focus" in settings_data:
                focus = settings_data["focus"]
                if "autofocus" in focus:
                    self.config.camera.autofocus = bool(focus["autofocus"])
                if "white_balance_value" in focus:
                    self.config.camera.white_balance = float(focus["white_balance_value"])
            
            # Update enhancement settings
            if "enhancement" in settings_data:
                enh = settings_data["enhancement"]
                if "auto_enhance" in enh:
                    self.config.enhancement.auto_enhance = bool(enh["auto_enhance"])
                if "gamma_correction" in enh:
                    self.config.enhancement.gamma_correction = float(enh["gamma_correction"])
                if "histogram_equalization" in enh:
                    self.config.enhancement.histogram_equalization = bool(enh["histogram_equalization"])
                if "clahe_enabled" in enh:
                    self.config.enhancement.clahe_enabled = bool(enh["clahe_enabled"])
                if "clahe_clip_limit" in enh:
                    self.config.enhancement.clahe_clip_limit = float(enh["clahe_clip_limit"])
                if "clahe_tile_grid_size" in enh:
                    self.config.enhancement.clahe_tile_grid_size = int(enh["clahe_tile_grid_size"])
            
            # Update misc settings
            if "misc" in settings_data:
                misc = settings_data["misc"]
                if "mirror" in misc:
                    self.config.camera.mirror = bool(misc["mirror"])
                if "warmup_frames" in misc:
                    self.config.camera.warmup_frames = int(misc["warmup_frames"])
                if "buffer_size" in misc:
                    self.config.camera.buffer_size = int(misc["buffer_size"])
            
            # Apply settings if camera device
            if self.detector.is_camera_device:
                await self._reinitialize_camera()
            
            self.logger.info("Camera settings updated successfully")
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
            if self.detector.is_camera_device:
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
        """Get available camera presets optimized for different conditions"""
        return {
            "outdoor_bright": CameraPresetInfo(
                name="Outdoor Bright",
                description="Optimized for bright outdoor parking lots",
                settings={
                    "exposure": {"value": 0.2},
                    "image_quality": {
                        "brightness": 0.3,
                        "contrast": 0.7,
                        "saturation": 0.6,
                        "gain": 0.2
                    },
                    "enhancement": {
                        "gamma_correction": 0.7,
                        "clahe_enabled": True,
                        "clahe_clip_limit": 2.5
                    }
                }
            ),
            "outdoor_normal": CameraPresetInfo(
                name="Outdoor Normal",
                description="Balanced settings for normal daylight",
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
            ),
            "indoor_low_light": CameraPresetInfo(
                name="Indoor Low Light",
                description="Enhanced for indoor/garage environments",
                settings={
                    "exposure": {"value": 0.4},
                    "image_quality": {
                        "brightness": 0.6,
                        "contrast": 0.8,
                        "saturation": 0.4,
                        "gain": 0.5
                    },
                    "enhancement": {
                        "gamma_correction": 1.2,
                        "clahe_enabled": True,
                        "clahe_clip_limit": 4.0
                    }
                }
            ),
            "high_contrast": CameraPresetInfo(
                name="High Contrast",
                description="Maximum contrast for difficult conditions",
                settings={
                    "exposure": {"value": 0.3},
                    "image_quality": {
                        "brightness": 0.4,
                        "contrast": 0.9,
                        "saturation": 0.6,
                        "sharpness": 0.8,
                        "gain": 0.4
                    },
                    "enhancement": {
                        "gamma_correction": 0.9,
                        "clahe_enabled": True,
                        "clahe_clip_limit": 5.0,
                        "histogram_equalization": True
                    }
                }
            )
        }
    
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
        if self.detector.is_camera_device:
            # Stop detector temporarily
            was_running = self.detector.running
            if was_running:
                self.detector.running = False
                await asyncio.sleep(0.5)  # Allow current processing to complete
            
            # Reinitialize camera with new settings
            self.detector.camera_initialized = False
            await self.detector._initialize_camera()
            
            # Restart detector if it was running
            if was_running:
                self.detector.running = True