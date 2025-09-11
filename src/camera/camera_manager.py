"""
Camera Management Module
Handles camera initialization, configuration, and frame capture
"""

import asyncio
import cv2
import numpy as np
import logging
from pathlib import Path
from typing import Optional

from ..config.models import ParkingConfig
from .parameter_utils import CameraParameterConverter


class CameraManager:
    """Manages camera initialization, configuration, and frame capture"""
    
    def __init__(self, config: ParkingConfig, video_source):
        """Initialize camera manager with configuration"""
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.video_source = video_source
        
        # Camera state
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_camera_device = str(video_source).isdigit()
        self.camera_initialized = False
        self.current_frame: Optional[np.ndarray] = None
        
        # Parameter converter
        self.param_converter = CameraParameterConverter()
    
    async def initialize(self) -> bool:
        """Initialize camera with enhanced controls and image quality settings"""
        if self.camera_initialized or not self.is_camera_device:
            return True
        
        try:
            # For camera devices, create persistent connection
            video_input = int(str(self.video_source))
            self.logger.info(f"Initializing camera device: {video_input}")
            
            self.cap = cv2.VideoCapture(video_input)
            if not self.cap.isOpened():
                self.logger.error(f"Cannot open camera device: {video_input}")
                return False
            
            # Apply camera settings
            success = self._apply_camera_settings()
            if not success:
                self.logger.warning("Some camera settings could not be applied")
            
            # Perform camera warm-up routine
            await self._perform_warmup()
            
            self.camera_initialized = True
            self.logger.info("Camera initialization completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Camera initialization failed: {e}")
            if self.cap:
                self.cap.release()
                self.cap = None
            return False
    
    def _apply_camera_settings(self) -> bool:
        """Apply enhanced camera properties for better image quality"""
        if not self.cap:
            return False
        
        try:
            # Resolution settings
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.camera.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.camera.height)
            self.cap.set(cv2.CAP_PROP_FPS, self.config.camera.fps)
            self.logger.debug(f"Set resolution: {self.config.camera.width}x{self.config.camera.height} @ {self.config.camera.fps}fps")
            
            # Buffer size to reduce latency
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.config.camera.buffer_size)
            self.logger.debug(f"Set camera buffer size to {self.config.camera.buffer_size}")
            
            # Focus settings
            if self.config.camera.autofocus:
                self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
                self.logger.debug("Enabled camera autofocus")
            else:
                self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
                self.logger.debug("Disabled camera autofocus")
            
            # Exposure control - critical for fixing overexposure
            if self.config.camera.exposure >= 0:
                # Manual exposure mode
                self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Manual mode
                exposure_value = self.param_converter.to_camera_exposure(self.config.camera.exposure)
                self.cap.set(cv2.CAP_PROP_EXPOSURE, exposure_value)
                self.logger.info(f"Set manual exposure: {self.config.camera.exposure} -> {exposure_value}")
            else:
                # Auto exposure mode
                self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
                self.logger.debug("Enabled auto exposure")
            
            # Gain control
            if self.config.camera.gain >= 0:
                gain_value = self.param_converter.to_camera_gain(self.config.camera.gain)
                self.cap.set(cv2.CAP_PROP_GAIN, gain_value)
                self.logger.debug(f"Set manual gain: {self.config.camera.gain} -> {gain_value}")
            
            # Image quality settings
            if hasattr(cv2, 'CAP_PROP_BRIGHTNESS'):
                brightness_value = self.param_converter.to_camera_brightness(self.config.camera.brightness)
                self.cap.set(cv2.CAP_PROP_BRIGHTNESS, brightness_value)
                self.logger.debug(f"Set brightness: {self.config.camera.brightness} -> {brightness_value}")
            
            if hasattr(cv2, 'CAP_PROP_CONTRAST'):
                contrast_value = self.param_converter.to_camera_contrast(self.config.camera.contrast)
                self.cap.set(cv2.CAP_PROP_CONTRAST, contrast_value)
                self.logger.debug(f"Set contrast: {self.config.camera.contrast} -> {contrast_value}")
            
            if hasattr(cv2, 'CAP_PROP_SATURATION'):
                saturation_value = self.param_converter.to_camera_saturation(self.config.camera.saturation)
                self.cap.set(cv2.CAP_PROP_SATURATION, saturation_value)
                self.logger.debug(f"Set saturation: {self.config.camera.saturation} -> {saturation_value}")
            
            if hasattr(cv2, 'CAP_PROP_SHARPNESS'):
                sharpness_value = self.param_converter.to_camera_sharpness(self.config.camera.sharpness)
                self.cap.set(cv2.CAP_PROP_SHARPNESS, sharpness_value)
                self.logger.debug(f"Set sharpness: {self.config.camera.sharpness} -> {sharpness_value}")
            
            # White balance
            if self.config.camera.white_balance >= 0:
                self.cap.set(cv2.CAP_PROP_AUTO_WB, 0)  # Manual white balance
                wb_value = self.param_converter.to_camera_white_balance(self.config.camera.white_balance)
                self.cap.set(cv2.CAP_PROP_WB_TEMPERATURE, wb_value)
                self.logger.debug(f"Set manual white balance: {self.config.camera.white_balance}")
            else:
                self.cap.set(cv2.CAP_PROP_AUTO_WB, 1)  # Auto white balance
                self.logger.debug("Enabled auto white balance")
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Could not set all camera properties: {e}")
            return False
    
    async def _perform_warmup(self):
        """Perform camera warm-up routine"""
        if not self.cap:
            return
        
        self.logger.info(f"Starting camera warm-up with {self.config.camera.warmup_frames} frames...")
        
        for i in range(self.config.camera.warmup_frames):
            ret, frame = self.cap.read()
            if not ret:
                self.logger.warning(f"Failed to read warm-up frame {i+1}/{self.config.camera.warmup_frames}")
                continue
            
            # Small delay between frames to allow camera adjustment
            await asyncio.sleep(0.1)
            
            self.logger.debug(f"Warm-up frame {i+1}/{self.config.camera.warmup_frames} captured")
    
    def capture_frame(self) -> Optional[np.ndarray]:
        """Capture single frame from video source"""
        try:
            if self.is_camera_device:
                return self._capture_from_camera()
            else:
                return self._capture_from_file()
        except Exception as e:
            self.logger.error(f"Frame capture failed: {e}")
            return None
    
    def _capture_from_camera(self) -> Optional[np.ndarray]:
        """Capture frame from camera device"""
        # Use persistent camera connection
        if not self.camera_initialized or self.cap is None:
            self.logger.error("Camera not initialized. Call initialize() first.")
            return None
        
        # Read from persistent connection
        ret, frame = self.cap.read()
        if not ret:
            self.logger.warning("Failed to read frame from persistent camera connection")
            # Try to reinitialize camera on failure
            try:
                self.logger.info("Attempting camera reconnection...")
                self._reinitialize_camera()
                ret, frame = self.cap.read() if self.cap else (False, None)
                if not ret:
                    return None
            except Exception as reconnect_error:
                self.logger.error(f"Camera reconnection failed: {reconnect_error}")
                return None
        
        # Apply camera mirroring if enabled
        if self.config.camera.mirror:
            frame = cv2.flip(frame, 1)  # Horizontal flip
            self.logger.debug("Applied camera mirror (horizontal flip)")
        
        # Store current frame for raw access
        self.current_frame = frame.copy()
        
        self.logger.debug("Captured frame from persistent camera connection")
        return frame
    
    def _capture_from_file(self) -> Optional[np.ndarray]:
        """Capture frame from video file"""
        video_source_path = Path(self.video_source) if isinstance(self.video_source, str) else self.video_source
        
        if not video_source_path.exists():
            self.logger.warning(f"Video source not found: {video_source_path}")
            return None
        
        video_input = str(video_source_path)
        self.logger.debug(f"Using video file: {video_input}")
        
        # Open video capture for file
        cap = cv2.VideoCapture(video_input)
        if not cap.isOpened():
            self.logger.error(f"Cannot open video source: {video_input}")
            return None
        
        # Read frame
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            self.logger.warning("Failed to read frame from video file")
            return None
        
        # Store current frame for raw access
        self.current_frame = frame.copy()
        return frame
    
    def _reinitialize_camera(self):
        """Synchronous camera reinitialization for use in capture_frame"""
        try:
            if self.cap:
                self.cap.release()
            
            video_input = int(str(self.video_source))
            self.cap = cv2.VideoCapture(video_input)
            
            if not self.cap.isOpened():
                raise RuntimeError(f"Cannot reopen camera device: {video_input}")
            
            # Reapply essential camera settings
            if self.config.camera.autofocus:
                self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.config.camera.buffer_size)
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
            
            self.logger.info("Camera reconnected successfully")
            
        except Exception as e:
            self.logger.error(f"Camera reinitialization failed: {e}")
            self.cap = None
            self.camera_initialized = False
            raise
    
    def get_current_frame(self) -> Optional[np.ndarray]:
        """Get the last captured frame"""
        return self.current_frame
    
    def is_initialized(self) -> bool:
        """Check if camera is initialized and ready"""
        return self.camera_initialized
    
    def release(self):
        """Release camera resources"""
        if self.cap is not None:
            try:
                self.cap.release()
                self.logger.info("Camera connection released")
            except Exception as e:
                self.logger.error(f"Error releasing camera: {e}")
            finally:
                self.cap = None
                self.camera_initialized = False