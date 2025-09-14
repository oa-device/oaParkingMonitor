"""
Temporal Smoothing Module
Provides detection persistence and stability across frames
"""

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple

import numpy as np


@dataclass
class ZoneHistory:
    """Tracks detection history for a single parking zone"""
    zone_id: int
    detections: deque = field(default_factory=lambda: deque(maxlen=5))
    confidence_history: deque = field(default_factory=lambda: deque(maxlen=5))
    last_state: bool = False
    state_change_count: int = 0
    last_state_change: float = 0.0
    stable_frames: int = 0
    
    def add_detection(self, detected: bool, confidence: float):
        """Add a new detection to history"""
        self.detections.append(detected)
        self.confidence_history.append(confidence if detected else 0.0)
        
        # Track state stability
        if len(self.detections) > 1:
            if self.detections[-1] == self.detections[-2]:
                self.stable_frames += 1
            else:
                self.stable_frames = 0


@dataclass
class VehicleMemory:
    """Tracks individual vehicle across frames"""
    vehicle_id: str
    zone_id: int
    first_seen: float
    last_seen: float
    bbox_history: deque = field(default_factory=lambda: deque(maxlen=3))
    confidence_avg: float = 0.0
    detection_count: int = 0


class TemporalSmoother:
    """
    Implements temporal smoothing for detection persistence
    Addresses the issue where stationary cars are inconsistently detected
    """
    
    def __init__(self, history_size: int = 5, hysteresis_threshold: float = 0.6):
        """
        Initialize temporal smoother
        
        Args:
            history_size: Number of frames to consider for smoothing
            hysteresis_threshold: Percentage of frames needed to change state
        """
        self.logger = logging.getLogger(__name__)
        self.history_size = history_size
        self.hysteresis_threshold = hysteresis_threshold
        
        # Zone tracking
        self.zone_histories: Dict[int, ZoneHistory] = {}
        
        # Vehicle tracking
        self.vehicle_memory: Dict[str, VehicleMemory] = {}
        self.next_vehicle_id = 1
        
        # Performance metrics
        self.stats = {
            "total_smoothed": 0,
            "state_changes_prevented": 0,
            "ghost_detections_removed": 0,
            "persistent_detections_added": 0,
            "vehicles_tracked": 0
        }
        
        # Temporal weights for averaging (most recent has highest weight)
        self.temporal_weights = self._generate_temporal_weights(history_size)
    
    def _generate_temporal_weights(self, size: int) -> List[float]:
        """Generate exponentially increasing weights for temporal averaging"""
        weights = [2 ** i for i in range(size)]
        total = sum(weights)
        return [w / total for w in weights]
    
    def smooth_detections(self, 
                         current_detections: List[Dict[str, Any]], 
                         zones: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Apply temporal smoothing to current detections
        
        Args:
            current_detections: Current frame's vehicle detections
            zones: Parking zone definitions
            
        Returns:
            Smoothed detections and zone states with persistence
        """
        self.stats["total_smoothed"] += 1
        
        # Initialize zone histories if needed
        for zone in zones:
            if zone["id"] not in self.zone_histories:
                self.zone_histories[zone["id"]] = ZoneHistory(zone_id=zone["id"])
        
        # Process current detections
        zone_detections = self._assign_detections_to_zones(current_detections, zones)
        
        # Apply temporal smoothing
        smoothed_zones = {}
        for zone in zones:
            zone_id = zone["id"]
            history = self.zone_histories[zone_id]
            
            # Current frame detection
            current_detected = zone_id in zone_detections
            current_confidence = zone_detections.get(zone_id, {}).get("confidence", 0.0)
            
            # Add to history
            history.add_detection(current_detected, current_confidence)
            
            # Apply smoothing
            smoothed_state, smoothed_confidence = self._apply_hysteresis(history)
            
            # Check for persistence improvement
            if not current_detected and smoothed_state:
                self.stats["persistent_detections_added"] += 1
                self.logger.debug(f"Zone {zone_id}: Added persistent detection (confidence: {smoothed_confidence:.2f})")
            
            smoothed_zones[zone_id] = {
                "occupied": smoothed_state,
                "confidence": smoothed_confidence,
                "stable_frames": history.stable_frames,
                "detection_history": list(history.detections)
            }
        
        # Track vehicles across frames
        self._update_vehicle_memory(current_detections, zone_detections)
        
        # Generate enhanced detections with temporal data
        enhanced_detections = self._enhance_detections_with_memory(
            current_detections, smoothed_zones
        )
        
        return enhanced_detections, smoothed_zones
    
    def _assign_detections_to_zones(self, 
                                   detections: List[Dict[str, Any]], 
                                   zones: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        """Assign vehicle detections to parking zones"""
        zone_detections = {}
        
        for detection in detections:
            # Find which zone this detection belongs to
            for zone in zones:
                if self._is_detection_in_zone(detection, zone):
                    zone_id = zone["id"]
                    # Keep highest confidence detection per zone
                    if zone_id not in zone_detections or \
                       detection.get("confidence", 0) > zone_detections[zone_id].get("confidence", 0):
                        zone_detections[zone_id] = detection
                    break
        
        return zone_detections
    
    def _is_detection_in_zone(self, detection: Dict[str, Any], zone: Dict[str, Any]) -> bool:
        """Check if detection center is within zone polygon"""
        # This will be called from the actual zone analyzer
        # For now, simplified check based on detection having zone_id
        return detection.get("zone_id") == zone["id"]
    
    def _apply_hysteresis(self, history: ZoneHistory) -> Tuple[bool, float]:
        """
        Apply hysteresis to prevent flickering
        
        Returns:
            Smoothed occupancy state and confidence
        """
        if len(history.detections) == 0:
            return False, 0.0
        
        # Calculate weighted detection ratio
        detection_count = sum(1 for d in history.detections if d)
        detection_ratio = detection_count / len(history.detections)
        
        # Calculate weighted confidence
        if history.confidence_history:
            weighted_confidence = sum(
                c * w for c, w in zip(history.confidence_history, self.temporal_weights[-len(history.confidence_history):])
            )
        else:
            weighted_confidence = 0.0
        
        # Apply hysteresis logic
        current_state = history.last_state
        
        # To change from vacant to occupied: need strong evidence
        if not current_state and detection_ratio >= self.hysteresis_threshold:
            new_state = True
            history.last_state_change = time.time()
            history.state_change_count += 1
        # To change from occupied to vacant: need strong evidence of absence
        elif current_state and detection_ratio <= (1 - self.hysteresis_threshold):
            new_state = False
            history.last_state_change = time.time()
            history.state_change_count += 1
        else:
            # Maintain current state (hysteresis)
            new_state = current_state
            if new_state != (detection_count > 0):
                self.stats["state_changes_prevented"] += 1
        
        history.last_state = new_state
        
        # Boost confidence for stable detections
        if history.stable_frames > 3:
            weighted_confidence = min(1.0, weighted_confidence * 1.2)
        
        return new_state, weighted_confidence
    
    def _update_vehicle_memory(self, 
                              detections: List[Dict[str, Any]], 
                              zone_detections: Dict[int, Dict[str, Any]]):
        """Track vehicles across frames for better persistence"""
        current_time = time.time()
        
        # Clean old memories (vehicles not seen for 10 seconds)
        self.vehicle_memory = {
            vid: mem for vid, mem in self.vehicle_memory.items()
            if current_time - mem.last_seen < 10.0
        }
        
        # Match current detections to existing vehicles
        for zone_id, detection in zone_detections.items():
            matched = False
            
            # Try to match with existing vehicle
            for vid, memory in self.vehicle_memory.items():
                if memory.zone_id == zone_id:
                    # Same zone, likely same vehicle
                    memory.last_seen = current_time
                    memory.detection_count += 1
                    memory.bbox_history.append(detection.get("bbox", []))
                    memory.confidence_avg = (
                        memory.confidence_avg * 0.7 + 
                        detection.get("confidence", 0) * 0.3
                    )
                    matched = True
                    break
            
            # New vehicle detected
            if not matched:
                vehicle_id = f"v_{self.next_vehicle_id}"
                self.next_vehicle_id += 1
                
                self.vehicle_memory[vehicle_id] = VehicleMemory(
                    vehicle_id=vehicle_id,
                    zone_id=zone_id,
                    first_seen=current_time,
                    last_seen=current_time,
                    confidence_avg=detection.get("confidence", 0),
                    detection_count=1
                )
                self.stats["vehicles_tracked"] += 1
    
    def _enhance_detections_with_memory(self, 
                                       detections: List[Dict[str, Any]], 
                                       smoothed_zones: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enhance detections with temporal memory data"""
        enhanced = []
        
        for detection in detections:
            enhanced_detection = detection.copy()
            
            # Add temporal metadata
            zone_id = detection.get("zone_id")
            if zone_id and zone_id in smoothed_zones:
                enhanced_detection["temporal_confidence"] = smoothed_zones[zone_id]["confidence"]
                enhanced_detection["stable_frames"] = smoothed_zones[zone_id]["stable_frames"]
                enhanced_detection["smoothed_state"] = smoothed_zones[zone_id]["occupied"]
            
            # Add vehicle tracking data
            for vid, memory in self.vehicle_memory.items():
                if memory.zone_id == zone_id:
                    enhanced_detection["vehicle_id"] = vid
                    enhanced_detection["detection_count"] = memory.detection_count
                    enhanced_detection["time_parked"] = time.time() - memory.first_seen
                    break
            
            enhanced.append(enhanced_detection)
        
        return enhanced
    
    def get_zone_stability_score(self, zone_id: int) -> float:
        """Get stability score for a zone (0-1, higher is more stable)"""
        if zone_id not in self.zone_histories:
            return 0.0
        
        history = self.zone_histories[zone_id]
        
        # Factors for stability
        stable_ratio = history.stable_frames / max(1, len(history.detections))
        change_penalty = 1.0 / (1 + history.state_change_count * 0.1)
        
        return min(1.0, stable_ratio * change_penalty)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get temporal smoothing statistics"""
        return {
            **self.stats,
            "active_zones": len(self.zone_histories),
            "tracked_vehicles": len(self.vehicle_memory),
            "avg_stability": np.mean([
                self.get_zone_stability_score(zid) 
                for zid in self.zone_histories
            ]) if self.zone_histories else 0.0
        }


class DetectionTracker:
    """
    Tracks detection patterns and provides analytics
    """
    
    def __init__(self, window_size: int = 60):
        """
        Initialize detection tracker
        
        Args:
            window_size: Time window in seconds for pattern analysis
        """
        self.logger = logging.getLogger(__name__)
        self.window_size = window_size
        
        # Detection patterns
        self.detection_times: Dict[int, deque] = {}
        self.occupancy_patterns: Dict[int, List[Tuple[float, bool]]] = {}
        
    def track_detection(self, zone_id: int, occupied: bool, timestamp: float):
        """Track a detection event"""
        if zone_id not in self.detection_times:
            self.detection_times[zone_id] = deque(maxlen=self.window_size)
            self.occupancy_patterns[zone_id] = []
        
        self.detection_times[zone_id].append(timestamp)
        
        # Track occupancy changes
        if not self.occupancy_patterns[zone_id] or \
           self.occupancy_patterns[zone_id][-1][1] != occupied:
            self.occupancy_patterns[zone_id].append((timestamp, occupied))
    
    def get_zone_metrics(self, zone_id: int) -> Dict[str, Any]:
        """Get detection metrics for a zone"""
        if zone_id not in self.detection_times:
            return {}
        
        times = list(self.detection_times[zone_id])
        if len(times) < 2:
            return {}
        
        # Calculate metrics
        time_span = times[-1] - times[0]
        detection_rate = len(times) / max(1, time_span)
        
        # Calculate occupancy duration
        patterns = self.occupancy_patterns.get(zone_id, [])
        occupancy_duration = 0.0
        if patterns:
            for i in range(len(patterns) - 1):
                if patterns[i][1]:  # If occupied
                    occupancy_duration += patterns[i + 1][0] - patterns[i][0]
        
        return {
            "detection_rate": detection_rate,
            "occupancy_duration": occupancy_duration,
            "total_detections": len(times),
            "pattern_changes": len(patterns)
        }