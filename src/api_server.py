"""FastAPI server for oaParkingMonitor service."""

import asyncio
import time
from typing import List, Dict, Any, Optional
import logging

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import structlog

from .core.detection import ParkingLotStatus, DetectionResult, ParkingSpace, VehicleInfo
from .config_manager import ConfigManager


# Pydantic models for API responses
class HealthResponse(BaseModel):
    service: str = "parking_monitor"
    status: str
    version: str = "0.1.0"
    uptime: float
    timestamp: float
    metrics: Dict[str, Any]


class ParkingStatusResponse(BaseModel):
    total_spaces: int
    occupied_spaces: int
    free_spaces: int
    occupancy_rate: float
    last_updated: float
    spaces: List[Dict[str, Any]]
    vehicles: List[Dict[str, Any]]


class MetricsResponse(BaseModel):
    performance: Dict[str, float]
    detection: Dict[str, Any]
    system: Dict[str, Any]
    timestamp: float


class WebSocketManager:
    """Manages WebSocket connections for real-time streaming."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.logger = structlog.get_logger("websocket_manager")
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.logger.info("WebSocket client connected", 
                        total_connections=len(self.active_connections))
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            self.logger.info("WebSocket client disconnected",
                           total_connections=len(self.active_connections))
    
    async def broadcast(self, data: Dict[str, Any]):
        """Broadcast data to all connected WebSocket clients."""
        if not self.active_connections:
            return
        
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except WebSocketDisconnect:
                disconnected.append(connection)
            except Exception as e:
                self.logger.error("Error sending WebSocket data", 
                                error=str(e))
                disconnected.append(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            self.disconnect(connection)


def create_app(detector=None, display_manager=None, health_monitor=None, config=None) -> FastAPI:
    """Create and configure FastAPI application."""
    
    app = FastAPI(
        title="oaParkingMonitor API",
        description="YOLOv11-based parking detection system optimized for Mac Mini M1",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    logger = structlog.get_logger("api_server")
    websocket_manager = WebSocketManager()
    
    # Configure CORS
    if config and config.api.cors_enabled:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.api.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["*"],
        )
    
    # Store components in app state
    app.state.detector = detector
    app.state.display_manager = display_manager
    app.state.health_monitor = health_monitor
    app.state.config = config
    app.state.websocket_manager = websocket_manager
    app.state.start_time = time.time()
    
    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """Service health check endpoint."""
        try:
            current_time = time.time()
            uptime = current_time - app.state.start_time
            
            # Get health metrics
            metrics = {}
            if app.state.detector:
                metrics.update(app.state.detector.get_performance_metrics())
            
            if app.state.health_monitor:
                health_data = await app.state.health_monitor.get_health_status()
                metrics.update(health_data)
            
            return HealthResponse(
                status="healthy",
                uptime=uptime,
                timestamp=current_time,
                metrics=metrics
            )
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/parking/status", response_model=ParkingStatusResponse)
    async def get_parking_status():
        """Get current parking lot occupancy status."""
        try:
            if not app.state.detector:
                raise HTTPException(status_code=503, detail="Detector not available")
            
            # Get current parking spaces and vehicles
            parking_spaces = app.state.detector.parking_spaces
            current_detections = app.state.detector.current_detections
            
            # Classify vehicles from current detections
            vehicles = await app.state.detector.classify_vehicles(current_detections)
            
            # Create parking lot status
            parking_status = ParkingLotStatus.from_spaces(parking_spaces, vehicles)
            
            return ParkingStatusResponse(
                total_spaces=parking_status.total_spaces,
                occupied_spaces=parking_status.occupied_spaces,
                free_spaces=parking_status.free_spaces,
                occupancy_rate=parking_status.occupancy_rate,
                last_updated=parking_status.last_updated,
                spaces=[space.to_dict() for space in parking_status.spaces],
                vehicles=[vehicle.to_dict() for vehicle in parking_status.vehicles]
            )
            
        except Exception as e:
            logger.error("Failed to get parking status", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/parking/metrics", response_model=MetricsResponse)
    async def get_performance_metrics():
        """Get performance and detection metrics."""
        try:
            current_time = time.time()
            
            # Performance metrics
            performance = {}
            if app.state.detector:
                performance = app.state.detector.get_performance_metrics()
            
            # Detection metrics
            detection = {
                "active_detections": len(app.state.detector.current_detections) if app.state.detector else 0,
                "parking_spaces": len(app.state.detector.parking_spaces) if app.state.detector else 0,
                "last_detection_age": performance.get("last_detection_age", 0)
            }
            
            # System metrics
            system = {}
            if app.state.health_monitor:
                system = await app.state.health_monitor.get_system_metrics()
            
            return MetricsResponse(
                performance=performance,
                detection=detection,
                system=system,
                timestamp=current_time
            )
            
        except Exception as e:
            logger.error("Failed to get metrics", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.websocket("/api/parking/stream")
    async def parking_stream_websocket(websocket: WebSocket):
        """Real-time parking detection stream via WebSocket."""
        await websocket_manager.connect(websocket)
        
        try:
            while True:
                # Wait for client messages (ping/pong for keep-alive)
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                    if data == "ping":
                        await websocket.send_text("pong")
                except asyncio.TimeoutError:
                    # Send current parking status every second
                    if app.state.detector:
                        parking_spaces = app.state.detector.parking_spaces
                        current_detections = app.state.detector.current_detections
                        vehicles = await app.state.detector.classify_vehicles(current_detections)
                        
                        status = ParkingLotStatus.from_spaces(parking_spaces, vehicles)
                        
                        await websocket.send_json({
                            "type": "parking_update",
                            "timestamp": time.time(),
                            "data": status.to_dict()
                        })
                
        except WebSocketDisconnect:
            websocket_manager.disconnect(websocket)
        except Exception as e:
            logger.error("WebSocket error", error=str(e))
            websocket_manager.disconnect(websocket)
    
    @app.get("/api/parking/spaces")
    async def get_parking_spaces():
        """Get parking space definitions and current status."""
        try:
            if not app.state.detector:
                raise HTTPException(status_code=503, detail="Detector not available")
            
            spaces = [space.to_dict() for space in app.state.detector.parking_spaces]
            
            return {
                "spaces": spaces,
                "total_count": len(spaces),
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error("Failed to get parking spaces", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/parking/vehicles")
    async def get_vehicles():
        """Get current vehicle detections."""
        try:
            if not app.state.detector:
                raise HTTPException(status_code=503, detail="Detector not available")
            
            current_detections = app.state.detector.current_detections
            vehicles = await app.state.detector.classify_vehicles(current_detections)
            
            return {
                "vehicles": [vehicle.to_dict() for vehicle in vehicles],
                "total_count": len(vehicles),
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error("Failed to get vehicles", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/")
    async def root():
        """Root endpoint with service information."""
        return {
            "service": "oaParkingMonitor",
            "version": "0.1.0",
            "description": "YOLOv11-based parking detection system optimized for Mac Mini M1",
            "endpoints": {
                "health": "/health",
                "parking_status": "/api/parking/status",
                "metrics": "/api/parking/metrics",
                "stream": "/api/parking/stream",
                "spaces": "/api/parking/spaces",
                "vehicles": "/api/parking/vehicles",
                "docs": "/docs"
            }
        }
    
    # Add startup event
    @app.on_event("startup")
    async def startup_event():
        logger.info("oaParkingMonitor API server started",
                   version="0.1.0",
                   cors_enabled=config.api.cors_enabled if config else False)
    
    # Add shutdown event  
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("oaParkingMonitor API server shutting down")
    
    return app