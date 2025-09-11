"""
Camera Parameter Conversion Utilities
Handles conversion between normalized values and camera-specific ranges
"""

class CameraParameterConverter:
    """Utility class for converting normalized parameter values to camera-specific ranges"""
    
    @staticmethod
    def to_camera_exposure(exposure: float) -> float:
        """Convert 0-1 exposure value to camera-specific range"""
        # Most cameras use negative values for exposure (e.g., -13 to -1)
        # Convert 0-1 to -13 to -1 range for manual exposure
        return -13.0 + (exposure * 12.0)
    
    @staticmethod
    def to_camera_gain(gain: float) -> float:
        """Convert 0-1 gain value to camera-specific range"""
        # Most cameras use 0-100 range for gain
        return gain * 100.0
    
    @staticmethod
    def to_camera_brightness(brightness: float) -> float:
        """Convert 0-1 brightness value to camera-specific range"""
        # Most cameras use -100 to 100 range for brightness
        return (brightness - 0.5) * 200.0
    
    @staticmethod
    def to_camera_contrast(contrast: float) -> float:
        """Convert 0-1 contrast value to camera-specific range"""
        # Most cameras use 0-100 range for contrast
        return contrast * 100.0
    
    @staticmethod
    def to_camera_saturation(saturation: float) -> float:
        """Convert 0-1 saturation value to camera-specific range"""
        # Most cameras use 0-100 range for saturation
        return saturation * 100.0
    
    @staticmethod
    def to_camera_sharpness(sharpness: float) -> float:
        """Convert 0-1 sharpness value to camera-specific range"""
        # Most cameras use 0-100 range for sharpness
        return sharpness * 100.0
    
    @staticmethod
    def to_camera_white_balance(wb: float) -> float:
        """Convert 0-1 white balance value to camera-specific range"""
        # Most cameras use 2000-7000K range for white balance
        return 2000 + (wb * 5000)