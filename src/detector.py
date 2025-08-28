"""
Simplified Parking Detector
Combines working staging logic with YOLOv11 integration
"""

import asyncio
import logging
import time
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import cv2
import numpy as np
from ultralytics import YOLO

from .config import ConfigManager, ParkingSpaceConfig


class ParkingSpace:
    """Represents a parking space with detection state"""
    
    def __init__(self, space_id: int, x: int, y: int, width: int, height: int):
        self.space_id = space_id
        self.x = x
        self.y = y  
        self.width = width
        self.height = height
        self.occupied = False
        self.confidence = 0.0
        self.last_detection = None
        self.vehicle_type = None


class VehicleDetection:
    """Represents a detected vehicle"""
    
    def __init__(self, x: int, y: int, width: int, height: int, confidence: float, class_name: str):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.confidence = confidence
        self.class_name = class_name
        self.detection_time = datetime.now()


class ParkingDetector:
    """Simplified parking detection with YOLOv11 integration"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.running = False
        
        # Load configuration
        self.config_manager = ConfigManager()
        self.config = self.config_manager.config
        
        # Paths and configuration
        self.base_dir = Path.home() / "orangead" / "parking-monitor"
        self.video_source = Path(self.config.video.source_path)
        self.model_path = self.base_dir / self.config.detection.model_path
        
        # Detection state
        self.model = None
        self.parking_spaces = self._initialize_parking_spaces()
        self.current_detections: List[VehicleDetection] = []
        
        # Statistics (compatible with staging format)
        self.stats = {
            "total_frames": 0,
            "detections": 0, 
            "vehicles_detected": 0,
            "processing_fps": 0.0,
            "uptime_start": datetime.now().isoformat(),
            "last_update": datetime.now().isoformat(),
            "total_spaces": len(self.parking_spaces),
            "occupied_spaces": 0,
            "occupancy_rate": 0.0,
            "video_source": str(self.video_source),
            "model_loaded": False
        }
        
        # Model will be loaded on first use
        
    def _initialize_parking_spaces(self) -> List[ParkingSpace]:
        """Initialize parking space definitions from configuration"""
        spaces = []
        for space_config in self.config.spaces:
            spaces.append(ParkingSpace(
                space_config.space_id, 
                space_config.x, 
                space_config.y, 
                space_config.width, 
                space_config.height
            ))
        return spaces
    
    async def _load_model(self):
        """Load YOLOv11 model asynchronously"""
        try:
            if self.model_path.exists():
                self.logger.info(f"Loading YOLOv11 model from {self.model_path}")
                self.model = YOLO(str(self.model_path))
                self.stats["model_loaded"] = True
                self.logger.info("YOLOv11 model loaded successfully")
            else:
                self.logger.warning(f"Model not found at {self.model_path}, downloading...")
                self.model = YOLO("yolo11m.pt")  # Will download if not exists
                # Save for future use
                self.model_path.parent.mkdir(parents=True, exist_ok=True)
                self.model.save(str(self.model_path))
                self.stats["model_loaded"] = True
                self.logger.info("YOLOv11 model downloaded and loaded")
        except Exception as e:
            self.logger.error(f"Failed to load YOLO model: {e}")
            self.stats["model_loaded"] = False
    
    async def process_video_stream(self):
        """Main video processing loop (compatible with staging approach)"""
        self.running = True
        self.logger.info("Starting video processing...")
        
        # Load model when starting processing
        if self.model is None:
            await self._load_model()
        
        frame_count = 0
        last_fps_time = time.time()
        
        while self.running:
            try:
                # Check video source
                if not self.video_source.exists():
                    self.logger.warning(f"Video source not found: {self.video_source}")
                    await asyncio.sleep(2)
                    continue
                
                # Open video capture
                cap = cv2.VideoCapture(str(self.video_source))
                if not cap.isOpened():
                    self.logger.error(f"Cannot open video: {self.video_source}")
                    await asyncio.sleep(2)
                    continue
                
                self.logger.info(f"Processing video: {self.video_source}")
                video_frame_count = 0
                
                while self.running and cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        self.logger.info("Video ended, restarting...")
                        break
                    
                    # Update frame statistics  
                    frame_count += 1
                    video_frame_count += 1
                    self.stats["total_frames"] += 1
                    
                    # Process detection (every 3rd frame for performance)
                    if video_frame_count % 3 == 0:
                        await self._process_frame(frame)
                    
                    # Update FPS calculation
                    if frame_count % 30 == 0:
                        current_time = time.time()
                        fps = 30 / (current_time - last_fps_time)
                        self.stats["processing_fps"] = round(fps, 2)
                        last_fps_time = current_time
                        
                        await self._update_stats()
                        self.logger.debug(f"Processed {frame_count} frames, FPS: {fps:.2f}")
                    
                    # Control processing speed (maintain ~10 FPS like staging)
                    await asyncio.sleep(0.1)
                
                cap.release()
                
            except Exception as e:
                self.logger.error(f"Video processing error: {e}")
                await asyncio.sleep(2)
    
    async def _process_frame(self, frame: np.ndarray):
        """Process a single frame for vehicle detection"""
        try:
            if self.model is None:
                # Fallback to simple simulation like staging code
                await self._simulate_detection()
                return
            
            # Run YOLO inference  
            results = self.model(frame, verbose=False)
            
            # Extract vehicle detections from configuration
            vehicle_classes = self.config.detection.vehicle_classes
            detections = []
            
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        class_id = int(box.cls[0])
                        class_name = self.model.names[class_id]
                        
                        if class_name in vehicle_classes:
                            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                            confidence = float(box.conf[0])
                            
                            if confidence > self.config.detection.confidence_threshold:
                                detections.append(VehicleDetection(
                                    int(x1), int(y1), int(x2-x1), int(y2-y1),
                                    confidence, class_name
                                ))
            
            # Update parking space occupancy
            await self._update_parking_spaces(detections)
            self.current_detections = detections
            
            # Update statistics
            self.stats["detections"] += 1
            self.stats["vehicles_detected"] = len(detections)
            
        except Exception as e:
            self.logger.error(f"Frame processing error: {e}")
            # Fallback to simulation
            await self._simulate_detection()
    
    async def _simulate_detection(self):
        """Fallback simulation when YOLO model unavailable (like staging)"""
        # Simple simulation similar to staging code
        self.stats["detections"] += 1
        
        # Simulate 0-4 vehicles like staging
        vehicles_count = random.randint(0, 4)
        self.stats["vehicles_detected"] = vehicles_count
        
        # Update parking spaces
        for i, space in enumerate(self.parking_spaces):
            space.occupied = i < vehicles_count
            space.confidence = 0.8 if space.occupied else 0.0
        
        await self._update_occupancy_stats()
    
    async def _update_parking_spaces(self, detections: List[VehicleDetection]):
        """Update parking space occupancy based on detections"""
        # Reset all spaces
        for space in self.parking_spaces:
            space.occupied = False
            space.confidence = 0.0
            space.vehicle_type = None
        
        # Check for vehicle overlap with parking spaces
        for detection in detections:
            for space in self.parking_spaces:
                # Simple overlap detection
                if self._rectangles_overlap(
                    detection.x, detection.y, detection.width, detection.height,
                    space.x, space.y, space.width, space.height
                ):
                    space.occupied = True
                    space.confidence = detection.confidence
                    space.vehicle_type = detection.class_name
                    space.last_detection = detection.detection_time
        
        await self._update_occupancy_stats()
    
    def _rectangles_overlap(self, x1, y1, w1, h1, x2, y2, w2, h2) -> bool:
        """Check if two rectangles overlap"""
        return (x1 < x2 + w2 and x1 + w1 > x2 and 
                y1 < y2 + h2 and y1 + h1 > y2)
    
    async def _update_occupancy_stats(self):
        """Update occupancy statistics"""
        occupied_count = sum(1 for space in self.parking_spaces if space.occupied)
        total_spaces = len(self.parking_spaces)
        
        self.stats["occupied_spaces"] = occupied_count
        self.stats["total_spaces"] = total_spaces
        self.stats["occupancy_rate"] = occupied_count / total_spaces if total_spaces > 0 else 0.0
    
    async def _update_stats(self):
        """Update general statistics"""
        self.stats["last_update"] = datetime.now().isoformat()
        
        # Calculate uptime
        start_time = datetime.fromisoformat(self.stats["uptime_start"])
        uptime = datetime.now() - start_time
        self.stats["uptime_seconds"] = uptime.total_seconds()
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get current detection statistics"""
        await self._update_stats()
        return self.stats.copy()
    
    async def get_parking_spaces(self) -> List[Dict[str, Any]]:
        """Get current parking space status"""
        spaces_data = []
        for space in self.parking_spaces:
            spaces_data.append({
                "space_id": space.space_id,
                "occupied": space.occupied,
                "confidence": space.confidence,
                "vehicle_type": space.vehicle_type,
                "last_detection": space.last_detection.isoformat() if space.last_detection else None,
                "bounds": {
                    "x": space.x,
                    "y": space.y, 
                    "width": space.width,
                    "height": space.height
                }
            })
        return spaces_data
    
    async def get_detections(self) -> List[Dict[str, Any]]:
        """Get current vehicle detections"""
        detections_data = []
        for detection in self.current_detections:
            detections_data.append({
                "class_name": detection.class_name,
                "confidence": detection.confidence,
                "bounds": {
                    "x": detection.x,
                    "y": detection.y,
                    "width": detection.width, 
                    "height": detection.height
                },
                "detection_time": detection.detection_time.isoformat()
            })
        return detections_data
    
    async def stop(self):
        """Stop the detection process"""
        self.running = False
        self.logger.info("Parking detector stopped")