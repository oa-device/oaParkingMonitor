"""
Image Preprocessing Module
Enhanced preprocessing for edge zones and difficult detection scenarios
"""

import cv2
import numpy as np
import logging
from typing import Dict, Any, List, Tuple, Optional

from ..models.enums import DetectionDifficulty


class ImagePreprocessor:
    """Enhanced image preprocessing for better detection accuracy"""
    
    def __init__(self):
        """Initialize image preprocessor"""
        self.logger = logging.getLogger(__name__)
        
        # Performance tracking
        self.stats = {
            "frames_processed": 0,
            "edge_zones_enhanced": 0,
            "clahe_applications": 0,
            "brightness_adjustments": 0,
            "contrast_enhancements": 0
        }
    
    def preprocess_frame(self, frame: np.ndarray, 
                        zones: List[Dict[str, Any]] = None,
                        enhance_edge_zones: bool = True) -> np.ndarray:
        """
        Apply comprehensive preprocessing to improve detection accuracy
        
        Args:
            frame: Input image frame
            zones: Parking zones for targeted enhancement
            enhance_edge_zones: Apply special enhancement for edge zones
            
        Returns:
            Enhanced frame optimized for vehicle detection
        """
        enhanced_frame = frame.copy()
        
        try:
            # Apply global enhancements
            enhanced_frame = self._apply_global_enhancement(enhanced_frame)
            
            # Apply targeted edge zone preprocessing
            if enhance_edge_zones and zones:
                enhanced_frame = self._enhance_edge_zones(enhanced_frame, zones)
            
            self.stats["frames_processed"] += 1
            return enhanced_frame
            
        except Exception as e:
            self.logger.error(f"Frame preprocessing failed: {e}")
            return frame  # Return original frame on error
    
    def _apply_global_enhancement(self, frame: np.ndarray) -> np.ndarray:
        """Apply global image enhancement techniques"""
        enhanced = frame.copy()
        
        # Convert to LAB color space for better luminance control
        lab = cv2.cvtColor(enhanced, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        
        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_channel = clahe.apply(l_channel)
        self.stats["clahe_applications"] += 1
        
        # Merge channels and convert back to BGR
        enhanced_lab = cv2.merge([l_channel, a_channel, b_channel])
        enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
        
        # Apply gamma correction for better visibility
        enhanced = self._apply_gamma_correction(enhanced, gamma=1.2)
        
        return enhanced
    
    def _enhance_edge_zones(self, frame: np.ndarray, 
                           zones: List[Dict[str, Any]]) -> np.ndarray:
        """Apply targeted enhancement for edge zones (B-section)"""
        enhanced = frame.copy()
        
        # Identify edge zones (hard difficulty zones at frame edges)
        edge_zones = [
            zone for zone in zones 
            if zone.detection_difficulty == DetectionDifficulty.HARD.value
        ]
        
        if not edge_zones:
            return enhanced
        
        for zone in edge_zones:
            enhanced = self._enhance_zone_region(enhanced, zone)
            self.stats["edge_zones_enhanced"] += 1
        
        return enhanced
    
    def _enhance_zone_region(self, frame: np.ndarray, 
                            zone: Dict[str, Any]) -> np.ndarray:
        """Apply localized enhancement to specific zone region"""
        enhanced = frame.copy()
        
        try:
            # Get zone coordinates and create mask
            coordinates = zone["coordinates"]
            zone_polygon = np.array(coordinates, dtype=np.int32)
            
            # Create mask for the zone
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            cv2.fillPoly(mask, [zone_polygon], 255)
            
            # Expand mask slightly for better edge coverage
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.dilate(mask, kernel, iterations=1)
            
            # Apply localized enhancements
            zone_enhanced = self._apply_localized_enhancement(frame, mask)
            
            # Blend enhanced region back into frame
            mask_normalized = mask.astype(np.float32) / 255.0
            mask_3d = np.stack([mask_normalized] * 3, axis=-1)
            
            enhanced = (frame.astype(np.float32) * (1 - mask_3d) + 
                       zone_enhanced.astype(np.float32) * mask_3d).astype(np.uint8)
            
        except Exception as e:
            self.logger.debug(f"Zone enhancement failed for zone {getattr(zone, 'id', 'unknown')}: {e}")
        
        return enhanced
    
    def _apply_localized_enhancement(self, frame: np.ndarray, 
                                   mask: np.ndarray) -> np.ndarray:
        """Apply aggressive localized enhancement for difficult regions"""
        enhanced = frame.copy()
        
        # Convert to HSV for better control
        hsv = cv2.cvtColor(enhanced, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        
        # Enhance value (brightness) channel aggressively
        v_enhanced = cv2.equalizeHist(v)
        
        # Apply additional brightness boost for very dark regions
        v_boosted = cv2.addWeighted(v, 0.6, v_enhanced, 0.4, 10)
        v_boosted = np.clip(v_boosted, 0, 255).astype(np.uint8)
        
        # Enhance saturation slightly for better color distinction
        s_enhanced = cv2.addWeighted(s, 1.0, s, 0.0, 5)
        s_enhanced = np.clip(s_enhanced, 0, 255).astype(np.uint8)
        
        # Merge and convert back to BGR
        enhanced_hsv = cv2.merge([h, s_enhanced, v_boosted])
        enhanced = cv2.cvtColor(enhanced_hsv, cv2.COLOR_HSV2BGR)
        
        self.stats["brightness_adjustments"] += 1
        self.stats["contrast_enhancements"] += 1
        
        return enhanced
    
    def _apply_gamma_correction(self, frame: np.ndarray, gamma: float) -> np.ndarray:
        """Apply gamma correction for better visibility"""
        # Build lookup table for gamma correction
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255 
                         for i in np.arange(0, 256)]).astype("uint8")
        
        # Apply gamma correction using the lookup table
        return cv2.LUT(frame, table)
    
    def preprocess_for_hard_zones(self, frame: np.ndarray, 
                                 hard_zone_coords: List[List[List[int]]]) -> np.ndarray:
        """Specialized preprocessing for hard detection zones"""
        enhanced = frame.copy()
        
        # Apply more aggressive enhancement for hard zones
        for coords in hard_zone_coords:
            try:
                # Create zone mask
                zone_polygon = np.array(coords, dtype=np.int32)
                mask = np.zeros(frame.shape[:2], dtype=np.uint8)
                cv2.fillPoly(mask, [zone_polygon], 255)
                
                # Apply very aggressive CLAHE to this region
                zone_region = cv2.bitwise_and(enhanced, enhanced, mask=mask)
                
                # Convert to LAB and enhance L channel aggressively
                if zone_region.any():
                    lab = cv2.cvtColor(zone_region, cv2.COLOR_BGR2LAB)
                    l, a, b = cv2.split(lab)
                    
                    # Very aggressive CLAHE for hard zones
                    clahe_aggressive = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4))
                    l = clahe_aggressive.apply(l)
                    
                    enhanced_lab = cv2.merge([l, a, b])
                    enhanced_region = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
                    
                    # Blend back into main frame
                    mask_3d = np.stack([mask.astype(np.float32) / 255.0] * 3, axis=-1)
                    enhanced = (enhanced.astype(np.float32) * (1 - mask_3d) + 
                               enhanced_region.astype(np.float32) * mask_3d).astype(np.uint8)
                
            except Exception as e:
                self.logger.debug(f"Hard zone preprocessing failed: {e}")
                continue
        
        return enhanced
    
    def enhance_low_light_regions(self, frame: np.ndarray, 
                                brightness_threshold: int = 50) -> np.ndarray:
        """Enhance regions with low brightness/contrast"""
        enhanced = frame.copy()
        
        # Convert to grayscale to analyze brightness
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Find low brightness regions
        low_light_mask = (gray < brightness_threshold).astype(np.uint8) * 255
        
        if cv2.countNonZero(low_light_mask) > 0:
            # Apply adaptive histogram equalization to low light regions
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(6, 6))
            
            # Process each channel
            for i in range(3):
                channel = enhanced[:, :, i]
                enhanced_channel = clahe.apply(channel)
                
                # Blend enhanced channel only in low light areas
                mask_norm = low_light_mask.astype(np.float32) / 255.0
                enhanced[:, :, i] = (channel.astype(np.float32) * (1 - mask_norm) + 
                                   enhanced_channel.astype(np.float32) * mask_norm).astype(np.uint8)
        
        return enhanced
    
    def get_stats(self) -> Dict[str, Any]:
        """Get preprocessing performance statistics"""
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset performance statistics"""
        for key in self.stats:
            self.stats[key] = 0