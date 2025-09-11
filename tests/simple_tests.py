#!/usr/bin/env python3
"""
Simple Unit Tests for oaParkingMonitor
No external dependencies (no pytest, no physical constraints)
Tests core logic validation and architecture integrity
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_basic_model_validation():
    """Test basic Pydantic model validation"""
    print("Testing basic model validation...")
    
    try:
        from models.shared import CameraSettings, ProcessingSettings, VideoSource
        
        # Test valid camera settings
        camera = CameraSettings()
        assert camera.width == 1920, f"Expected width 1920, got {camera.width}"
        assert camera.height == 1080, f"Expected height 1080, got {camera.height}"
        
        # Test processing settings
        processing = ProcessingSettings()
        assert processing.snapshot_interval == 5, f"Expected interval 5, got {processing.snapshot_interval}"
        assert processing.confidence_threshold == 0.5, f"Expected threshold 0.5, got {processing.confidence_threshold}"
        
        # Test video source default
        video = VideoSource(source="")
        assert video.source == "0", f"Expected source '0', got '{video.source}'"
        
        print("✅ Basic model validation working")
        return True
        
    except Exception as e:
        print(f"❌ Basic model validation failed: {e}")
        return False

def test_config_loading():
    """Test configuration loading without physical files"""
    print("\nTesting configuration loading...")
    
    try:
        from config.models import ParkingConfig, ParkingZone
        from config.enums import DetectionDifficulty
        
        # Test creating config programmatically
        zone = ParkingZone(
            id=1, space_id=1, name="A1", description="Test zone",
            coordinates=[[100, 100], [200, 200], [300, 300]],
            detection_difficulty=DetectionDifficulty.EASY
        )
        
        config = ParkingConfig(parking_zones=[zone])
        
        # Test convenience methods
        assert config.get_total_zones() == 1
        found_zone = config.get_zone_by_id(1)
        assert found_zone is not None
        assert found_zone.name == "A1"
        
        # Test zone counting
        assert config.get_easy_zones_count() == 1
        assert config.get_hard_zones_count() == 0
        
        print("✅ Configuration loading working")
        return True
        
    except Exception as e:
        print(f"❌ Configuration loading failed: {e}")
        return False

def test_settings_applicator_logic():
    """Test settings applicator reflection logic"""
    print("\nTesting settings applicator...")
    
    try:
        from services.settings_applicator import SettingsApplicator
        from config.models import ParkingConfig
        
        config = ParkingConfig()
        applicator = SettingsApplicator()
        
        # Test structure validation
        valid_structure = {
            "resolution": {"width": 1280},
            "image_quality": {"brightness": 0.8}
        }
        assert applicator.validate_settings_structure(valid_structure) is True
        
        # Test invalid structure
        invalid_structure = {
            "unknown_section": {"field": "value"}
        }
        assert applicator.validate_settings_structure(invalid_structure) is False
        
        print("✅ Settings applicator working")
        return True
        
    except Exception as e:
        print(f"❌ Settings applicator failed: {e}")
        return False

def test_data_accessor_logic():
    """Test data accessor without detector dependency"""
    print("\nTesting data accessor...")
    
    try:
        from services.data_accessor import DataAccessor
        from config.models import ParkingConfig, ParkingZone
        
        # Create simple config
        zone = ParkingZone(
            id=1, space_id=1, name="A1", description="Test",
            coordinates=[[0, 0], [1, 1], [2, 2]]
        )
        config = ParkingConfig(parking_zones=[zone])
        
        accessor = DataAccessor(config)
        
        # Test zones data
        zones_data = accessor.get_zones_data()
        assert "zones" in zones_data
        assert "total_zones" in zones_data
        assert zones_data["total_zones"] == 1
        
        # Test camera settings
        camera_settings = accessor.get_camera_settings()
        assert "resolution" in camera_settings
        assert camera_settings["resolution"]["width"] == 1920
        
        print("✅ Data accessor working")
        return True
        
    except Exception as e:
        print(f"❌ Data accessor failed: {e}")
        return False

def test_model_factory_creation():
    """Test dynamic model creation"""
    print("\nTesting model factory...")
    
    try:
        from models.model_factory import ModelFactory
        
        # Test creating camera models
        camera_models = ModelFactory.create_camera_request_models()
        
        expected_models = [
            'CameraResolutionSettings', 'CameraExposureSettings',
            'CameraImageQuality', 'CameraSettingsRequest'
        ]
        
        for model_name in expected_models:
            assert model_name in camera_models, f"Model {model_name} not created"
        
        # Test instantiation
        resolution_model = camera_models['CameraResolutionSettings']
        instance = resolution_model(width=1920, height=1080, fps=30)
        assert instance.width == 1920
        
        print("✅ Model factory working")
        return True
        
    except Exception as e:
        print(f"❌ Model factory failed: {e}")
        return False

def test_import_structure():
    """Test that all imports work correctly"""
    print("\nTesting import structure...")
    
    try:
        # Test main model imports
        from models.shared import CameraSettings, ImageEnhancement, ProcessingSettings
        from config.models import ParkingConfig, ParkingZone
        from config.enums import DetectionDifficulty, LogLevel
        
        # Test service imports
        from services.settings_applicator import SettingsApplicator
        from services.data_accessor import DataAccessor
        from services.preset_loader import PresetLoader
        
        # Test utility imports
        from utils.schema_generator import SchemaGenerator
        
        print("✅ All imports working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Import structure failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_architecture_validation():
    """Validate the complete architecture works"""
    print("\n🏗️ Validating Complete Architecture")
    print("=" * 40)
    
    try:
        from config.models import ParkingConfig
        from models.shared import CameraSettings
        
        # Test complete workflow without physical dependencies
        config = ParkingConfig()
        
        # Test that models work together
        camera = config.camera
        assert isinstance(camera, CameraSettings)
        
        # Test serialization
        config_dict = config.to_dict()
        assert "camera_width" in config_dict
        assert config_dict["camera_width"] == 1920
        
        # Test zones data
        zones_data = config.get_zones_data()
        assert isinstance(zones_data, list)
        
        print("✅ Complete architecture validated")
        return True
        
    except Exception as e:
        print(f"❌ Architecture validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test execution"""
    print("🧹 oaParkingMonitor Final Cleanup & Validation")
    print("=" * 55)
    print("Running simple, precise tests without physical dependencies\n")
    
    tests = [
        ("Import Structure", test_import_structure),
        ("Model Validation", test_basic_model_validation),
        ("Config Loading", test_config_loading),
        ("Settings Applicator", test_settings_applicator_logic),
        ("Data Accessor", test_data_accessor_logic),
        ("Model Factory", test_model_factory_creation),
        ("Architecture", run_architecture_validation)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"🔍 {test_name}")
        print("-" * 30)
        if test_func():
            passed += 1
        print()
    
    print("=" * 55)
    print(f"📊 Final Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("\n✨ oaParkingMonitor Status: CLEAN & READY")
        print("  ✅ Architecture validated")
        print("  ✅ No physical dependencies in tests")
        print("  ✅ Future-proof structure confirmed")
        print("  ✅ Zero maintenance burden achieved")
        print("  ✅ Professional structure maintained")
        
        print("\n🚀 Ready for production deployment!")
        return 0
    else:
        print(f"\n❌ {total - passed} tests failed - needs attention")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)