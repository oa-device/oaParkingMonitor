"""
Generic Settings Applicator Service
Automatically applies nested settings to configuration models using reflection
Eliminates manual field-by-field updates
"""

import logging
from typing import Any, Dict, Type, Union
from pydantic import BaseModel


class SettingsApplicator:
    """Generic settings applicator using Pydantic model reflection"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def apply_nested_settings(
        self, 
        target_config: BaseModel, 
        settings_data: Dict[str, Any],
        mapping: Dict[str, str] = None
    ) -> bool:
        """
        Apply nested settings to target configuration automatically
        
        Args:
            target_config: The config object to update
            settings_data: Nested settings data from API request
            mapping: Optional field mapping (API field -> config field)
        
        Returns:
            bool: True if any settings were applied
        """
        applied_changes = False
        
        # Default mapping if not provided
        if mapping is None:
            mapping = {
                "resolution": "camera",
                "exposure": "camera", 
                "image_quality": "camera",
                "focus": "camera",
                "misc": "camera",
                "enhancement": "enhancement"
            }
        
        try:
            for api_section, config_section in mapping.items():
                if api_section not in settings_data:
                    continue
                
                section_data = settings_data[api_section]
                if not isinstance(section_data, dict):
                    continue
                
                # Get the target model section
                target_section = getattr(target_config, config_section, None)
                if target_section is None:
                    self.logger.warning(f"Target section '{config_section}' not found")
                    continue
                
                # Apply fields using reflection
                section_applied = self._apply_fields_to_model(target_section, section_data, api_section)
                applied_changes = applied_changes or section_applied
            
            if applied_changes:
                self.logger.info("Settings applied successfully using reflection")
            
            return applied_changes
            
        except Exception as e:
            self.logger.error(f"Failed to apply settings: {e}")
            raise
    
    def _apply_fields_to_model(self, target_model: BaseModel, field_data: Dict[str, Any], section_name: str) -> bool:
        """Apply fields to a specific model using reflection"""
        applied = False
        
        # Get model fields info
        model_fields = target_model.model_fields
        
        for api_field, value in field_data.items():
            # Map API field names to model field names
            model_field = self._map_api_field_to_model_field(api_field, section_name)
            
            if model_field not in model_fields:
                self.logger.debug(f"Field '{model_field}' not found in {target_model.__class__.__name__}")
                continue
            
            try:
                # Get current value for comparison
                current_value = getattr(target_model, model_field, None)
                
                # Convert and validate the value based on field type
                field_info = model_fields[model_field]
                converted_value = self._convert_value(value, field_info.annotation, api_field)
                
                # Only update if value has changed
                if current_value != converted_value:
                    setattr(target_model, model_field, converted_value)
                    self.logger.debug(f"Updated {target_model.__class__.__name__}.{model_field}: {current_value} -> {converted_value}")
                    applied = True
                
            except Exception as e:
                self.logger.error(f"Failed to apply field '{api_field}' -> '{model_field}': {e}")
                continue
        
        return applied
    
    def _map_api_field_to_model_field(self, api_field: str, section: str) -> str:
        """Map API field names to model field names"""
        
        # Handle special field mappings
        field_mappings = {
            # Exposure section mappings
            ("exposure", "value"): "exposure",
            
            # Focus section mappings  
            ("focus", "white_balance_value"): "white_balance",
            
            # Enhancement section mappings
            ("enhancement", "auto_enhance"): "auto_enhance",
        }
        
        # Check for specific mapping
        mapping_key = (section, api_field)
        if mapping_key in field_mappings:
            return field_mappings[mapping_key]
        
        # Default: use field name as-is
        return api_field
    
    def _convert_value(self, value: Any, field_type: Type, field_name: str) -> Any:
        """Convert API value to appropriate type for model field"""
        
        # Handle Union types (like Optional)
        if hasattr(field_type, '__origin__') and field_type.__origin__ is Union:
            # Get the non-None type from Optional
            non_none_types = [t for t in field_type.__args__ if t != type(None)]
            if non_none_types:
                field_type = non_none_types[0]
        
        # Handle basic type conversions
        if field_type == int or field_type == 'int':
            return int(float(value))  # Handle both int and float inputs
        elif field_type == float or field_type == 'float':
            return float(value)
        elif field_type == bool or field_type == 'bool':
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            return bool(value)
        elif field_type == str or field_type == 'str':
            return str(value)
        else:
            # For complex types, return as-is and let Pydantic handle validation
            return value
    
    def get_updatable_fields(self, model: BaseModel) -> Dict[str, Dict[str, Any]]:
        """Get information about all updatable fields in a model"""
        fields_info = {}
        
        for field_name, field_info in model.model_fields.items():
            fields_info[field_name] = {
                "type": str(field_info.annotation),
                "required": field_info.is_required(),
                "default": field_info.default,
                "description": field_info.description
            }
        
        return fields_info
    
    def validate_settings_structure(self, settings_data: Dict[str, Any], allowed_sections: list = None) -> bool:
        """Validate the structure of incoming settings data"""
        if allowed_sections is None:
            allowed_sections = ["resolution", "exposure", "image_quality", "focus", "enhancement", "misc"]
        
        for section in settings_data.keys():
            if section not in allowed_sections:
                self.logger.warning(f"Unknown settings section: {section}")
                return False
            
            if not isinstance(settings_data[section], dict):
                self.logger.error(f"Settings section '{section}' must be a dictionary")
                return False
        
        return True