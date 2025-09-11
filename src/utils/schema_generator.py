"""
Configuration Schema Documentation Generator
Auto-generates YAML schema and documentation from Pydantic models
Ensures documentation always stays in sync with code
"""

import json
import yaml
from typing import Any, Dict, Type, get_origin, get_args
from pathlib import Path
from pydantic import BaseModel
from datetime import datetime

from ..config.models import ParkingConfig
from ..models.shared import CameraSettings, ImageEnhancement, ProcessingSettings


class SchemaGenerator:
    """Generates configuration schemas and documentation from Pydantic models"""
    
    def __init__(self):
        self.generated_at = datetime.now().isoformat()
    
    def generate_yaml_schema(self, model: Type[BaseModel], include_examples: bool = True) -> str:
        """Generate YAML schema documentation from Pydantic model"""
        
        schema_data = {
            "# Auto-generated Configuration Schema": None,
            f"# Generated at: {self.generated_at}": None,
            "# DO NOT EDIT - Regenerate using schema_generator.py": None,
            "": None
        }
        
        # Add model documentation
        if model.__doc__:
            schema_data[f"# {model.__doc__.strip()}"] = None
            schema_data[" "] = None
        
        # Process model fields
        for field_name, field_info in model.model_fields.items():
            field_schema = self._process_field(field_name, field_info, include_examples)
            schema_data.update(field_schema)
        
        # Convert to YAML string
        yaml_str = yaml.dump(schema_data, default_flow_style=False, allow_unicode=True)
        
        # Clean up the YAML formatting
        lines = yaml_str.split('\n')
        cleaned_lines = []
        
        for line in lines:
            if ': null' in line and line.strip().startswith('#'):
                # Convert comment lines
                cleaned_lines.append(line.replace(': null', ''))
            elif line.strip():
                cleaned_lines.append(line)
            else:
                cleaned_lines.append('')  # Preserve empty lines
        
        return '\n'.join(cleaned_lines)
    
    def generate_api_schema(self, model: Type[BaseModel]) -> Dict[str, Any]:
        """Generate API schema documentation"""
        
        return {
            "model": model.__name__,
            "description": model.__doc__.strip() if model.__doc__ else "",
            "generated_at": self.generated_at,
            "fields": {
                field_name: {
                    "type": str(field_info.annotation),
                    "required": field_info.is_required(),
                    "default": field_info.default,
                    "description": field_info.description or "",
                    "constraints": self._get_field_constraints(field_info)
                }
                for field_name, field_info in model.model_fields.items()
            }
        }
    
    def generate_full_documentation(self, output_dir: str = "docs/generated") -> Dict[str, str]:
        """Generate complete documentation for all models"""
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        generated_files = {}
        
        # Main configuration schema
        main_schema = self.generate_yaml_schema(ParkingConfig)
        main_file = output_path / "config_schema.yaml"
        main_file.write_text(main_schema)
        generated_files["config_schema"] = str(main_file)
        
        # Camera settings schema
        camera_schema = self.generate_yaml_schema(CameraSettings)
        camera_file = output_path / "camera_schema.yaml"
        camera_file.write_text(camera_schema)
        generated_files["camera_schema"] = str(camera_file)
        
        # Processing settings schema
        processing_schema = self.generate_yaml_schema(ProcessingSettings)
        processing_file = output_path / "processing_schema.yaml"
        processing_file.write_text(processing_schema)
        generated_files["processing_schema"] = str(processing_file)
        
        # API documentation
        api_docs = {
            "parking_config": self.generate_api_schema(ParkingConfig),
            "camera_settings": self.generate_api_schema(CameraSettings),
            "processing_settings": self.generate_api_schema(ProcessingSettings),
            "image_enhancement": self.generate_api_schema(ImageEnhancement)
        }
        
        api_file = output_path / "api_schemas.json"
        api_file.write_text(json.dumps(api_docs, indent=2, default=str))
        generated_files["api_schemas"] = str(api_file)
        
        # Generate README
        readme_content = self._generate_readme(generated_files)
        readme_file = output_path / "README.md"
        readme_file.write_text(readme_content)
        generated_files["readme"] = str(readme_file)
        
        return generated_files
    
    def _process_field(self, field_name: str, field_info, include_examples: bool) -> Dict[str, Any]:
        """Process a single field into schema format"""
        
        result = {}
        
        # Add field description as comment
        if field_info.description:
            result[f"# {field_name}: {field_info.description}"] = None
        
        # Get field type and default
        field_type = field_info.annotation
        default_value = field_info.default
        
        # Handle different field types
        if isinstance(default_value, BaseModel):
            # Nested model
            nested_schema = {}
            for nested_name, nested_info in default_value.model_fields.items():
                nested_field = self._process_field(nested_name, nested_info, include_examples)
                nested_schema.update(nested_field)
            result[field_name] = nested_schema
            
        elif isinstance(default_value, list) and default_value:
            # List with default items
            if include_examples:
                result[field_name] = default_value
            else:
                result[field_name] = "[]  # Array"
                
        else:
            # Simple field
            if include_examples and default_value is not None:
                result[field_name] = default_value
            else:
                type_name = self._get_type_name(field_type)
                constraints = self._get_field_constraints(field_info)
                constraint_str = f" {constraints}" if constraints else ""
                result[field_name] = f"<{type_name}>{constraint_str}"
        
        return result
    
    def _get_type_name(self, field_type) -> str:
        """Get a readable type name"""
        
        if field_type == int:
            return "integer"
        elif field_type == float:
            return "number"
        elif field_type == str:
            return "string"
        elif field_type == bool:
            return "boolean"
        elif field_type == list:
            return "array"
        elif field_type == dict:
            return "object"
        elif get_origin(field_type) is list:
            args = get_args(field_type)
            if args:
                return f"array<{self._get_type_name(args[0])}>"
            return "array"
        else:
            return str(field_type).replace('typing.', '').replace('<class \'', '').replace('\'>', '')
    
    def _get_field_constraints(self, field_info) -> str:
        """Extract field constraints as readable string"""
        
        constraints = []
        
        # Get constraints from field info
        if hasattr(field_info, 'constraints'):
            for constraint in field_info.constraints:
                if hasattr(constraint, 'ge') and constraint.ge is not None:
                    constraints.append(f"≥{constraint.ge}")
                if hasattr(constraint, 'le') and constraint.le is not None:
                    constraints.append(f"≤{constraint.le}")
                if hasattr(constraint, 'min_length') and constraint.min_length is not None:
                    constraints.append(f"min_length:{constraint.min_length}")
                if hasattr(constraint, 'max_length') and constraint.max_length is not None:
                    constraints.append(f"max_length:{constraint.max_length}")
        
        return f"({', '.join(constraints)})" if constraints else ""
    
    def _generate_readme(self, generated_files: Dict[str, str]) -> str:
        """Generate minimal README for documentation"""
        return f"""# Auto-Generated Documentation

Generated at: {self.generated_at}

Files: {', '.join(generated_files.keys())}
"""


def generate_schemas():
    """Convenience function to generate all schemas"""
    generator = SchemaGenerator()
    return generator.generate_full_documentation()


if __name__ == "__main__":
    files = generate_schemas()
    print("Generated documentation files:")
    for name, path in files.items():
        print(f"  {name}: {path}")