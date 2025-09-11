"""
Zone Analysis Module
Enhanced parking zone analysis with multi-point overlap detection
"""

import cv2
import numpy as np
import logging
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass

from ..models.enums import DetectionDifficulty


@dataclass
class ZoneDetection:
    """Enhanced zone detection result with detailed metadata"""
    zone_id: int
    space_id: int
    occupied: bool
    confidence: float
    detection_count: int
    detections: List[Dict[str, Any]]
    overlap_scores: List[float]
    detection_method: str  # "center", "multi_point", "iou"
    zone_difficulty: DetectionDifficulty


class ZoneAnalyzer:
    """Enhanced zone analyzer with multi-point overlap detection"""
    
    def __init__(self):
        """Initialize zone analyzer with enhanced detection methods"""
        self.logger = logging.getLogger(__name__)
        
        # Performance tracking
        self.stats = {
            "total_zones_analyzed": 0,
            "occupied_zones": 0,
            "detection_methods_used": {
                "center_only": 0,
                "multi_point": 0,
                "iou_enhanced": 0
            },
            "confidence_adjustments": 0,
            "edge_zone_preprocessing": 0
        }
    
    def analyze_zones(self, zones: List[Dict[str, Any]], 
                     detections: List[Dict[str, Any]],
                     enhanced_detection: bool = True) -> List[ZoneDetection]:
        """
        Analyze parking zones with enhanced multi-point detection
        
        Args:
            zones: List of parking zone configurations
            detections: List of vehicle detections
            enhanced_detection: Enable multi-point and IoU detection methods
            
        Returns:
            List of zone detection results with enhanced metadata
        """
        zone_results = []
        
        for zone in zones:
            zone_result = self._analyze_single_zone(
                zone, detections, enhanced_detection
            )
            zone_results.append(zone_result)
        
        # Update statistics
        self.stats["total_zones_analyzed"] = len(zone_results)
        self.stats["occupied_zones"] = sum(1 for z in zone_results if z.occupied)
        
        return zone_results
    
    def _analyze_single_zone(self, zone: Dict[str, Any], 
                            detections: List[Dict[str, Any]],
                            enhanced_detection: bool) -> ZoneDetection:
        """Analyze a single parking zone with multiple detection methods"""
        zone_id = zone["id"]
        space_id = zone["space_id"]
        coordinates = zone["coordinates"]
        difficulty = DetectionDifficulty(zone.get("detection_difficulty", "easy"))
        
        # Convert coordinates to numpy array for OpenCV
        zone_polygon = np.array(coordinates, dtype=np.int32)
        
        # Find detections in this zone using multiple methods
        zone_detections = []
        overlap_scores = []
        detection_methods = []
        
        for detection in detections:
            # Method 1: Traditional center-point detection
            center_inside, center_score = self._check_center_point(
                detection, zone_polygon
            )
            
            if enhanced_detection:
                # Method 2: Multi-point overlap detection  
                multi_point_inside, multi_point_score = self._check_multi_point_overlap(
                    detection, zone_polygon
                )
                
                # Method 3: IoU-based overlap detection for edge zones
                iou_inside, iou_score = self._check_iou_overlap(
                    detection, zone_polygon, zone
                )
                
                # Determine best detection method
                if iou_score > 0.3:  # Strong IoU overlap
                    is_inside = iou_inside
                    overlap_score = iou_score
                    method = "iou_enhanced"
                    self.stats["detection_methods_used"]["iou_enhanced"] += 1
                elif multi_point_score > 0.2:  # Multi-point detection
                    is_inside = multi_point_inside
                    overlap_score = multi_point_score
                    method = "multi_point"
                    self.stats["detection_methods_used"]["multi_point"] += 1
                else:  # Fall back to center point
                    is_inside = center_inside
                    overlap_score = center_score
                    method = "center_only"
                    self.stats["detection_methods_used"]["center_only"] += 1
            else:
                # Traditional center-only method
                is_inside = center_inside
                overlap_score = center_score
                method = "center_only"
                self.stats["detection_methods_used"]["center_only"] += 1
            
            if is_inside:
                # Apply confidence adjustment based on zone difficulty
                adjusted_detection = self._adjust_detection_confidence(
                    detection, difficulty, overlap_score
                )
                zone_detections.append(adjusted_detection)
                overlap_scores.append(overlap_score)
                detection_methods.append(method)
        
        # Determine zone occupancy with enhanced logic
        occupied = self._determine_occupancy(
            zone_detections, overlap_scores, difficulty
        )
        
        # Calculate overall confidence
        confidence = self._calculate_zone_confidence(
            zone_detections, overlap_scores, difficulty
        )
        
        return ZoneDetection(
            zone_id=zone_id,
            space_id=space_id,
            occupied=occupied,
            confidence=confidence,
            detection_count=len(zone_detections),
            detections=zone_detections,
            overlap_scores=overlap_scores,
            detection_method=detection_methods[0] if detection_methods else "none",
            zone_difficulty=difficulty
        )
    
    def _check_center_point(self, detection: Dict[str, Any], 
                           zone_polygon: np.ndarray) -> Tuple[bool, float]:
        """Traditional center-point detection method"""
        center_x, center_y = detection["center"]
        result = cv2.pointPolygonTest(zone_polygon, (center_x, center_y), False)
        inside = result >= 0
        score = 1.0 if inside else 0.0
        return inside, score
    
    def _check_multi_point_overlap(self, detection: Dict[str, Any], 
                                  zone_polygon: np.ndarray) -> Tuple[bool, float]:
        """Enhanced multi-point overlap detection for edge cases"""
        # Check all corner points and edge points
        test_points = detection["corners"] + detection["edge_points"]
        
        inside_count = 0
        for point in test_points:
            result = cv2.pointPolygonTest(zone_polygon, tuple(point), False)
            if result >= 0:
                inside_count += 1
        
        # Calculate overlap ratio
        overlap_ratio = inside_count / len(test_points)
        
        # Consider detection valid if significant overlap (>10% for hard zones, >30% for easy)
        threshold = 0.1 if detection.get("zone_difficulty") == DetectionDifficulty.HARD else 0.3
        inside = overlap_ratio >= threshold
        
        return inside, overlap_ratio
    
    def _check_iou_overlap(self, detection: Dict[str, Any], 
                          zone_polygon: np.ndarray, 
                          zone: Dict[str, Any]) -> Tuple[bool, float]:
        """IoU-based overlap detection for precise edge zone analysis"""
        try:
            # Get detection bounding box
            x1, y1, x2, y2 = detection["bbox"]
            det_box = np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.int32)
            
            # Calculate intersection
            intersection_area = self._calculate_polygon_intersection(det_box, zone_polygon)
            
            if intersection_area <= 0:
                return False, 0.0
            
            # Calculate union
            det_area = detection["area"]
            zone_area = cv2.contourArea(zone_polygon)
            union_area = det_area + zone_area - intersection_area
            
            # Calculate IoU
            iou = intersection_area / union_area if union_area > 0 else 0.0
            
            # For hard/edge zones, accept lower IoU threshold
            difficulty = DetectionDifficulty(zone.get("detection_difficulty", "easy"))
            threshold = 0.05 if difficulty == DetectionDifficulty.HARD else 0.25
            
            inside = iou >= threshold
            return inside, iou
            
        except Exception as e:
            self.logger.debug(f"IoU calculation failed: {e}")
            return False, 0.0
    
    def _calculate_polygon_intersection(self, poly1: np.ndarray, 
                                     poly2: np.ndarray) -> float:
        """Calculate intersection area between two polygons"""
        try:
            # Create masks for both polygons
            # Use reasonable image size for calculation
            img_size = (2000, 1200)  # Assuming 1920x1080 frame + margin
            
            mask1 = np.zeros(img_size, dtype=np.uint8)
            mask2 = np.zeros(img_size, dtype=np.uint8)
            
            cv2.fillPoly(mask1, [poly1], 255)
            cv2.fillPoly(mask2, [poly2], 255)
            
            # Calculate intersection
            intersection = cv2.bitwise_and(mask1, mask2)
            intersection_area = cv2.countNonZero(intersection)
            
            return float(intersection_area)
            
        except Exception as e:
            self.logger.debug(f"Polygon intersection calculation failed: {e}")
            return 0.0
    
    def _adjust_detection_confidence(self, detection: Dict[str, Any], 
                                   difficulty: DetectionDifficulty,
                                   overlap_score: float) -> Dict[str, Any]:
        """Apply aggressive confidence adjustments for hard zones"""
        adjusted_detection = detection.copy()
        original_conf = detection["original_confidence"]
        
        # Aggressive confidence boosting for hard zones (B-section)
        if difficulty == DetectionDifficulty.HARD:
            # Much more aggressive boost: 3.0x confidence + overlap bonus
            confidence_multiplier = 4.0 + (overlap_score * 2.0)  
            adjusted_confidence = min(1.0, original_conf * confidence_multiplier)
            self.stats["confidence_adjustments"] += 1
        else:
            # Standard boost for easy zones
            confidence_multiplier = 1.2 + (overlap_score * 0.3)
            adjusted_confidence = min(1.0, original_conf * confidence_multiplier)
        
        adjusted_detection["confidence"] = adjusted_confidence
        adjusted_detection["confidence_multiplier"] = confidence_multiplier
        
        return adjusted_detection
    
    def _determine_occupancy(self, detections: List[Dict[str, Any]], 
                           overlap_scores: List[float],
                           difficulty: DetectionDifficulty) -> bool:
        """Enhanced occupancy determination with difficulty-aware thresholds"""
        if not detections:
            return False
        
        # For hard zones (B-section), use very aggressive thresholds
        if difficulty == DetectionDifficulty.HARD:
            # Accept any detection with reasonable confidence
            min_confidence = 0.05  # Extremely low threshold for hard zones
            strong_detections = [d for d in detections if d["confidence"] >= min_confidence]
            return len(strong_detections) > 0
        else:
            # Standard logic for easy zones
            min_confidence = 0.5
            strong_detections = [d for d in detections if d["confidence"] >= min_confidence]
            return len(strong_detections) > 0
    
    def _calculate_zone_confidence(self, detections: List[Dict[str, Any]], 
                                 overlap_scores: List[float],
                                 difficulty: DetectionDifficulty) -> float:
        """Calculate overall zone detection confidence"""
        if not detections:
            return 0.0
        
        # Use highest confidence detection with overlap bonus
        max_confidence = max(d["confidence"] for d in detections)
        max_overlap = max(overlap_scores) if overlap_scores else 0.0
        
        # Combine confidence and overlap score
        combined_confidence = min(1.0, max_confidence + (max_overlap * 0.2))
        
        return combined_confidence
    
    def get_stats(self) -> Dict[str, Any]:
        """Get analyzer performance statistics"""
        return self.stats.copy()