"""
Generic Data Access Layer
Provides path-based access to configuration data with automatic serialization
Replaces multiple get_* methods with a single configurable accessor
"""

import logging
from typing import Any, Dict, Optional, Union, List
from datetime import datetime
from pydantic import BaseModel


class DataAccessor:
    """Generic data accessor with path-based navigation and automatic serialization"""
    
    def __init__(self, config, detector=None):
        self.config = config
        self.detector = detector
        self.logger = logging.getLogger(__name__)
    
    def get_data(
        self, 
        path: str = "", 
        format_type: str = "nested",
        include_metadata: bool = True,
        exclude_runtime: bool = False
    ) -> Dict[str, Any]:
        """
        Get configuration data using path-based access
        
        Args:
            path: Dot-notation path (e.g., "camera.resolution", "zones", "")
            format_type: "nested", "flat", or "api"
            include_metadata: Include server metadata like timestamp
            exclude_runtime: Exclude runtime-only fields
        
        Returns:
            Dict containing requested data with optional metadata
        """
        try:
            # Get base data
            if not path:
                # Return entire configuration
                data = self._get_full_config_data(format_type, exclude_runtime)
            else:
                # Get specific path data
                data = self._get_path_data(path, format_type, exclude_runtime)
            
            # Add metadata if requested
            if include_metadata:
                data.update(self._get_metadata())
            
            return data
            
        except Exception as e:
            self.logger.error(f"Failed to get data for path '{path}': {e}")
            raise
    
    def get_camera_settings(self, format_type: str = "api") -> Dict[str, Any]:
        """Get camera settings in API format"""
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
    
    def get_zones_data(self, include_details: bool = True) -> Dict[str, Any]:
        """Get parking zones data with optional details"""
        zones_data = []
        
        for zone in self.config.parking_zones:
            zone_info = {
                "id": zone.id,
                "space_id": zone.space_id,
                "name": zone.name,
                "occupied": zone.occupied,
                "confidence": zone.confidence
            }
            
            if include_details:
                zone_info.update({
                    "description": zone.description,
                    "coordinates": zone.coordinates,
                    "detection_difficulty": zone.detection_difficulty.value if hasattr(zone.detection_difficulty, "value") else zone.detection_difficulty,
                    "last_detection": zone.last_detection
                })
            
            zones_data.append(zone_info)
        
        return {
            "zones": zones_data,
            "total_zones": len(zones_data)
        }
    
    def get_status_info(self, include_performance: bool = False) -> Dict[str, Any]:
        """Get system status information"""
        status = {
            "processing_enabled": self.config.processing.processing_enabled,
            "snapshot_interval": self.config.processing.snapshot_interval,
            "last_snapshot_epoch": self.config.last_snapshot_epoch,
            "total_zones": len(self.config.parking_zones)
        }
        
        if self.detector:
            status.update({
                "model_loaded": hasattr(self.detector, 'model') and self.detector.model is not None,
                "device": getattr(self.detector, 'device', 'unknown'),
                "next_snapshot_in": max(0, self.config.processing.snapshot_interval - 
                                     (datetime.now().timestamp() - self.config.last_snapshot_epoch))
            })
            
            if include_performance:
                status.update({
                    "processing_fps": getattr(self.detector, 'processing_fps', 0.0),
                    "is_camera_device": getattr(self.detector, 'is_camera_device', False)
                })
        
        return status
    
    def _get_full_config_data(self, format_type: str, exclude_runtime: bool) -> Dict[str, Any]:
        """Get full configuration data in specified format"""
        
        if format_type == "flat":
            # Use existing to_dict for backward compatibility
            return self.config.to_dict()
        
        elif format_type == "api":
            # API-friendly format
            return {
                "camera": self.get_camera_settings(),
                "zones": self.get_zones_data(),
                "status": self.get_status_info(),
                "processing": {
                    "snapshot_interval": self.config.processing.snapshot_interval,
                    "confidence_threshold": self.config.processing.confidence_threshold,
                    "model_path": self.config.processing.model_path,
                    "processing_enabled": self.config.processing.processing_enabled
                }
            }
        
        else:  # nested format
            # Use Pydantic's model_dump for nested structure
            exclude_fields = set()
            if exclude_runtime:
                exclude_fields.update(['last_snapshot_epoch', 'config_loaded_from'])
            
            return self.config.model_dump(exclude=exclude_fields if exclude_fields else None)
    
    def _get_path_data(self, path: str, format_type: str, exclude_runtime: bool) -> Dict[str, Any]:
        """Get data for a specific path"""
        
        # Split path into components
        path_parts = path.split('.')
        
        # Navigate to the target
        current = self.config
        for part in path_parts:
            if hasattr(current, part):
                current = getattr(current, part)
            else:
                raise ValueError(f"Path '{path}' not found in configuration")
        
        # Handle different data types
        if isinstance(current, BaseModel):
            exclude_fields = set()
            if exclude_runtime:
                exclude_fields.update(['occupied', 'confidence', 'last_detection'])
            
            return current.model_dump(exclude=exclude_fields if exclude_fields else None)
        
        elif isinstance(current, list):
            # Handle list of models (like parking_zones)
            result = []
            for item in current:
                if isinstance(item, BaseModel):
                    exclude_fields = set()
                    if exclude_runtime:
                        exclude_fields.update(['occupied', 'confidence', 'last_detection'])
                    
                    result.append(item.model_dump(exclude=exclude_fields if exclude_fields else None))
                else:
                    result.append(item)
            
            return {"data": result, "count": len(result)}
        
        else:
            # Simple value
            return {"value": current}
    
    def _get_metadata(self) -> Dict[str, Any]:
        """Get server metadata"""
        return {
            "server_time_epoch": datetime.now().timestamp(),
            "config_loaded_from": getattr(self.config, 'config_loaded_from', None)
        }
    
    def get_updatable_fields_info(self, model_path: str = "") -> Dict[str, Any]:
        """Get information about updatable fields for a model"""
        
        if not model_path:
            # Return info for all main models
            return {
                "camera": self._get_model_fields_info(self.config.camera),
                "processing": self._get_model_fields_info(self.config.processing),
                "enhancement": self._get_model_fields_info(self.config.enhancement),
                "api": self._get_model_fields_info(self.config.api),
                "video": self._get_model_fields_info(self.config.video)
            }
        
        # Get specific model
        path_parts = model_path.split('.')
        current = self.config
        for part in path_parts:
            current = getattr(current, part)
        
        if isinstance(current, BaseModel):
            return self._get_model_fields_info(current)
        else:
            return {"error": f"Path '{model_path}' does not point to a model"}
    
    def _get_model_fields_info(self, model: BaseModel) -> Dict[str, Any]:
        """Get field information for a model"""
        fields_info = {}
        
        for field_name, field_info in model.model_fields.items():
            fields_info[field_name] = {
                "type": str(field_info.annotation),
                "required": field_info.is_required(),
                "default": field_info.default,
                "description": field_info.description
            }
        
        return fields_info