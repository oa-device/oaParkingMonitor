"""
Vehicle Tracking Module
Implements multi-scale detection and vehicle tracking across frames
"""

import cv2
import numpy as np
import logging
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import time


@dataclass
class TrackedVehicle:
    """Represents a tracked vehicle across multiple frames"""
    id: str
    bbox: List[float]
    confidence: float
    zone_id: Optional[int]
    first_seen: float
    last_updated: float
    missed_frames: int
    appearance_features: Optional[np.ndarray] = None


class VehicleTracker:
    """
    Enhanced vehicle tracker with multi-scale detection support
    Addresses the issue of missing vehicle detections (1/4 detection rate)
    """
    
    def __init__(self, 
                 max_missed_frames: int = 5,
                 iou_threshold: float = 0.3,
                 scales: List[float] = None):
        """
        Initialize vehicle tracker
        
        Args:
            max_missed_frames: Maximum frames a vehicle can be missed before removal
            iou_threshold: IoU threshold for matching vehicles across frames
            scales: Scales for multi-scale detection
        """
        self.logger = logging.getLogger(__name__)
        self.max_missed_frames = max_missed_frames
        self.iou_threshold = iou_threshold
        self.scales = scales or [0.8, 1.0, 1.2, 1.5]
        
        # Tracked vehicles
        self.tracked_vehicles: Dict[str, TrackedVehicle] = {}
        self.next_vehicle_id = 1
        
        # Performance metrics
        self.stats = {
            "vehicles_tracked": 0,
            "vehicles_lost": 0,
            "vehicles_reidentified": 0,
            "multi_scale_detections": 0,
            "scales_used": {scale: 0 for scale in self.scales}
        }
    
    def detect_multi_scale(self, 
                          frame: np.ndarray, 
                          detector,
                          base_confidence: float = 0.35) -> List[Dict[str, Any]]:
        """
        Perform multi-scale detection to catch vehicles at different sizes
        This addresses the issue where only 1/4 cars are detected
        
        Args:
            frame: Input image frame
            detector: Vehicle detector instance
            base_confidence: Base confidence threshold
            
        Returns:
            Fused detections from multiple scales
        """
        all_detections = []
        original_h, original_w = frame.shape[:2]
        
        for scale in self.scales:
            try:
                # Skip if scale would make image too small
                if original_w * scale < 320 or original_h * scale < 240:
                    continue
                
                # Resize frame
                if scale != 1.0:
                    scaled_w = int(original_w * scale)
                    scaled_h = int(original_h * scale)
                    scaled_frame = cv2.resize(frame, (scaled_w, scaled_h), 
                                             interpolation=cv2.INTER_LINEAR)
                else:
                    scaled_frame = frame
                
                # Adjust confidence based on scale
                # Lower confidence for smaller scales (harder to detect)
                scale_confidence = base_confidence * (0.8 if scale < 1.0 else 1.0)
                
                # Run detection
                detections = detector.detect_vehicles(
                    scaled_frame, 
                    base_confidence=scale_confidence
                )
                
                # Scale coordinates back to original
                if scale != 1.0:
                    for det in detections:
                        det["bbox"] = [
                            coord / scale for coord in det["bbox"]
                        ]
                        det["center"] = [
                            coord / scale for coord in det["center"]
                        ]
                        det["dimensions"] = [
                            dim / scale for dim in det["dimensions"]
                        ]
                        det["area"] = det["area"] / (scale * scale)
                        det["scale_factor"] = scale
                
                all_detections.extend(detections)
                self.stats["scales_used"][scale] += len(detections)
                
            except Exception as e:
                self.logger.error(f"Multi-scale detection failed at scale {scale}: {e}")
                continue
        
        self.stats["multi_scale_detections"] += 1
        
        # Apply NMS to fuse overlapping detections
        fused_detections = self._nms_fusion(all_detections)
        
        self.logger.debug(f"Multi-scale detection: {len(all_detections)} raw -> {len(fused_detections)} fused")
        
        return fused_detections
    
    def _nms_fusion(self, detections: List[Dict[str, Any]], 
                   nms_threshold: float = 0.4) -> List[Dict[str, Any]]:
        """
        Apply Non-Maximum Suppression to fuse overlapping detections
        Prioritizes detections with higher confidence
        """
        if not detections:
            return []
        
        # Convert to numpy arrays for NMS
        boxes = np.array([d["bbox"] for d in detections])
        scores = np.array([d["confidence"] for d in detections])
        
        # Apply NMS
        indices = self._non_max_suppression(boxes, scores, nms_threshold)
        
        # Return filtered detections
        fused = [detections[i] for i in indices]
        
        # Merge information from suppressed detections
        for i, det in enumerate(fused):
            # Find overlapping detections
            overlaps = []
            for j, other in enumerate(detections):
                if j not in indices and self._calculate_iou(det["bbox"], other["bbox"]) > 0.3:
                    overlaps.append(other)
            
            # Boost confidence if multiple scales detected the same vehicle
            if overlaps:
                avg_confidence = np.mean([det["confidence"]] + [o["confidence"] for o in overlaps])
                det["confidence"] = min(1.0, avg_confidence * 1.1)
                det["multi_scale_confirmed"] = True
                det["detection_scales"] = len(overlaps) + 1
        
        return fused
    
    def _non_max_suppression(self, boxes: np.ndarray, 
                           scores: np.ndarray, 
                           threshold: float) -> List[int]:
        """
        Perform Non-Maximum Suppression
        
        Returns:
            Indices of boxes to keep
        """
        x1 = boxes[:, 0]
        y1 = boxes[:, 1]
        x2 = boxes[:, 2]
        y2 = boxes[:, 3]
        
        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]
        
        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            
            # Calculate IoU with remaining boxes
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            
            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            inter = w * h
            
            iou = inter / (areas[i] + areas[order[1:]] - inter)
            
            # Keep boxes with IoU less than threshold
            inds = np.where(iou <= threshold)[0]
            order = order[inds + 1]
        
        return keep
    
    def track_vehicles(self, 
                       detections: List[Dict[str, Any]], 
                       timestamp: float) -> List[Dict[str, Any]]:
        """
        Track vehicles across frames and assign persistent IDs
        
        Args:
            detections: Current frame detections
            timestamp: Current timestamp
            
        Returns:
            Detections with tracking information
        """
        tracked_detections = []
        matched_ids = set()
        
        # Match current detections with tracked vehicles
        for detection in detections:
            best_match = None
            best_iou = 0.0
            
            # Find best matching tracked vehicle
            for vehicle_id, vehicle in self.tracked_vehicles.items():
                if vehicle_id in matched_ids:
                    continue
                
                iou = self._calculate_iou(detection["bbox"], vehicle.bbox)
                if iou > self.iou_threshold and iou > best_iou:
                    best_match = vehicle_id
                    best_iou = iou
            
            if best_match:
                # Update existing vehicle
                vehicle = self.tracked_vehicles[best_match]
                vehicle.bbox = detection["bbox"]
                vehicle.confidence = detection["confidence"]
                vehicle.last_updated = timestamp
                vehicle.missed_frames = 0
                vehicle.zone_id = detection.get("zone_id")
                
                detection["tracked_id"] = best_match
                detection["tracking_confidence"] = best_iou
                detection["tracked_duration"] = timestamp - vehicle.first_seen
                
                matched_ids.add(best_match)
                self.stats["vehicles_reidentified"] += 1
            else:
                # Create new tracked vehicle
                vehicle_id = f"vehicle_{self.next_vehicle_id}"
                self.next_vehicle_id += 1
                
                self.tracked_vehicles[vehicle_id] = TrackedVehicle(
                    id=vehicle_id,
                    bbox=detection["bbox"],
                    confidence=detection["confidence"],
                    zone_id=detection.get("zone_id"),
                    first_seen=timestamp,
                    last_updated=timestamp,
                    missed_frames=0
                )
                
                detection["tracked_id"] = vehicle_id
                detection["tracking_confidence"] = 1.0
                detection["tracked_duration"] = 0.0
                
                matched_ids.add(vehicle_id)
                self.stats["vehicles_tracked"] += 1
            
            tracked_detections.append(detection)
        
        # Update missed frames for unmatched vehicles
        for vehicle_id, vehicle in list(self.tracked_vehicles.items()):
            if vehicle_id not in matched_ids:
                vehicle.missed_frames += 1
                
                # Keep vehicle if recently seen (ghost detection prevention)
                if vehicle.missed_frames <= self.max_missed_frames:
                    # Create ghost detection to maintain persistence
                    ghost_detection = {
                        "bbox": vehicle.bbox,
                        "confidence": vehicle.confidence * 0.8,  # Decay confidence
                        "tracked_id": vehicle_id,
                        "zone_id": vehicle.zone_id,
                        "is_ghost": True,
                        "missed_frames": vehicle.missed_frames,
                        "tracked_duration": timestamp - vehicle.first_seen
                    }
                    tracked_detections.append(ghost_detection)
                else:
                    # Remove vehicle after too many missed frames
                    del self.tracked_vehicles[vehicle_id]
                    self.stats["vehicles_lost"] += 1
        
        return tracked_detections
    
    def _calculate_iou(self, box1: List[float], box2: List[float]) -> float:
        """Calculate Intersection over Union between two bounding boxes"""
        x1_min, y1_min, x1_max, y1_max = box1
        x2_min, y2_min, x2_max, y2_max = box2
        
        # Calculate intersection
        intersect_xmin = max(x1_min, x2_min)
        intersect_ymin = max(y1_min, y2_min)
        intersect_xmax = min(x1_max, x2_max)
        intersect_ymax = min(y1_max, y2_max)
        
        if intersect_xmax < intersect_xmin or intersect_ymax < intersect_ymin:
            return 0.0
        
        intersect_area = (intersect_xmax - intersect_xmin) * (intersect_ymax - intersect_ymin)
        
        # Calculate union
        box1_area = (x1_max - x1_min) * (y1_max - y1_min)
        box2_area = (x2_max - x2_min) * (y2_max - y2_min)
        union_area = box1_area + box2_area - intersect_area
        
        return intersect_area / union_area if union_area > 0 else 0.0
    
    def get_persistent_zones(self) -> Dict[int, float]:
        """
        Get zones with persistent vehicle presence
        
        Returns:
            Dictionary of zone_id to persistence score
        """
        zone_persistence = {}
        current_time = time.time()
        
        for vehicle in self.tracked_vehicles.values():
            if vehicle.zone_id is not None:
                duration = current_time - vehicle.first_seen
                persistence_score = min(1.0, duration / 60.0)  # Max score after 1 minute
                
                if vehicle.zone_id not in zone_persistence:
                    zone_persistence[vehicle.zone_id] = 0.0
                
                zone_persistence[vehicle.zone_id] = max(
                    zone_persistence[vehicle.zone_id],
                    persistence_score
                )
        
        return zone_persistence
    
    def get_stats(self) -> Dict[str, Any]:
        """Get tracking statistics"""
        return {
            **self.stats,
            "active_vehicles": len(self.tracked_vehicles),
            "persistent_zones": len(self.get_persistent_zones())
        }