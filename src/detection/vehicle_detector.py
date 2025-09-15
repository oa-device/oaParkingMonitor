"""
Vehicle Detection Module
Handles YOLO model management and vehicle inference
"""

import cv2
import numpy as np
import logging
from typing import List, Dict, Any, Optional, Tuple
from ultralytics import YOLO

from ..models.enums import DetectionDifficulty


class VehicleDetector:
    """Enhanced vehicle detector with optimized inference and filtering"""
    
    # COCO vehicle class IDs
    VEHICLE_CLASSES = {2, 3, 5, 7}  # car, motorcycle, bus, truck
    
    def __init__(self, model_path: str, device: str = "cpu"):
        """Initialize vehicle detector with YOLO model"""
        self.logger = logging.getLogger(__name__)
        self.model_path = model_path
        self.device = device
        self.model: Optional[YOLO] = None
        self._model_loaded = False
        
        # Performance tracking
        self.stats = {
            "total_detections": 0,
            "filtered_detections": 0,
            "inference_count": 0,
            "model_loaded": False,
            "last_inference_time": 0.0
        }
    
    def load_model(self) -> bool:
        """Load YOLO model for vehicle detection"""
        try:
            self.logger.info(f"Loading YOLO model from {self.model_path}")
            self.model = YOLO(self.model_path)
            
            # Set device
            if hasattr(self.model, 'to'):
                self.model.to(self.device)
            
            self._model_loaded = True
            self.stats["model_loaded"] = True
            self.logger.info(f"YOLO model loaded successfully on {self.device}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load YOLO model: {e}")
            self._model_loaded = False
            self.stats["model_loaded"] = False
            return False
    
    def detect_vehicles(self, frame: np.ndarray, 
                       base_confidence: float = 0.5,
                       zone_difficulty_map: Optional[Dict[int, DetectionDifficulty]] = None) -> List[Dict[str, Any]]:
        """
        Detect vehicles in frame with adaptive confidence thresholds
        
        Args:
            frame: Input image frame
            base_confidence: Base confidence threshold
            zone_difficulty_map: Mapping of zone IDs to difficulty levels for adaptive thresholds
            
        Returns:
            List of vehicle detections with enhanced metadata
        """
        if not self._model_loaded or self.model is None:
            self.logger.warning("Model not loaded, returning empty detections")
            return []
        
        try:
            import time
            start_time = time.time()
            
            # Use base confidence directly - adaptive logic was causing issues
            adjusted_confidence = base_confidence
            self.logger.info(f"Using confidence threshold: {adjusted_confidence:.2f}")
            
            # Run inference with adjusted confidence
            results = self.model(frame, conf=adjusted_confidence, verbose=False)

            inference_time = time.time() - start_time
            self.stats["last_inference_time"] = inference_time
            self.stats["inference_count"] += 1

            # DEBUG: Log raw YOLO results before filtering
            if hasattr(results[0], 'boxes') and results[0].boxes is not None:
                raw_count = len(results[0].boxes)
                self.logger.info(f"YOLO raw detections: {raw_count} boxes with conf threshold={adjusted_confidence:.2f}")
                if raw_count > 0:
                    # Log all detection details for debugging
                    for i, box in enumerate(results[0].boxes):
                        conf = float(box.conf) if hasattr(box, 'conf') else 'unknown'
                        cls = int(box.cls) if hasattr(box, 'cls') else 'unknown'
                        self.logger.info(f"  Detection {i}: class={cls}, conf={conf:.3f}, is_vehicle={cls in self.VEHICLE_CLASSES}")
            else:
                self.logger.warning("YOLO returned no results or malformed results")

            # Extract and filter vehicle detections
            detections = self._extract_vehicle_detections(results[0])

            # DEBUG: Log after filtering
            self.logger.info(f"After vehicle filtering: {len(detections)} vehicles (from {raw_count if 'raw_count' in locals() else 0} raw)")

            # Add adaptive confidence scores based on zone difficulty
            if zone_difficulty_map:
                detections = self._add_adaptive_confidence(detections, zone_difficulty_map)

            self.stats["total_detections"] = len(detections)
            self.logger.debug(f"Detected {len(detections)} vehicles in {inference_time:.3f}s")
            
            return detections
            
        except Exception as e:
            self.logger.error(f"Vehicle detection failed: {e}")
            return []
    
    def _extract_vehicle_detections(self, result) -> List[Dict[str, Any]]:
        """Extract vehicle detections from YOLO results"""
        detections = []
        
        if result.boxes is None or len(result.boxes) == 0:
            return detections
        
        boxes = result.boxes.xyxy.cpu().numpy()
        confidences = result.boxes.conf.cpu().numpy()
        classes = result.boxes.cls.cpu().numpy().astype(int)
        
        for i, (box, conf, cls) in enumerate(zip(boxes, confidences, classes)):
            # Filter for vehicle classes only
            if cls not in self.VEHICLE_CLASSES:
                continue
            
            x1, y1, x2, y2 = box
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            width = x2 - x1
            height = y2 - y1
            area = width * height
            
            detection = {
                "id": i,
                "class_id": int(cls),
                "confidence": float(conf),
                "bbox": [float(x1), float(y1), float(x2), float(y2)],
                "center": [float(center_x), float(center_y)],
                "dimensions": [float(width), float(height)],
                "area": float(area),
                # Enhanced detection metadata
                "corners": [
                    [float(x1), float(y1)],  # top-left
                    [float(x2), float(y1)],  # top-right
                    [float(x2), float(y2)],  # bottom-right
                    [float(x1), float(y2)]   # bottom-left
                ],
                "edge_points": self._get_edge_points(x1, y1, x2, y2),
                "original_confidence": float(conf)  # Store original before adjustments
            }
            
            detections.append(detection)
        
        self.stats["filtered_detections"] = len(detections)
        return detections
    
    def _get_edge_points(self, x1: float, y1: float, x2: float, y2: float) -> List[List[float]]:
        """Get additional edge points for better overlap detection"""
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        
        return [
            [float(center_x), float(y1)],    # top-center
            [float(x2), float(center_y)],    # right-center
            [float(center_x), float(y2)],    # bottom-center
            [float(x1), float(center_y)],    # left-center
            [float(center_x), float(center_y)]  # center (original method)
        ]
    
    def _add_adaptive_confidence(self, detections: List[Dict[str, Any]], 
                                zone_difficulty_map: Dict[int, DetectionDifficulty]) -> List[Dict[str, Any]]:
        """Add adaptive confidence adjustments based on zone difficulty"""
        # This will be enhanced when zone analysis is integrated
        # For now, just preserve original confidence
        return detections
    
    def get_stats(self) -> Dict[str, Any]:
        """Get detector performance statistics"""
        return self.stats.copy()
    
    def is_loaded(self) -> bool:
        """Check if model is loaded and ready"""
        return self._model_loaded and self.model is not None