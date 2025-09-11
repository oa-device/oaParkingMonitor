"""
Dynamic Model Factory
Creates API request models from base configuration models
Eliminates duplication and ensures automatic synchronization
"""

from typing import Dict, Type, Optional, Any
from pydantic import BaseModel, Field, create_model
from .shared import CameraSettings, ImageEnhancement


class ModelFactory:
    """Factory for creating dynamic models from base configuration models"""
    
    @staticmethod
    def create_camera_request_models() -> Dict[str, Type[BaseModel]]:
        """Create camera request models dynamically from CameraSettings"""
        
        # Get field definitions from CameraSettings
        camera_fields = CameraSettings.model_fields
        enhancement_fields = ImageEnhancement.model_fields
        
        # Create resolution settings model
        resolution_fields = {
            name: (field.annotation, Field(default=field.default, description=field.description))
            for name, field in camera_fields.items()
            if name in ['width', 'height', 'fps']
        }
        CameraResolutionSettings = create_model('CameraResolutionSettings', **resolution_fields)
        
        # Create exposure settings model
        exposure_fields = {
            'mode': (str, Field(default="manual", description="Exposure mode: 'auto' or 'manual'")),
            'value': (float, Field(default=0.25, ge=0.0, le=1.0, description="Manual exposure value (0-1)"))
        }
        CameraExposureSettings = create_model('CameraExposureSettings', **exposure_fields)
        
        # Create image quality settings model
        quality_fields = {
            name: (field.annotation, Field(default=field.default, description=field.description))
            for name, field in camera_fields.items()
            if name in ['gain', 'brightness', 'contrast', 'saturation', 'sharpness']
        }
        CameraImageQuality = create_model('CameraImageQuality', **quality_fields)
        
        # Create focus settings model
        focus_fields = {
            'autofocus': (bool, Field(default=True, description="Enable automatic focus")),
            'white_balance': (str, Field(default="auto", description="White balance mode: 'auto' or 'manual'")),
            'white_balance_value': (float, Field(default=-1.0, ge=-1.0, le=1.0, description="Manual white balance value"))
        }
        CameraFocusSettings = create_model('CameraFocusSettings', **focus_fields)
        
        # Create enhancement settings model (based on ImageEnhancement)
        enhancement_model_fields = {
            name: (field.annotation, Field(default=field.default, description=field.description))
            for name, field in enhancement_fields.items()
        }
        CameraEnhancementSettings = create_model('CameraEnhancementSettings', **enhancement_model_fields)
        
        # Create misc settings model
        misc_fields = {
            name: (field.annotation, Field(default=field.default, description=field.description))
            for name, field in camera_fields.items()
            if name in ['mirror', 'warmup_frames', 'buffer_size']
        }
        CameraMiscSettings = create_model('CameraMiscSettings', **misc_fields)
        
        # Create main request model
        request_fields = {
            'resolution': (Optional[CameraResolutionSettings], Field(None, description="Resolution settings")),
            'exposure': (Optional[CameraExposureSettings], Field(None, description="Exposure settings")),
            'image_quality': (Optional[CameraImageQuality], Field(None, description="Image quality settings")),
            'focus': (Optional[CameraFocusSettings], Field(None, description="Focus settings")),
            'enhancement': (Optional[CameraEnhancementSettings], Field(None, description="Enhancement settings")),
            'misc': (Optional[CameraMiscSettings], Field(None, description="Miscellaneous settings"))
        }
        CameraSettingsRequest = create_model('CameraSettingsRequest', **request_fields)
        
        return {
            'CameraResolutionSettings': CameraResolutionSettings,
            'CameraExposureSettings': CameraExposureSettings,
            'CameraImageQuality': CameraImageQuality,
            'CameraFocusSettings': CameraFocusSettings,
            'CameraEnhancementSettings': CameraEnhancementSettings,
            'CameraMiscSettings': CameraMiscSettings,
            'CameraSettingsRequest': CameraSettingsRequest
        }
    
    @staticmethod
    def create_response_models() -> Dict[str, Type[BaseModel]]:
        """Create response models with consistent structure"""
        
        # Camera settings response
        response_fields = {
            'camera_settings': (Dict, Field(..., description="Current camera settings grouped by category")),
            'is_camera_device': (bool, Field(..., description="Whether using a camera device or video file")),
            'device_initialized': (bool, Field(..., description="Whether the camera device is initialized")),
            'server_time_epoch': (float, Field(..., description="Server timestamp"))
        }
        CameraSettingsResponse = create_model('CameraSettingsResponse', **response_fields)
        
        # Camera preset info
        preset_fields = {
            'name': (str, Field(..., description="Preset display name")),
            'description': (str, Field(..., description="Preset description")),
            'settings': (Dict, Field(..., description="Preset camera settings"))
        }
        CameraPresetInfo = create_model('CameraPresetInfo', **preset_fields)
        
        # Presets response
        presets_response_fields = {
            'presets': (Dict[str, CameraPresetInfo], Field(..., description="Available camera presets")),
            'current_preset': (str, Field(..., description="Currently active preset name")),
            'server_time_epoch': (float, Field(..., description="Server timestamp"))
        }
        CameraPresetsResponse = create_model('CameraPresetsResponse', **presets_response_fields)
        
        # Operation response
        operation_fields = {
            'success': (bool, Field(..., description="Whether the operation was successful")),
            'message': (str, Field(..., description="Operation result message")),
            'applied_at': (Optional[str], Field(None, description="Timestamp when settings were applied")),
            'preset': (Optional[str], Field(None, description="Preset name if applicable")),
            'error': (Optional[str], Field(None, description="Error message if operation failed"))
        }
        CameraOperationResponse = create_model('CameraOperationResponse', **operation_fields)
        
        return {
            'CameraSettingsResponse': CameraSettingsResponse,
            'CameraPresetInfo': CameraPresetInfo,
            'CameraPresetsResponse': CameraPresetsResponse,
            'CameraOperationResponse': CameraOperationResponse
        }
    
    @staticmethod
    def get_all_camera_models() -> Dict[str, Type[BaseModel]]:
        """Get all camera models (request + response)"""
        models = {}
        models.update(ModelFactory.create_camera_request_models())
        models.update(ModelFactory.create_response_models())
        return models
    
    @staticmethod
    def create_model_from_base(base_model: Type[BaseModel], model_name: str, include_fields: list = None, exclude_fields: list = None) -> Type[BaseModel]:
        """Create a new model from a base model with field filtering"""
        
        base_fields = base_model.model_fields
        
        # Filter fields
        if include_fields:
            filtered_fields = {name: field for name, field in base_fields.items() if name in include_fields}
        elif exclude_fields:
            filtered_fields = {name: field for name, field in base_fields.items() if name not in exclude_fields}
        else:
            filtered_fields = base_fields
        
        # Create new model fields
        new_fields = {
            name: (field.annotation, Field(default=field.default, description=field.description))
            for name, field in filtered_fields.items()
        }
        
        return create_model(model_name, **new_fields)