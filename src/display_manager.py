"""Display management system for oaParkingMonitor."""

import time
import asyncio
from typing import List, Dict, Any, Optional, Tuple
import logging

import cv2
import numpy as np
import structlog

from .core.detection import ParkingSpace, VehicleInfo, DetectionResult
from .config_manager import ConfigManager


class DisplayManager:
    """Manages dual-mode display: ads + detection overlay."""
    
    def __init__(self, config: ConfigManager, detector=None):
        """Initialize display manager.
        
        Args:
            config: Configuration manager
            detector: Parking detector instance
        """
        self.config = config
        self.detector = detector
        self.logger = structlog.get_logger("display_manager")
        
        self.is_running = False
        self.is_initialized = False
        
        # Display settings
        self.overlay_opacity = config.display.overlay_opacity
        self.font_scale = config.display.font_scale
        self.line_thickness = config.display.line_thickness
        self.colors = config.display.colors
        
        # Font for text overlay
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        
        # Current display state
        self.current_frame = None
        self.last_update = 0
    
    async def initialize(self) -> None:
        """Initialize the display manager."""
        if not self.config.display.enabled:
            self.logger.info("Display management disabled in configuration")
            return
        
        try:
            self.logger.info("Initializing display manager",
                           overlay_enabled=True,
                           opacity=self.overlay_opacity)
            
            self.is_initialized = True
            self.is_running = True
            
            self.logger.info("Display manager initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize display manager", error=str(e))
            raise
    
    async def stop(self) -> None:
        """Stop the display manager."""
        self.logger.info("Stopping display manager")
        self.is_running = False
    
    def render_ad_with_overlay(self, 
                              ad_frame: np.ndarray,
                              parking_spaces: List[ParkingSpace],
                              vehicles: List[VehicleInfo]) -> np.ndarray:
        """Combine ad display with detection overlay.
        
        Args:
            ad_frame: Base ad/content frame
            parking_spaces: List of parking spaces with occupancy
            vehicles: List of detected vehicles
            
        Returns:
            Combined frame with overlay
        """
        if not self.is_initialized:
            return ad_frame
        
        # Create a copy of the ad frame
        display_frame = ad_frame.copy()
        
        try:
            # Create overlay for parking spaces and vehicles
            overlay = self._create_detection_overlay(display_frame.shape, parking_spaces, vehicles)
            
            # Blend overlay with ad frame
            if overlay is not None:
                display_frame = self._blend_overlay(display_frame, overlay)
            
            # Add status information
            display_frame = self._add_status_overlay(display_frame, parking_spaces, vehicles)
            
            self.current_frame = display_frame
            self.last_update = time.time()
            
            return display_frame
            
        except Exception as e:
            self.logger.error("Failed to render display overlay", error=str(e))
            return ad_frame
    
    def create_status_overlay(self, occupancy_data: Dict[str, Any]) -> np.ndarray:
        """Generate real-time parking status overlay.
        
        Args:
            occupancy_data: Dictionary with occupancy statistics
            
        Returns:
            Status overlay image
        """
        # Create a status overlay image (e.g., 400x300)
        overlay_height, overlay_width = 300, 400
        overlay = np.zeros((overlay_height, overlay_width, 3), dtype=np.uint8)
        
        # Background
        overlay.fill(50)  # Dark gray background
        
        # Title
        title = "Parking Status"
        title_size = cv2.getTextSize(title, self.font, 1.0, 2)[0]
        title_x = (overlay_width - title_size[0]) // 2
        cv2.putText(overlay, title, (title_x, 40), self.font, 1.0, (255, 255, 255), 2)
        
        # Statistics
        stats = [
            f"Total Spaces: {occupancy_data.get('total_spaces', 0)}",
            f"Occupied: {occupancy_data.get('occupied_spaces', 0)}",
            f"Available: {occupancy_data.get('free_spaces', 0)}",
            f"Occupancy: {occupancy_data.get('occupancy_rate', 0)*100:.1f}%",
            f"Vehicles: {len(occupancy_data.get('vehicles', []))}"
        ]
        
        y_pos = 80
        for stat in stats:
            cv2.putText(overlay, stat, (20, y_pos), self.font, 0.6, (200, 200, 200), 1)
            y_pos += 30
        
        # Status indicator
        occupancy_rate = occupancy_data.get('occupancy_rate', 0)
        if occupancy_rate < 0.7:
            status_color = (0, 255, 0)  # Green - good availability
            status_text = "Good Availability"
        elif occupancy_rate < 0.9:
            status_color = (0, 255, 255)  # Yellow - limited availability
            status_text = "Limited Availability"
        else:
            status_color = (0, 0, 255)  # Red - full/nearly full
            status_text = "Nearly Full"
        
        cv2.rectangle(overlay, (20, 220), (380, 260), status_color, -1)
        cv2.putText(overlay, status_text, (30, 245), self.font, 0.7, (0, 0, 0), 2)
        
        # Timestamp
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        cv2.putText(overlay, f"Updated: {timestamp}", (20, 285), self.font, 0.4, (150, 150, 150), 1)
        
        return overlay
    
    def _create_detection_overlay(self, 
                                frame_shape: Tuple[int, int, int],
                                parking_spaces: List[ParkingSpace],
                                vehicles: List[VehicleInfo]) -> Optional[np.ndarray]:
        """Create detection overlay with parking spaces and vehicles.
        
        Args:
            frame_shape: Shape of the base frame (height, width, channels)
            parking_spaces: List of parking spaces
            vehicles: List of detected vehicles
            
        Returns:
            Overlay image or None if no detections
        """
        if not parking_spaces and not vehicles:
            return None
        
        height, width = frame_shape[:2]
        overlay = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Draw parking spaces
        for space in parking_spaces:
            self._draw_parking_space(overlay, space)
        
        # Draw vehicle detections
        for vehicle in vehicles:
            self._draw_vehicle(overlay, vehicle)
        
        return overlay
    
    def _draw_parking_space(self, overlay: np.ndarray, space: ParkingSpace) -> None:
        """Draw a parking space on the overlay.
        
        Args:
            overlay: Overlay image to draw on
            space: Parking space to draw
        """
        # Convert coordinates to numpy array
        points = np.array(space.coordinates, np.int32)
        points = points.reshape((-1, 1, 2))
        
        # Choose color based on occupancy
        if space.is_occupied:
            color = self.colors["occupied_space"]
        else:
            color = self.colors["free_space"]
        
        # Draw parking space polygon
        cv2.polylines(overlay, [points], True, color, self.line_thickness)
        
        # Fill with semi-transparent color
        cv2.fillPoly(overlay, [points], color)
        
        # Draw space ID
        if space.coordinates:
            center_x = int(np.mean([p[0] for p in space.coordinates]))
            center_y = int(np.mean([p[1] for p in space.coordinates]))
            
            # Space ID text
            text = space.space_id
            text_size = cv2.getTextSize(text, self.font, self.font_scale, self.line_thickness)[0]
            text_x = center_x - text_size[0] // 2
            text_y = center_y + text_size[1] // 2
            
            # Text background
            cv2.rectangle(overlay, 
                         (text_x - 5, text_y - text_size[1] - 5),
                         (text_x + text_size[0] + 5, text_y + 5),
                         (0, 0, 0), -1)
            
            # Text
            cv2.putText(overlay, text, (text_x, text_y), self.font, 
                       self.font_scale, (255, 255, 255), self.line_thickness)
            
            # Confidence indicator (if occupied)
            if space.is_occupied and space.confidence > 0:
                conf_text = f"{space.confidence:.0%}"
                cv2.putText(overlay, conf_text, (text_x, text_y + 20), self.font,
                           self.font_scale * 0.7, (255, 255, 0), 1)
    
    def _draw_vehicle(self, overlay: np.ndarray, vehicle: VehicleInfo) -> None:
        """Draw a vehicle detection on the overlay.
        
        Args:
            overlay: Overlay image to draw on
            vehicle: Vehicle information to draw
        """
        x1, y1, x2, y2 = vehicle.bbox
        color = self.colors["vehicle"]
        
        # Draw bounding box
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, self.line_thickness)
        
        # Vehicle type label
        label = f"{vehicle.vehicle_type}"
        if self.config.display.show_confidence:
            label += f" {vehicle.confidence:.0%}"
        
        # Label background
        label_size = cv2.getTextSize(label, self.font, self.font_scale, 1)[0]
        cv2.rectangle(overlay, (x1, y1 - label_size[1] - 10), 
                     (x1 + label_size[0] + 10, y1), (0, 0, 0), -1)
        
        # Label text
        cv2.putText(overlay, label, (x1 + 5, y1 - 5), self.font,
                   self.font_scale, color, 1)
        
        # Additional vehicle info
        if self.config.display.show_vehicle_info and vehicle.color:
            info_text = vehicle.color
            cv2.putText(overlay, info_text, (x1 + 5, y2 - 5), self.font,
                       self.font_scale * 0.6, (200, 200, 200), 1)
    
    def _blend_overlay(self, base_frame: np.ndarray, overlay: np.ndarray) -> np.ndarray:
        """Blend overlay with base frame using configured opacity.
        
        Args:
            base_frame: Base image frame
            overlay: Overlay image
            
        Returns:
            Blended image
        """
        # Create mask for non-black pixels in overlay
        mask = np.any(overlay != [0, 0, 0], axis=2)
        
        # Blend only where overlay has content
        result = base_frame.copy()
        if np.any(mask):
            alpha = self.overlay_opacity
            result[mask] = (alpha * overlay[mask] + (1 - alpha) * base_frame[mask]).astype(np.uint8)
        
        return result
    
    def _add_status_overlay(self, 
                           frame: np.ndarray,
                           parking_spaces: List[ParkingSpace],
                           vehicles: List[VehicleInfo]) -> np.ndarray:
        """Add status information overlay to frame.
        
        Args:
            frame: Base frame
            parking_spaces: List of parking spaces
            vehicles: List of vehicles
            
        Returns:
            Frame with status overlay
        """
        if not parking_spaces:
            return frame
        
        # Calculate statistics
        total_spaces = len(parking_spaces)
        occupied_spaces = sum(1 for space in parking_spaces if space.is_occupied)
        occupancy_rate = occupied_spaces / total_spaces if total_spaces > 0 else 0
        
        # Status position
        position = self.config.display.status_position
        height, width = frame.shape[:2]
        
        if position == "top_right":
            x, y = width - 300, 30
        elif position == "top_left":
            x, y = 30, 30
        elif position == "bottom_right":
            x, y = width - 300, height - 150
        else:  # bottom_left
            x, y = 30, height - 150
        
        # Status background
        cv2.rectangle(frame, (x - 10, y - 10), (x + 280, y + 120), (0, 0, 0), -1)
        cv2.rectangle(frame, (x - 10, y - 10), (x + 280, y + 120), (100, 100, 100), 2)
        
        # Status text
        status_lines = [
            f"Parking Status",
            f"Spaces: {occupied_spaces}/{total_spaces}",
            f"Available: {total_spaces - occupied_spaces}",
            f"Occupancy: {occupancy_rate*100:.1f}%",
            f"Vehicles: {len(vehicles)}"
        ]
        
        for i, line in enumerate(status_lines):
            y_pos = y + i * 25
            if i == 0:  # Title
                cv2.putText(frame, line, (x, y_pos), self.font, 0.7, (255, 255, 255), 2)
            else:
                cv2.putText(frame, line, (x, y_pos), self.font, 0.5, (200, 200, 200), 1)
        
        # Add timestamp
        timestamp = time.strftime("%H:%M:%S")
        cv2.putText(frame, timestamp, (x, y + 110), self.font, 0.4, (150, 150, 150), 1)
        
        return frame
    
    def get_current_frame(self) -> Optional[np.ndarray]:
        """Get the current display frame.
        
        Returns:
            Current frame or None if not available
        """
        return self.current_frame.copy() if self.current_frame is not None else None
    
    def get_display_status(self) -> Dict[str, Any]:
        """Get display manager status.
        
        Returns:
            Dictionary with display status information
        """
        return {
            "is_running": self.is_running,
            "is_initialized": self.is_initialized,
            "last_update": self.last_update,
            "overlay_enabled": self.config.display.enabled,
            "overlay_opacity": self.overlay_opacity,
            "status_position": self.config.display.status_position
        }