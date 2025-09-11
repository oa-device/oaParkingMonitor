"""
MVP Snapshot-Based Parking Detector (Updated for Modular Config)
Simplified detection engine that processes one frame every 5 seconds
"""

import asyncio
import logging
import platform
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import cv2
import numpy as np

from .config import ConfigManager, ParkingConfig
from .config.models import ParkingZone


@dataclass
class VehicleDetection:
    """Represents a single vehicle detection"""
    x: int
    y: int
    width: int
    height: int
    confidence: float
    class_name: str = "vehicle"
    zone_id: Optional[int] = None


@dataclass
class SnapshotResult:
    """Result of snapshot processing"""
    image: np.ndarray
    detections: List[VehicleDetection]
    timestamp: float
    zones_status: List[Dict[str, Any]]
    processing_time: float


class MVPParkingDetector:
    """Simplified MVP parking detector with snapshot processing (Updated for modular config)"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.running = False
        
        # Load configuration using new system
        self.config_manager = ConfigManager()
        self.config = self.config_manager.config
        
        # Video source setup - handle both camera devices and file paths
        video_source_str = str(self.config.video.source)
        if video_source_str.isdigit():
            self.video_source = self.config.video.source  # Keep as string for camera device
        else:
            self.video_source = Path(self.config.video.source)  # Convert to Path for file
        self.model_path = Path.home() / "orangead" / "parking-monitor" / self.config.processing.model_path
        
        # Device detection
        self.device = self._detect_optimal_device()
        self.is_apple_silicon = self._is_apple_silicon()
        
        # Detection state
        self.model = None
        self.last_snapshot: Optional[SnapshotResult] = None
        self.current_frame: Optional[np.ndarray] = None
        
        # Camera state for persistent connection
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_camera_device = video_source_str.isdigit()
        self.camera_initialized = False
        
        # Statistics for API compatibility
        self.stats = {
            "total_frames": 0,
            "detections": 0,
            "vehicles_detected": 0,
            "processing_fps": 0.0,
            "uptime_start": datetime.now().isoformat(),
            "last_update": datetime.now().isoformat(),
            "last_detection": None,
            "total_spaces": len(self.config.parking_zones),
            "occupied_spaces": 0,
            "occupancy_rate": 0.0,
            "video_source": str(self.video_source),
            "model_loaded": False,
            "device_info": {
                "device": str(self.device),
                "metal_available": self.is_apple_silicon,
                "platform": platform.platform(),
                "python_version": platform.python_version()
            }
        }
        
        # Initialize logging
        self.logger.info(f"MVP Detector initialized with device: {self.device}")
        self.logger.info(f"Video source: {self.video_source}")
        self.logger.info(f"Snapshot interval: {self.config.processing.snapshot_interval} seconds")
    
    def _is_apple_silicon(self) -> bool:
        """Check if running on Apple Silicon"""
        try:
            return platform.system() == "Darwin" and platform.machine() == "arm64"
        except Exception:
            return False
    
    def _detect_optimal_device(self) -> str:
        """Detect optimal processing device"""
        try:
            import torch
            
            # Check for Apple Silicon MPS
            if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                return "mps"
            
            # Check for CUDA
            if torch.cuda.is_available():
                return "cuda"
            
            # Fallback to CPU
            return "cpu"
        except Exception as e:
            self.logger.warning(f"Device detection failed: {e}, using CPU")
            return "cpu"
    
    def _convert_to_camera_exposure(self, exposure: float) -> float:
        """Convert 0-1 exposure value to camera-specific range"""
        # Most cameras use negative values for exposure (e.g., -13 to -1)
        # Convert 0-1 to -13 to -1 range for manual exposure
        return -13.0 + (exposure * 12.0)
    
    def _convert_to_camera_gain(self, gain: float) -> float:
        """Convert 0-1 gain value to camera-specific range"""
        # Most cameras use 0-100 range for gain
        return gain * 100.0
    
    def _convert_to_camera_brightness(self, brightness: float) -> float:
        """Convert 0-1 brightness value to camera-specific range"""
        # Most cameras use -100 to 100 range for brightness
        return (brightness - 0.5) * 200.0
    
    def _convert_to_camera_contrast(self, contrast: float) -> float:
        """Convert 0-1 contrast value to camera-specific range"""
        # Most cameras use 0-100 range for contrast
        return contrast * 100.0
    
    def _convert_to_camera_saturation(self, saturation: float) -> float:
        """Convert 0-1 saturation value to camera-specific range"""
        # Most cameras use 0-100 range for saturation
        return saturation * 100.0
    
    def _convert_to_camera_sharpness(self, sharpness: float) -> float:
        """Convert 0-1 sharpness value to camera-specific range"""
        # Most cameras use 0-100 range for sharpness
        return sharpness * 100.0
    
    def _convert_to_camera_white_balance(self, wb: float) -> float:
        """Convert 0-1 white balance value to camera-specific range"""
        # Most cameras use 2000-7000K range for white balance
        return 2000 + (wb * 5000)
    
    def _enhance_frame(self, frame: np.ndarray) -> np.ndarray:
        """Apply image enhancement to improve quality"""
        if not self.config.enhancement.auto_enhance:
            return frame
        
        enhanced_frame = frame.copy()
        
        try:
            # Apply gamma correction to fix overexposure
            if self.config.enhancement.gamma_correction != 1.0:
                # Build lookup table for gamma correction
                gamma = self.config.enhancement.gamma_correction
                inv_gamma = 1.0 / gamma
                table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(256)]).astype("uint8")
                enhanced_frame = cv2.LUT(enhanced_frame, table)
                self.logger.debug(f"Applied gamma correction: {gamma}")
            
            # Apply histogram equalization if enabled
            if self.config.enhancement.histogram_equalization:
                # Convert to LAB color space for better histogram equalization
                lab = cv2.cvtColor(enhanced_frame, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab)
                # Apply histogram equalization to lightness channel
                l = cv2.equalizeHist(l)
                enhanced_frame = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
                self.logger.debug("Applied histogram equalization")
            
            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
            if self.config.enhancement.clahe_enabled:
                # Convert to LAB color space
                lab = cv2.cvtColor(enhanced_frame, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab)
                
                # Create CLAHE object
                clahe = cv2.createCLAHE(
                    clipLimit=self.config.enhancement.clahe_clip_limit,
                    tileGridSize=(self.config.enhancement.clahe_tile_grid_size, 
                                self.config.enhancement.clahe_tile_grid_size)
                )
                
                # Apply CLAHE to lightness channel
                l = clahe.apply(l)
                enhanced_frame = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
                self.logger.debug(f"Applied CLAHE with clip limit {self.config.enhancement.clahe_clip_limit}")
            
        except Exception as e:
            self.logger.error(f"Image enhancement failed: {e}")
            return frame
        
        return enhanced_frame
    
    async def _initialize_camera(self):
        """Initialize camera with enhanced controls and image quality settings"""
        if self.camera_initialized or not self.is_camera_device:
            return
        
        try:
            # For camera devices, create persistent connection
            video_input = int(str(self.video_source))
            self.logger.info(f"Initializing camera device: {video_input}")
            
            self.cap = cv2.VideoCapture(video_input)
            if not self.cap.isOpened():
                self.logger.error(f"Cannot open camera device: {video_input}")
                raise RuntimeError(f"Camera device {video_input} not accessible")
            
            # Set enhanced camera properties for better image quality
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
                    # Convert 0-1 range to camera-specific range
                    exposure_value = self._convert_to_camera_exposure(self.config.camera.exposure)
                    self.cap.set(cv2.CAP_PROP_EXPOSURE, exposure_value)
                    self.logger.info(f"Set manual exposure: {self.config.camera.exposure} -> {exposure_value}")
                else:
                    # Auto exposure mode
                    self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
                    self.logger.debug("Enabled auto exposure")
                
                # Gain control
                if self.config.camera.gain >= 0:
                    gain_value = self._convert_to_camera_gain(self.config.camera.gain)
                    self.cap.set(cv2.CAP_PROP_GAIN, gain_value)
                    self.logger.debug(f"Set manual gain: {self.config.camera.gain} -> {gain_value}")
                
                # Image quality settings
                if hasattr(cv2, 'CAP_PROP_BRIGHTNESS'):
                    brightness_value = self._convert_to_camera_brightness(self.config.camera.brightness)
                    self.cap.set(cv2.CAP_PROP_BRIGHTNESS, brightness_value)
                    self.logger.debug(f"Set brightness: {self.config.camera.brightness} -> {brightness_value}")
                
                if hasattr(cv2, 'CAP_PROP_CONTRAST'):
                    contrast_value = self._convert_to_camera_contrast(self.config.camera.contrast)
                    self.cap.set(cv2.CAP_PROP_CONTRAST, contrast_value)
                    self.logger.debug(f"Set contrast: {self.config.camera.contrast} -> {contrast_value}")
                
                if hasattr(cv2, 'CAP_PROP_SATURATION'):
                    saturation_value = self._convert_to_camera_saturation(self.config.camera.saturation)
                    self.cap.set(cv2.CAP_PROP_SATURATION, saturation_value)
                    self.logger.debug(f"Set saturation: {self.config.camera.saturation} -> {saturation_value}")
                
                if hasattr(cv2, 'CAP_PROP_SHARPNESS'):
                    sharpness_value = self._convert_to_camera_sharpness(self.config.camera.sharpness)
                    self.cap.set(cv2.CAP_PROP_SHARPNESS, sharpness_value)
                    self.logger.debug(f"Set sharpness: {self.config.camera.sharpness} -> {sharpness_value}")
                
                # White balance
                if self.config.camera.white_balance >= 0:
                    self.cap.set(cv2.CAP_PROP_AUTO_WB, 0)  # Manual white balance
                    wb_value = self._convert_to_camera_white_balance(self.config.camera.white_balance)
                    self.cap.set(cv2.CAP_PROP_WB_TEMPERATURE, wb_value)
                    self.logger.debug(f"Set manual white balance: {self.config.camera.white_balance}")
                else:
                    self.cap.set(cv2.CAP_PROP_AUTO_WB, 1)  # Auto white balance
                    self.logger.debug("Enabled auto white balance")
                
            except Exception as prop_error:
                self.logger.warning(f"Could not set all camera properties: {prop_error}")
            
            # Perform camera warm-up routine
            self.logger.info(f"Starting camera warm-up with {self.config.camera.warmup_frames} frames...")
            
            for i in range(self.config.camera.warmup_frames):
                ret, frame = self.cap.read()
                if not ret:
                    self.logger.warning(f"Failed to read warm-up frame {i+1}/{self.config.camera.warmup_frames}")
                    continue
                
                # Small delay between frames to allow camera adjustment
                await asyncio.sleep(0.1)
                
                self.logger.debug(f"Warm-up frame {i+1}/{self.config.camera.warmup_frames} captured")
            
            self.camera_initialized = True
            self.logger.info("Camera initialization and warm-up completed successfully")
            
        except Exception as e:
            self.logger.error(f"Camera initialization failed: {e}")
            if self.cap:
                self.cap.release()
                self.cap = None
            raise
    
    async def _load_model(self):
        """Load YOLO model for detection with auto-download to correct location"""
        if self.model is not None:
            return
        
        try:
            from ultralytics import YOLO
            
            # Load model
            if self.model_path.exists():
                self.logger.info(f"Loading model from: {self.model_path}")
                self.model = YOLO(str(self.model_path))
            else:
                # Auto-download the configured model if missing
                model_name = self.model_path.name  # e.g., "yolo11m.pt"
                self.logger.info(f"Model not found at {self.model_path}, downloading {model_name}")
                
                # Ensure the models directory exists
                self.model_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Download the configured model directly to the correct location
                # Change to the models directory temporarily to download there
                import os
                original_cwd = os.getcwd()
                try:
                    os.chdir(str(self.model_path.parent))
                    self.model = YOLO(model_name)  # Downloads to current directory (models/)
                    self.logger.info(f"Downloaded and loaded model: {self.model_path}")
                finally:
                    os.chdir(original_cwd)
                
                # Verify the model was downloaded to the correct location
                if not self.model_path.exists():
                    # If download didn't work as expected, try fallback approach
                    self.logger.warning(f"Model download to {self.model_path} failed, trying fallback")
                    self.model = YOLO(model_name)  # Download to current directory
                    
                    # Move if downloaded to wrong location
                    downloaded_path = Path(model_name)
                    if downloaded_path.exists():
                        downloaded_path.rename(self.model_path)
                        self.logger.info(f"Moved downloaded model to: {self.model_path}")
                    else:
                        self.logger.warning(f"Failed to download {model_name}, using default yolo11n.pt")
                        self.model = YOLO("yolo11n.pt")  # Fallback to smaller model
            
            # Move to optimal device
            if hasattr(self.model, 'to'):
                self.model.to(self.device)
            
            self.stats["model_loaded"] = True
            self.logger.info(f"Model loaded successfully on device: {self.device}")
            
        except Exception as e:
            self.logger.error(f"Model loading failed: {e}")
            self.stats["model_loaded"] = False
            raise
    
    def _capture_frame(self) -> Optional[np.ndarray]:
        """Capture single frame from video source"""
        try:
            video_source_str = str(self.video_source)
            
            if self.is_camera_device:
                # Use persistent camera connection
                if not self.camera_initialized or self.cap is None:
                    self.logger.error("Camera not initialized. Call _initialize_camera() first.")
                    return None
                
                # Read from persistent connection
                ret, frame = self.cap.read()
                if not ret:
                    self.logger.warning("Failed to read frame from persistent camera connection")
                    # Try to reinitialize camera on failure
                    try:
                        self.logger.info("Attempting camera reconnection...")
                        self._reinitialize_camera_sync()
                        ret, frame = self.cap.read() if self.cap else (False, None)
                        if not ret:
                            return None
                    except Exception as reconnect_error:
                        self.logger.error(f"Camera reconnection failed: {reconnect_error}")
                        return None
                
                self.logger.debug(f"Captured frame from persistent camera connection")
                
            else:
                # For video files, use the original approach (open/read/close)
                if not self.video_source.exists():
                    self.logger.warning(f"Video source not found: {self.video_source}")
                    return None
                
                video_input = str(self.video_source)
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
            
            # Apply camera mirroring if enabled and using a camera device
            if self.config.camera.mirror and self.is_camera_device:
                frame = cv2.flip(frame, 1)  # Horizontal flip
                self.logger.debug("Applied camera mirror (horizontal flip)")
            
            # Apply image enhancement for better quality
            if self.is_camera_device:
                frame = self._enhance_frame(frame)
            
            # Store current frame for raw access
            self.current_frame = frame.copy()
            
            return frame
            
        except Exception as e:
            self.logger.error(f"Frame capture failed: {e}")
            return None
    
    def _reinitialize_camera_sync(self):
        """Synchronous camera reinitialization for use in _capture_frame"""
        try:
            if self.cap:
                self.cap.release()
            
            video_input = int(str(self.video_source))
            self.cap = cv2.VideoCapture(video_input)
            
            if not self.cap.isOpened():
                raise RuntimeError(f"Cannot reopen camera device: {video_input}")
            
            # Reapply camera settings
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
    
    def _detect_vehicles(self, frame: np.ndarray) -> List[VehicleDetection]:
        """Run YOLO detection on frame"""
        try:
            if self.model is None:
                return []
            
            # Run inference
            results = self.model(frame, conf=self.config.processing.confidence_threshold, verbose=False)
            
            detections = []
            for result in results:
                if hasattr(result, 'boxes') and result.boxes is not None:
                    for box in result.boxes:
                        # Extract detection data
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        conf = box.conf[0].cpu().numpy()
                        cls = int(box.cls[0].cpu().numpy())
                        
                        # Filter for vehicle classes (assuming COCO classes)
                        vehicle_classes = [2, 3, 5, 7]  # car, motorcycle, bus, truck
                        if cls in vehicle_classes:
                            detection = VehicleDetection(
                                x=int(x1),
                                y=int(y1),
                                width=int(x2 - x1),
                                height=int(y2 - y1),
                                confidence=float(conf),
                                class_name="vehicle"
                            )
                            detections.append(detection)
            
            return detections
            
        except Exception as e:
            self.logger.error(f"Vehicle detection failed: {e}")
            return []
    
    def _analyze_parking_zones(self, detections: List[VehicleDetection]) -> List[Dict[str, Any]]:
        """Analyze which parking zones are occupied with improved detection logic"""
        zones_status = []
        
        # Only process detections that overlap with defined zones (ignore outside detections)
        zone_detections = []
        
        for zone in self.config.parking_zones:
            occupied = False
            best_confidence = 0.0
            zone_detection_count = 0
            
            # Check if any detection overlaps with this zone
            zone_coords = zone.coordinates
            if len(zone_coords) >= 3:  # Need at least 3 points for polygon
                # Use polygon containment check for more accurate detection
                zone_polygon_points = np.array(zone_coords, dtype=np.int32)
                
                for detection in detections:
                    # Calculate detection center point
                    det_center_x = detection.x + detection.width // 2
                    det_center_y = detection.y + detection.height // 2
                    
                    # Check if detection center is inside zone polygon
                    inside = cv2.pointPolygonTest(zone_polygon_points, 
                                                (det_center_x, det_center_y), False)
                    
                    if inside >= 0:  # Point is inside or on the polygon
                        zone_detection_count += 1
                        detection.zone_id = zone.id
                        zone_detections.append(detection)
                        
                        # Apply detection difficulty adjustment
                        adjusted_confidence = self._adjust_confidence_by_difficulty(
                            detection.confidence, zone.detection_difficulty.value if hasattr(zone.detection_difficulty, "value") else zone.detection_difficulty
                        )
                        
                        # Use lower threshold for hard zones to improve detection
                        difficulty_value = (zone.detection_difficulty.value 
                                          if hasattr(zone.detection_difficulty, "value") 
                                          else zone.detection_difficulty)
                        threshold = (self.config.processing.confidence_threshold * 0.7 
                                   if difficulty_value == "hard" 
                                   else self.config.processing.confidence_threshold)
                        
                        if adjusted_confidence >= threshold:
                            occupied = True
                            best_confidence = max(best_confidence, adjusted_confidence)
            
            # Update zone status
            self.config.update_zone_status(zone.id, occupied, best_confidence)
            
            zones_status.append({
                "id": zone.id,
                "space_id": zone.space_id,
                "name": zone.name,
                "description": zone.description,
                "occupied": occupied,
                "confidence": best_confidence,
                "coordinates": zone.coordinates,
                "detection_difficulty": zone.detection_difficulty.value if hasattr(zone.detection_difficulty, "value") else zone.detection_difficulty,
                "detection_count": zone_detection_count
            })
        
        # Log ignored detections (outside all zones)
        ignored_detections = [d for d in detections if d.zone_id is None]
        if ignored_detections:
            self.logger.debug(f"Ignored {len(ignored_detections)} detections outside defined zones")
        
        return zones_status
    
    def _adjust_confidence_by_difficulty(self, confidence: float, difficulty: str) -> float:
        """Adjust detection confidence based on zone detection difficulty"""
        if difficulty == "easy":
            # Boost confidence for easy zones
            return min(1.0, confidence * 1.1)
        elif difficulty == "hard":
            # Boost confidence for hard zones to improve detection
            return min(1.0, confidence * 1.2)
        else:
            # Normal zones - no adjustment
            return confidence
    
    def _draw_overlay(self, frame: np.ndarray, detections: List[VehicleDetection], 
                     zones_status: List[Dict[str, Any]]) -> np.ndarray:
        """Draw detection and zone overlays on frame"""
        overlay_frame = frame.copy()
        
        try:
            # Draw parking zones with improved visualization
            for zone in zones_status:
                coords = zone["coordinates"]
                if len(coords) >= 3:
                    # Convert to numpy array for drawing
                    points = np.array(coords, dtype=np.int32)
                    
                    # Choose color based on occupancy and difficulty
                    if zone["occupied"]:
                        color = (0, 0, 255)  # Red if occupied
                    elif zone["detection_difficulty"] == "hard":
                        color = (0, 165, 255)  # Orange for hard zones
                    else:
                        color = (0, 255, 0)  # Green if free
                    
                    # Draw zone boundary
                    cv2.polylines(overlay_frame, [points], True, color, 2)
                    
                    # Add zone label with better positioning
                    label_x = min(coord[0] for coord in coords) + 5
                    label_y = min(coord[1] for coord in coords) - 5
                    cv2.putText(overlay_frame, f"{zone['name']}", 
                              (label_x, max(15, label_y)),  # Ensure label stays within bounds
                              cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                    
                    # Add detection count for debugging
                    if zone["detection_count"] > 0:
                        count_y = label_y + 20 if label_y > 20 else label_y + 35
                        cv2.putText(overlay_frame, f"Det: {zone['detection_count']}", 
                                  (label_x, count_y),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
            
            # Draw vehicle detections
            for detection in detections:
                # Draw bounding box
                cv2.rectangle(overlay_frame, 
                            (detection.x, detection.y), 
                            (detection.x + detection.width, detection.y + detection.height),
                            (255, 255, 0), 2)  # Yellow for vehicles
                
                # Add confidence label
                label = f"Vehicle: {detection.confidence:.2f}"
                cv2.putText(overlay_frame, label,
                          (detection.x, detection.y - 5),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
            
            # Add timestamp and stats
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(overlay_frame, timestamp, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Add occupancy info with zone breakdown
            occupied_count = sum(1 for zone in zones_status if zone["occupied"])
            total_zones = len(zones_status)
            easy_zones = len([z for z in zones_status if z["detection_difficulty"] == "easy"])
            hard_zones = len([z for z in zones_status if z["detection_difficulty"] == "hard"])
            
            occupancy_text = f"Occupied: {occupied_count}/{total_zones} (Easy: {easy_zones}, Hard: {hard_zones})"
            cv2.putText(overlay_frame, occupancy_text, (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
        except Exception as e:
            self.logger.error(f"Overlay drawing failed: {e}")
        
        return overlay_frame
    
    async def process_snapshot(self) -> Optional[SnapshotResult]:
        """Process a single snapshot and return results"""
        start_time = time.time()
        
        try:
            # Load model if needed
            if self.model is None:
                await self._load_model()
            
            # Initialize camera if needed (for camera devices only)
            if self.is_camera_device and not self.camera_initialized:
                await self._initialize_camera()
            
            # Capture frame
            frame = self._capture_frame()
            if frame is None:
                return None
            
            # Detect vehicles
            detections = self._detect_vehicles(frame)
            
            # Analyze parking zones
            zones_status = self._analyze_parking_zones(detections)
            
            # Create overlay image
            overlay_frame = self._draw_overlay(frame, detections, zones_status)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Update statistics
            self._update_stats(detections, zones_status)
            
            # Create result
            result = SnapshotResult(
                image=overlay_frame,
                detections=detections,
                timestamp=time.time(),
                zones_status=zones_status,
                processing_time=processing_time
            )
            
            self.last_snapshot = result
            self.config.mark_snapshot_processed()
            
            self.logger.debug(f"Snapshot processed in {processing_time:.2f}s, "
                            f"{len(detections)} vehicles detected")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Snapshot processing failed: {e}")
            return None
    
    def _update_stats(self, detections: List[VehicleDetection], zones_status: List[Dict[str, Any]]):
        """Update internal statistics"""
        self.stats["total_frames"] += 1
        self.stats["detections"] = len(detections)
        self.stats["vehicles_detected"] = len(detections)
        self.stats["last_update"] = datetime.now().isoformat()
        
        if detections:
            self.stats["last_detection"] = datetime.now().isoformat()
        
        # Update occupancy stats
        occupied_count = sum(1 for zone in zones_status if zone["occupied"])
        self.stats["occupied_spaces"] = occupied_count
        self.stats["occupancy_rate"] = occupied_count / len(zones_status) if zones_status else 0.0
        
        # Simple FPS calculation (inverse of snapshot interval)
        self.stats["processing_fps"] = 1.0 / self.config.processing.snapshot_interval
    
    async def start_snapshot_loop(self):
        """Start the snapshot processing loop"""
        self.running = True
        self.logger.info("Starting snapshot processing loop...")
        
        while self.running:
            try:
                if self.config.should_process_snapshot():
                    await self.process_snapshot()
                
                # Sleep for 1 second before checking again
                await asyncio.sleep(1.0)
                
            except Exception as e:
                self.logger.error(f"Snapshot loop error: {e}")
                await asyncio.sleep(5.0)  # Wait longer on error
        
        self.logger.info("Snapshot processing loop stopped")
    
    async def stop(self):
        """Stop the detector and clean up resources"""
        self.running = False
        
        # Clean up camera resources
        if self.cap is not None:
            try:
                self.cap.release()
                self.logger.info("Camera connection released")
            except Exception as e:
                self.logger.error(f"Error releasing camera: {e}")
            finally:
                self.cap = None
                self.camera_initialized = False
        
        # Clean up model resources if needed
        if self.model is not None:
            try:
                # YOLO models don't require explicit cleanup, but clear reference
                self.model = None
                self.logger.info("Model resources cleaned up")
            except Exception as e:
                self.logger.error(f"Error cleaning up model: {e}")
        
        self.logger.info("Detector stopped and resources cleaned up")
    
    def get_last_snapshot_image(self) -> Optional[bytes]:
        """Get last processed snapshot as JPEG bytes"""
        if self.last_snapshot is None:
            return None
        
        try:
            # Encode as JPEG
            _, buffer = cv2.imencode('.jpg', self.last_snapshot.image)
            return buffer.tobytes()
        except Exception as e:
            self.logger.error(f"Image encoding failed: {e}")
            return None
    
    def get_raw_frame_image(self) -> Optional[bytes]:
        """Get current raw frame (without overlays) as JPEG bytes"""
        # Try to capture a fresh frame first
        fresh_frame = self._capture_frame()
        frame_to_use = fresh_frame if fresh_frame is not None else self.current_frame
        
        if frame_to_use is None:
            return None
        
        try:
            # Encode as JPEG
            _, buffer = cv2.imencode('.jpg', frame_to_use)
            return buffer.tobytes()
        except Exception as e:
            self.logger.error(f"Raw frame encoding failed: {e}")
            return None
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get current detection statistics"""
        # Use new config system methods
        return {
            **self.stats,
            "snapshot_interval": self.config.processing.snapshot_interval,
            "last_snapshot_epoch": self.config.last_snapshot_epoch,
            "total_zones": self.config.get_total_zones(),
            "occupied_zones": sum(1 for zone in self.config.parking_zones if zone.occupied),
            "available_zones": sum(1 for zone in self.config.parking_zones if not zone.occupied),
            "occupancy_rate": (sum(1 for zone in self.config.parking_zones if zone.occupied) / 
                             max(1, self.config.get_total_zones())),
            "last_update_epoch": self.config.last_snapshot_epoch,
            "video_source": str(self.video_source)
        }
    
    async def get_parking_spaces(self) -> Dict[str, Any]:
        """Get parking spaces data"""
        zones_data = self.config.get_zones_data()
        
        spaces = []
        for zone in zones_data:
            # Convert zone to space format for compatibility
            coords = zone["coordinates"]
            if len(coords) >= 4:
                x = min(coord[0] for coord in coords)
                y = min(coord[1] for coord in coords)
                width = max(coord[0] for coord in coords) - x
                height = max(coord[1] for coord in coords) - y
                
                spaces.append({
                    "id": zone["id"],
                    "occupied": zone["occupied"],
                    "confidence": zone["confidence"],
                    "coordinates": [x, y, width, height]
                })
        
        return {
            "spaces": spaces,
            "total_spaces": len(spaces),
            "occupied_count": sum(1 for space in spaces if space["occupied"]),
            "available_count": sum(1 for space in spaces if not space["occupied"])
        }
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        return {
            "device_info": self.stats["device_info"],
            "processing": {
                "snapshot_interval": self.config.processing.snapshot_interval,
                "last_processing_time": self.last_snapshot.processing_time if self.last_snapshot else 0.0,
                "model_loaded": self.stats["model_loaded"]
            },
            "system": {
                "memory_usage_gb": self._get_memory_usage(),
                "temperature": self._get_system_temperature()
            }
        }
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in GB"""
        try:
            import psutil
            return psutil.virtual_memory().used / (1024**3)
        except:
            return 0.0
    
    def _get_system_temperature(self) -> float:
        """Get system temperature if available"""
        try:
            if self.is_apple_silicon:
                # Try to read temperature on macOS
                import subprocess
                result = subprocess.run(['sysctl', 'machdep.xcpm.cpu_thermal_state'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    return float(result.stdout.split(':')[1].strip())
        except:
            pass
        return 0.0