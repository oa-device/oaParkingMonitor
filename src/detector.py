"""
MVP Snapshot-Based Parking Detector
Simplified detection engine that processes one frame every 5 seconds
"""

import asyncio
import logging
import time
import cv2
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import platform
from dataclasses import dataclass

from .config import MVPConfigManager, MVPConfig, ParkingZone


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
    """Simplified MVP parking detector with snapshot processing"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.running = False
        
        # Load MVP configuration
        self.config_manager = MVPConfigManager()
        self.config = self.config_manager.config
        
        # Video source setup - handle both camera devices and file paths
        if self.config.video_source.isdigit():
            self.video_source = self.config.video_source  # Keep as string for camera device
        else:
            self.video_source = Path(self.config.video_source)  # Convert to Path for file
        self.model_path = Path.home() / "orangead" / "parking-monitor" / self.config.model_path
        
        # Device detection
        self.device = self._detect_optimal_device()
        self.is_apple_silicon = self._is_apple_silicon()
        
        # Detection state
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
        self.logger.info(f"Snapshot interval: {self.config.snapshot_interval} seconds")
    
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
    
    async def _load_model(self):
        """Load YOLO model for detection"""
        if self.model is not None:
            return
        
        try:
            from ultralytics import YOLO
            
            # Load model
            if self.model_path.exists():
                self.logger.info(f"Loading model from: {self.model_path}")
                self.model = YOLO(str(self.model_path))
            else:
                self.logger.warning(f"Model not found at {self.model_path}, using default")
                self.model = YOLO("yolo11n.pt")  # Smaller default model
            
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
            # Determine if video source is a camera device or file path
            video_source_str = str(self.video_source)
            
            # If it's a digit (camera device), convert to int
            if video_source_str.isdigit():
                video_input = int(video_source_str)
                self.logger.debug(f"Using camera device: {video_input}")
            else:
                # It's a file path, check if it exists
                if not self.video_source.exists():
                    self.logger.warning(f"Video source not found: {self.video_source}")
                    return None
                video_input = str(self.video_source)
                self.logger.debug(f"Using video file: {video_input}")
            
            # Open video capture
            cap = cv2.VideoCapture(video_input)
            if not cap.isOpened():
                self.logger.error(f"Cannot open video source: {video_input}")
                return None
            
            # Read frame
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                self.logger.warning("Failed to read frame from video source")
                return None
            
            return frame
            
        except Exception as e:
            self.logger.error(f"Frame capture failed: {e}")
            return None
    
    def _detect_vehicles(self, frame: np.ndarray) -> List[VehicleDetection]:
        """Run YOLO detection on frame"""
        try:
            if self.model is None:
                return []
            
            # Run inference
            results = self.model(frame, conf=self.config.confidence_threshold, verbose=False)
            
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
                            detection.confidence, zone.detection_difficulty
                        )
                        
                        if adjusted_confidence >= self.config.confidence_threshold:
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
                "detection_difficulty": zone.detection_difficulty,
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
            # Reduce confidence for hard zones (more conservative)
            return confidence * 0.9
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
        self.stats["processing_fps"] = 1.0 / self.config.snapshot_interval
    
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
        """Stop the detector"""
        self.running = False
        self.logger.info("Detector stopped")
    
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
        if self.current_frame is None:
            return None
        
        try:
            # Encode as JPEG
            _, buffer = cv2.imencode('.jpg', self.current_frame)
            return buffer.tobytes()
        except Exception as e:
            self.logger.error(f"Raw frame encoding failed: {e}")
            return None
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get current detection statistics"""
        # Add config data to stats
        occupancy_summary = self.config.get_occupancy_summary()
        
        return {
            **self.stats,
            "snapshot_interval": self.config.snapshot_interval,
            "last_snapshot_epoch": self.config.last_snapshot_epoch,
            "total_zones": occupancy_summary["total_zones"],
            "occupied_zones": occupancy_summary["occupied_zones"],
            "available_zones": occupancy_summary["available_zones"],
            "occupancy_rate": occupancy_summary["occupancy_rate"],
            "last_update_epoch": occupancy_summary["last_update"]
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
                "snapshot_interval": self.config.snapshot_interval,
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


# Alias for backward compatibility with main.py
ParkingDetector = MVPParkingDetector


# Legacy compatibility classes for existing API code
class ParkingSpace:
    """Legacy parking space for compatibility"""
    def __init__(self, space_id: int, x: int, y: int, width: int, height: int, label: str = ""):
        self.id = space_id
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.label = label
        self.occupied = False
        self.confidence = 0.0