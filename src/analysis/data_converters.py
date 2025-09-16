"""
Data Format Converters
Handles conversion between VehicleDetection format and analysis formats
"""

from typing import List, Dict, Any
import numpy as np
import cv2
import logging


class DetectionConverter:
    """Converts VehicleDetection objects to analysis format"""
    
    @staticmethod
    def to_analysis_format(detections) -> List[Dict[str, Any]]:
        """Convert VehicleDetection objects to analysis format for zone analyzer"""
        detection_data = []
        
        for i, detection in enumerate(detections):
            x1, y1 = detection.x, detection.y
            x2, y2 = detection.x + detection.width, detection.y + detection.height
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            area = detection.width * detection.height
            
            detection_dict = {
                "id": i,
                "class_id": 2,  # Assume car class
                "confidence": detection.confidence,
                "bbox": [float(x1), float(y1), float(x2), float(y2)],
                "center": [float(center_x), float(center_y)],
                "dimensions": [float(detection.width), float(detection.height)],
                "area": float(area),
                "corners": [
                    [float(x1), float(y1)],  # top-left
                    [float(x2), float(y1)],  # top-right
                    [float(x2), float(y2)],  # bottom-right
                    [float(x1), float(y2)]   # bottom-left
                ],
                "edge_points": [
                    [float(center_x), float(y1)],    # top-center
                    [float(x2), float(center_y)],    # right-center
                    [float(center_x), float(y2)],    # bottom-center
                    [float(x1), float(center_y)],    # left-center
                    [float(center_x), float(center_y)]  # center
                ],
                "original_confidence": detection.confidence
            }
            detection_data.append(detection_dict)
        
        return detection_data


class ZoneConverter:
    """Converts parking zone configuration to analysis format"""
    
    @staticmethod
    def to_analysis_format(parking_zones) -> List[Dict[str, Any]]:
        """Convert parking zones to analyzer format"""
        zones_data = []
        
        for zone in parking_zones:
            zones_data.append({
                "id": zone.id,
                "space_id": zone.space_id,
                "name": zone.name,
                "description": zone.description,
                "coordinates": zone.coordinates,
                "detection_difficulty": (zone.detection_difficulty.value 
                                       if hasattr(zone.detection_difficulty, "value") 
                                       else zone.detection_difficulty)
            })
        
        return zones_data


class ResultConverter:
    """Converts analysis results back to zone status format"""
    
    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or logging.getLogger(__name__)
    
    def to_zone_status_format(self, zone_results, zones_data, detections, config) -> List[Dict[str, Any]]:
        """Convert results back to zone status format and update config"""
        zones_status = []
        
        for result in zone_results:
            # Update zone status in config
            config.update_zone_status(
                result.zone_id, 
                result.occupied, 
                result.confidence
            )
            
            # Update detection zone_id for result tracking
            self._update_detection_zone_ids(detections, result)
            
            zones_status.append({
                "id": result.zone_id,
                "space_id": result.space_id,
                "name": next(z["name"] for z in zones_data if z["id"] == result.zone_id),
                "description": next(z["description"] for z in zones_data if z["id"] == result.zone_id),
                "occupied": result.occupied,
                "confidence": result.confidence,
                "coordinates": next(z["coordinates"] for z in zones_data if z["id"] == result.zone_id),
                "detection_difficulty": result.zone_difficulty.value,
                "detection_count": result.detection_count,
                "detection_method": result.detection_method,
                "overlap_scores": result.overlap_scores
            })
        
        # Log ignored detections
        self._log_ignored_detections(detections)
        
        return zones_status
    
    def _update_detection_zone_ids(self, detections, result):
        """Update detection zone_id for result tracking"""
        for detection in detections:
            det_center_x = detection.x + detection.width // 2
            det_center_y = detection.y + detection.height // 2
            
            # Check if this detection contributed to this zone
            for zone_det in result.detections:
                zone_center = zone_det["center"]
                if (abs(det_center_x - zone_center[0]) < 10 and 
                    abs(det_center_y - zone_center[1]) < 10):
                    detection.zone_id = result.zone_id
                    break
    
    def _log_ignored_detections(self, detections):
        """Log ignored detections outside defined zones"""
        assigned_detections = sum(1 for d in detections if hasattr(d, 'zone_id') and d.zone_id is not None)
        ignored_count = len(detections) - assigned_detections
        if ignored_count > 0:
            self.logger.debug(f"Ignored {ignored_count} detections outside defined zones")


class FallbackAnalyzer:
    """Fallback zone analysis using original polygon-based logic"""
    
    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or logging.getLogger(__name__)
    
    def analyze_zones(self, parking_zones, detections, config) -> List[Dict[str, Any]]:
        """Fallback zone analysis using original logic"""
        zones_status = []
        
        for zone in parking_zones:
            occupied = False
            best_confidence = 0.0
            zone_detection_count = 0
            
            zone_coords = zone.coordinates
            if len(zone_coords) >= 3:
                zone_polygon_points = np.array(zone_coords, dtype=np.int32)
                
                for detection in detections:
                    det_center_x = detection.x + detection.width // 2
                    det_center_y = detection.y + detection.height // 2
                    
                    inside = cv2.pointPolygonTest(zone_polygon_points, 
                                                (det_center_x, det_center_y), False)
                    
                    if inside >= 0:
                        zone_detection_count += 1
                        detection.zone_id = zone.id
                        
                        adjusted_confidence = self._adjust_confidence_by_difficulty(
                            detection.confidence, 
                            zone.detection_difficulty.value if hasattr(zone.detection_difficulty, "value") else zone.detection_difficulty
                        )
                        
                        difficulty_value = (zone.detection_difficulty.value 
                                          if hasattr(zone.detection_difficulty, "value") 
                                          else zone.detection_difficulty)
                        threshold = (config.processing.confidence_threshold * 0.7 
                                   if difficulty_value == "hard" 
                                   else config.processing.confidence_threshold)
                        
                        if adjusted_confidence >= threshold:
                            occupied = True
                            best_confidence = max(best_confidence, adjusted_confidence)
            
            config.update_zone_status(zone.id, occupied, best_confidence)
            
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