"""
Zone Change Tracker for Delta Updates
Tracks parking zone state changes with timestamps for efficient delta updates
"""

import time
import logging
from collections import deque
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class ZoneChange:
    """Represents a single zone state change"""
    zone_id: str
    space_id: str
    name: str
    previous_state: bool
    current_state: bool
    previous_confidence: float
    current_confidence: float
    timestamp: int  # epoch milliseconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "zoneId": self.zone_id,
            "spaceId": self.space_id,
            "name": self.name,
            "previousState": self.previous_state,
            "currentState": self.current_state,
            "previousConfidence": self.previous_confidence,
            "currentConfidence": self.current_confidence,
            "timestamp": self.timestamp
        }


class ZoneChangeTracker:
    """
    Tracks zone state changes for delta update API
    Maintains recent changes in memory (last 10 minutes) for efficient incremental updates
    """
    
    def __init__(self, retention_minutes: int = 10):
        """
        Initialize zone change tracker
        
        Args:
            retention_minutes: How long to keep changes in memory (default: 10 minutes)
        """
        self.logger = logging.getLogger(__name__)
        self.retention_ms = retention_minutes * 60 * 1000  # Convert to milliseconds
        
        # Storage for recent changes (FIFO queue for efficient cleanup)
        self.changes: deque[ZoneChange] = deque()
        
        # Current zone states for comparison
        self.current_states: Dict[str, Dict[str, Any]] = {}
        
        self.logger.info(f"Zone change tracker initialized with {retention_minutes} minute retention")
    
    def update_zone_states(self, zones_status: List[Dict[str, Any]]) -> List[ZoneChange]:
        """
        Update zone states and track changes
        
        Args:
            zones_status: Current zone status from detector
            
        Returns:
            List of zone changes (empty if no changes)
        """
        changes = []
        current_time = int(time.time() * 1000)
        
        for zone in zones_status:
            zone_id = str(zone["id"])
            
            # Get current state
            current_occupied = bool(zone["occupied"])
            current_confidence = float(zone.get("confidence", 0.0))
            
            # Check if we have previous state
            if zone_id in self.current_states:
                previous_state = self.current_states[zone_id]
                previous_occupied = previous_state["occupied"]
                previous_confidence = previous_state["confidence"]
                
                # Check if state changed
                if (previous_occupied != current_occupied or 
                    abs(previous_confidence - current_confidence) > 0.1):
                    
                    change = ZoneChange(
                        zone_id=zone_id,
                        space_id=zone.get("space_id", zone_id),
                        name=zone.get("name", f"Zone {zone_id}"),
                        previous_state=previous_occupied,
                        current_state=current_occupied,
                        previous_confidence=previous_confidence,
                        current_confidence=current_confidence,
                        timestamp=current_time
                    )
                    
                    changes.append(change)
                    self.changes.append(change)
                    
                    self.logger.debug(
                        f"Zone {zone_id} changed: {previous_occupied} -> {current_occupied} "
                        f"(confidence: {previous_confidence:.2f} -> {current_confidence:.2f})"
                    )
            
            # Update current state
            self.current_states[zone_id] = {
                "occupied": current_occupied,
                "confidence": current_confidence,
                "space_id": zone.get("space_id", zone_id),
                "name": zone.get("name", f"Zone {zone_id}"),
                "timestamp": current_time
            }
        
        # Clean up old changes
        self._cleanup_old_changes(current_time)
        
        return changes
    
    def get_changes_since(self, since_timestamp: int) -> List[ZoneChange]:
        """
        Get zone changes since specified timestamp
        
        Args:
            since_timestamp: Timestamp in milliseconds since epoch
            
        Returns:
            List of zone changes since the timestamp
        """
        if since_timestamp < 0:
            self.logger.warning(f"Invalid timestamp: {since_timestamp}")
            return []
        
        current_time = int(time.time() * 1000)
        
        # Clean up old changes first
        self._cleanup_old_changes(current_time)
        
        # Filter changes since timestamp
        filtered_changes = [
            change for change in self.changes 
            if change.timestamp > since_timestamp
        ]
        
        self.logger.debug(
            f"Found {len(filtered_changes)} changes since {since_timestamp} "
            f"(out of {len(self.changes)} total)"
        )
        
        return filtered_changes
    
    def get_current_states(self) -> Dict[str, Dict[str, Any]]:
        """
        Get current states of all zones
        
        Returns:
            Dictionary of zone_id -> state information
        """
        return self.current_states.copy()
    
    def _cleanup_old_changes(self, current_time: int):
        """
        Remove changes older than retention period
        
        Args:
            current_time: Current timestamp in milliseconds
        """
        cutoff_time = current_time - self.retention_ms
        
        # Remove old changes from left side of deque
        while self.changes and self.changes[0].timestamp < cutoff_time:
            removed_change = self.changes.popleft()
            self.logger.debug(f"Removed old change for zone {removed_change.zone_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get tracker statistics
        
        Returns:
            Dictionary with tracker statistics
        """
        current_time = int(time.time() * 1000)
        self._cleanup_old_changes(current_time)
        
        # Calculate age of oldest change
        oldest_change_age = None
        if self.changes:
            oldest_change_age = current_time - self.changes[0].timestamp
        
        return {
            "total_changes": len(self.changes),
            "tracked_zones": len(self.current_states),
            "retention_minutes": self.retention_ms // (60 * 1000),
            "oldest_change_age_ms": oldest_change_age,
            "memory_size_estimate": len(self.changes) * 200  # Rough estimate in bytes
        }
    
    def clear_history(self):
        """Clear all change history (useful for testing)"""
        self.changes.clear()
        self.logger.info("Change history cleared")
    
    def initialize_states(self, zones_status: List[Dict[str, Any]]):
        """
        Initialize zone states without generating changes
        Useful for initial setup
        
        Args:
            zones_status: Initial zone status from detector
        """
        current_time = int(time.time() * 1000)
        
        for zone in zones_status:
            zone_id = str(zone["id"])
            
            self.current_states[zone_id] = {
                "occupied": bool(zone["occupied"]),
                "confidence": float(zone.get("confidence", 0.0)),
                "space_id": zone.get("space_id", zone_id),
                "name": zone.get("name", f"Zone {zone_id}"),
                "timestamp": current_time
            }
        
        self.logger.info(f"Initialized states for {len(zones_status)} zones")