"""
YHU Dashboard integration client for oaParkingMonitor

Bridges state-based parking detection with event-driven YHU Dashboard
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

import httpx

from ..config import YHUConfig


class YHUIntegration:
    """
    Bridges oaParkingMonitor with YHU Dashboard
    
    Converts state-based parking detection to event-driven updates
    """
    
    def __init__(self, config: YHUConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.previous_state = {
            "occupied_spaces": 0,
            "vehicles": [],
            "last_update": None
        }
        self.running = False
        self._http_client = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        if self.config.enabled:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout),
                headers={
                    "x-api-key": self.config.api_key,
                    "Content-Type": "application/json"
                }
            )
            self.logger.info("YHU integration initialized")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._http_client:
            await self._http_client.aclose()
            self.logger.info("YHU integration closed")
    
    async def start(self):
        """Start YHU integration service"""
        if not self.config.enabled:
            self.logger.info("YHU integration disabled")
            return
            
        if not self.config.lot_id:
            self.logger.error("YHU integration enabled but lot_id not configured")
            return
            
        self.running = True
        self.logger.info(f"YHU integration started for lot {self.config.lot_id}")
        
        # Test connection
        await self._test_connection()
    
    async def stop(self):
        """Stop YHU integration service"""
        self.running = False
        self.logger.info("YHU integration stopped")
    
    async def process_detection_update(self, current_state: Dict[str, Any]):
        """
        Process parking detection update and send events to YHU
        
        Args:
            current_state: Current parking detection state
        """
        if not self.config.enabled or not self.running:
            return
            
        try:
            # Check for occupancy changes
            await self._process_occupancy_changes(current_state)
            
            # Send state update to YHU
            await self._send_state_update(current_state)
            
            # Update previous state
            self.previous_state = {
                "occupied_spaces": current_state.get("occupied_spaces", 0),
                "vehicles": current_state.get("vehicles", []),
                "last_update": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error processing detection update: {e}")
    
    async def _process_occupancy_changes(self, current_state: Dict[str, Any]):
        """Generate entry/exit events from occupancy changes"""
        current_occupied = current_state.get("occupied_spaces", 0)
        previous_occupied = self.previous_state.get("occupied_spaces", 0)
        
        delta = current_occupied - previous_occupied
        
        if delta != 0:
            # Generate event for YHU ingestion
            event = {
                "lotId": self.config.lot_id,
                "delta": delta,
                "vehicleClass": self._get_dominant_vehicle_class(current_state),
                "make": None,  # Not available from detection
                "ts": datetime.now().isoformat()
            }
            
            await self._send_parking_event(event)
            
            action = "entry" if delta > 0 else "exit"
            self.logger.info(f"Parking {action} detected: delta={delta}, occupied={current_occupied}")
    
    async def _send_parking_event(self, event: Dict[str, Any]):
        """Send parking event to YHU Dashboard"""
        if not self._http_client:
            return
            
        endpoint = f"{self.config.api_url}/api/ingest/parking"
        
        for attempt in range(self.config.retry_attempts):
            try:
                response = await self._http_client.post(endpoint, json=event)
                response.raise_for_status()
                
                self.logger.debug(f"Event sent to YHU: {event}")
                return
                
            except httpx.RequestError as e:
                self.logger.warning(f"HTTP error sending event (attempt {attempt + 1}): {e}")
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    self.logger.error(f"Failed to send event after {self.config.retry_attempts} attempts")
            
            except httpx.HTTPStatusError as e:
                self.logger.error(f"HTTP {e.response.status_code} error sending event: {e}")
                break  # Don't retry on 4xx errors
    
    async def _send_state_update(self, current_state: Dict[str, Any]):
        """Send full state update to YHU Dashboard"""
        if not self._http_client:
            return
            
        state_data = {
            "lotId": self.config.lot_id,
            "occupied_spaces": current_state.get("occupied_spaces", 0),
            "total_spaces": current_state.get("total_spaces", 4),
            "occupancy_rate": current_state.get("occupancy_rate", 0.0),
            "vehicles": current_state.get("vehicles", []),
            "processing_fps": current_state.get("processing_fps", 0.0),
            "last_detection": current_state.get("last_detection"),
            "ts": datetime.now().isoformat()
        }
        
        endpoint = f"{self.config.api_url}/api/ingest/parking/state"
        
        try:
            response = await self._http_client.post(endpoint, json=state_data)
            response.raise_for_status()
            
            self.logger.debug(f"State update sent to YHU: lot={self.config.lot_id}")
            
        except Exception as e:
            self.logger.warning(f"Failed to send state update: {e}")
    
    def _get_dominant_vehicle_class(self, current_state: Dict[str, Any]) -> str:
        """Get the dominant vehicle class from current detections"""
        vehicles = current_state.get("vehicles", [])
        
        if not vehicles:
            return "CAR"  # Default
        
        # Count vehicle classes
        class_counts = {}
        for vehicle in vehicles:
            vehicle_class = vehicle.get("class_name", "car").upper()
            # Map common detection classes to YHU enum values
            if vehicle_class in ["CAR", "AUTOMOBILE"]:
                vehicle_class = "SEDAN"
            elif vehicle_class in ["TRUCK"]:
                vehicle_class = "PICKUP"
            elif vehicle_class in ["BUS"]:
                vehicle_class = "VAN"
            elif vehicle_class in ["MOTORCYCLE", "BIKE"]:
                vehicle_class = "MOTORCYCLE"
            else:
                vehicle_class = "OTHER"
                
            class_counts[vehicle_class] = class_counts.get(vehicle_class, 0) + 1
        
        # Return most common class
        return max(class_counts.items(), key=lambda x: x[1])[0] if class_counts else "SEDAN"
    
    async def _test_connection(self):
        """Test connection to YHU Dashboard"""
        if not self._http_client:
            return False
            
        try:
            endpoint = f"{self.config.api_url}/api/healthz"
            response = await self._http_client.get(endpoint)
            response.raise_for_status()
            
            self.logger.info("YHU Dashboard connection test successful")
            return True
            
        except Exception as e:
            self.logger.error(f"YHU Dashboard connection test failed: {e}")
            return False
    
    async def get_integration_status(self) -> Dict[str, Any]:
        """Get current integration status"""
        return {
            "enabled": self.config.enabled,
            "running": self.running,
            "lot_id": self.config.lot_id,
            "api_url": self.config.api_url,
            "last_update": self.previous_state.get("last_update"),
            "connection_healthy": await self._test_connection() if self.config.enabled else False
        }
    
    async def update_config(self, new_config: YHUConfig):
        """Update integration configuration"""
        self.config = new_config
        
        if self.config.enabled and not self.running:
            await self.start()
        elif not self.config.enabled and self.running:
            await self.stop()
            
        self.logger.info("YHU integration configuration updated")