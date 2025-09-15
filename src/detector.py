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
from .detection import VehicleDetector, ZoneAnalyzer, ImagePreprocessor
from .camera import CameraManager
from .analysis import ZoneAnalysisAdapter
from .core import TemporalSmoother, DetectionTracker, VehicleTracker


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
    
    def __init__(self, config=None):
        self.logger = logging.getLogger(__name__)
        self.running = False
        
        # Use provided config or load configuration using new system
        if config is not None:
            self.config = config
            self.config_manager = None  # Using external config
        else:
            self.config_manager = ConfigManager()
            self.config = self.config_manager.config
        
        # Video source setup - handle both camera devices and file paths
        video_source_str = str(self.config.video.source)
        if video_source_str.isdigit():
            self.video_source = self.config.video.source  # Keep as string for camera device
        else:
            self.video_source = Path(self.config.video.source)  # Convert to Path for file
        # Use centralized path management for models
        from .utils.paths import get_data_paths
        data_paths = get_data_paths()
        self.model_path = data_paths.base_data_dir.parent / "oaParkingMonitor" / self.config.processing.model_path
        
        # Device detection
        self.device = self._detect_optimal_device()
        self.is_apple_silicon = self._is_apple_silicon()
        
        # Initialize modular detection components
        self.vehicle_detector = VehicleDetector(str(self.model_path), str(self.device))
        self.zone_analyzer = ZoneAnalyzer()
        self.preprocessor = ImagePreprocessor()
        self.camera_manager = CameraManager(self.config, self.video_source)
        self.zone_analysis_adapter = ZoneAnalysisAdapter(self.zone_analyzer, self.logger)
        
        # Initialize temporal smoothing and tracking for persistence
        self.temporal_smoother = TemporalSmoother(history_size=5, hysteresis_threshold=0.6)
        self.detection_tracker = DetectionTracker(window_size=60)
        self.vehicle_tracker = VehicleTracker(max_missed_frames=3)
        
        # Legacy detection state (for compatibility)
        self.model = None
        self.last_snapshot: Optional[SnapshotResult] = None
        self.current_frame: Optional[np.ndarray] = None
        
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
        if config is not None:
            self.logger.info("Using shared configuration from service")
    
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
    

    
    async def _load_model(self):
        """Load YOLO model for detection using modular vehicle detector"""
        if self.vehicle_detector.is_loaded():
            return
        
        try:
            # Load model using the modular vehicle detector
            success = self.vehicle_detector.load_model()
            
            if success:
                self.stats["model_loaded"] = True
                self.logger.info(f"Model loaded successfully via vehicle detector on device: {self.device}")
                # Keep legacy model reference for compatibility
                self.model = self.vehicle_detector.model
            else:
                self.stats["model_loaded"] = False
                self.logger.error("Model loading failed via vehicle detector")
                raise RuntimeError("Vehicle detector failed to load model")
            
        except Exception as e:
            self.logger.error(f"Model loading failed: {e}")
            self.stats["model_loaded"] = False
            raise
    

    

    
    def _detect_vehicles(self, frame: np.ndarray) -> List[VehicleDetection]:
        """Run vehicle detection using multi-scale detection with temporal tracking"""
        try:
            if not self.vehicle_detector.is_loaded():
                return []
            
            # Apply preprocessing for better detection accuracy
            processed_frame = self.preprocessor.preprocess_frame(
                frame, 
                zones=self.config.parking_zones,
                enhance_edge_zones=True
            )
            
            # Use multi-scale detection for better accuracy
            detections_data = self.vehicle_tracker.detect_multi_scale(
                processed_frame,
                self.vehicle_detector,
                base_confidence=self.config.processing.confidence_threshold
            )
            
            # Track vehicles across frames
            tracked_detections = self.vehicle_tracker.track_vehicles(
                detections_data,
                timestamp=time.time()
            )
            
            # Convert to legacy VehicleDetection format for compatibility
            detections = []
            for det_data in tracked_detections:
                x1, y1, x2, y2 = det_data["bbox"]
                detection = VehicleDetection(
                    x=int(x1),
                    y=int(y1),
                    width=int(x2 - x1),
                    height=int(y2 - y1),
                    confidence=float(det_data["confidence"]),
                    class_name="vehicle",
                    zone_id=det_data.get("zone_id")
                )
                detections.append(detection)
            
            self.logger.debug(f"Multi-scale detection found {len(detections)} vehicles")
            return detections
            
        except Exception as e:
            self.logger.error(f"Vehicle detection failed: {e}")
            return []
    
    def _analyze_parking_zones(self, detections: List[VehicleDetection]) -> List[Dict[str, Any]]:
        """Analyze parking zones with temporal smoothing for persistence"""
        # First pass: basic zone analysis
        initial_zones = self.zone_analysis_adapter.analyze_parking_zones(detections, self.config)
        
        # Convert detections to dict format for temporal smoothing
        detection_dicts = []
        for det in detections:
            detection_dicts.append({
                "bbox": [det.x, det.y, det.x + det.width, det.y + det.height],
                "confidence": det.confidence,
                "zone_id": det.zone_id,
                "center": [det.x + det.width/2, det.y + det.height/2]
            })
        
        # Apply temporal smoothing for persistence
        zone_configs = [
            {
                "id": zone.id,
                "space_id": zone.space_id,
                "name": zone.name,
                "coordinates": zone.coordinates,
                "detection_difficulty": zone.detection_difficulty
            }
            for zone in self.config.parking_zones
        ]
        
        _, smoothed_zones = self.temporal_smoother.smooth_detections(
            detection_dicts, zone_configs
        )
        
        # Merge smoothed results with initial analysis
        enhanced_zones = []
        for zone in initial_zones:
            zone_id = zone["id"]
            if zone_id in smoothed_zones:
                # Use smoothed state for better persistence
                zone["occupied"] = smoothed_zones[zone_id]["occupied"]
                zone["confidence"] = smoothed_zones[zone_id]["confidence"]
                zone["stable_frames"] = smoothed_zones[zone_id]["stable_frames"]
                zone["temporal_smoothed"] = True
            enhanced_zones.append(zone)
        
        # Track detection patterns
        for zone in enhanced_zones:
            self.detection_tracker.track_detection(
                zone["id"], zone["occupied"], time.time()
            )
        
        self.logger.debug(f"Temporal smoothing applied to {len(enhanced_zones)} zones")
        return enhanced_zones
    

    
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
            
            # Initialize camera if needed
            await self.camera_manager.initialize()
            
            # Capture frame
            frame = self.camera_manager.capture_frame()
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
            
            # Save snapshot image for airport demo
            snapshot_epoch = int(time.time())
            self._save_snapshot_image(overlay_frame, snapshot_epoch)
            
            # Create result
            result = SnapshotResult(
                image=overlay_frame,
                detections=detections,
                timestamp=snapshot_epoch,  # Use epoch timestamp
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
        # Note: occupancy_rate calculation moved to frontend
        
        # Simple FPS calculation (inverse of snapshot interval)
        self.stats["processing_fps"] = 1.0 / self.config.processing.snapshot_interval

    
    def _save_snapshot_image(self, image: np.ndarray, epoch: int) -> bool:
        """
        Save snapshot image to disk for airport demo.
        
        Args:
            image: Processed image with overlays
            epoch: Epoch timestamp for filename
            
        Returns:
            True if successful
        """
        try:
            # Import at method level to avoid circular imports
            from .utils.paths import save_snapshot_image
            import cv2
            
            # Encode image as JPEG
            success, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 95])
            if not success:
                self.logger.error(f"Failed to encode image for epoch {epoch}")
                return False
            
            # Save using centralized path management
            image_bytes = buffer.tobytes()
            saved = save_snapshot_image(epoch, image_bytes)
            
            if saved:
                self.logger.debug(f"Saved snapshot image for epoch {epoch}")
            else:
                self.logger.warning(f"Failed to save snapshot image for epoch {epoch}")
            
            return saved
            
        except Exception as e:
            self.logger.error(f"Error saving snapshot image for epoch {epoch}: {e}")
            return False
    
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
        self.camera_manager.release()
        
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
        fresh_frame = self.camera_manager.capture_frame()
        frame_to_use = fresh_frame if fresh_frame is not None else self.camera_manager.get_current_frame()
        
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