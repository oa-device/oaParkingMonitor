"""
Real-time Parking Monitor Dashboard
Temporary monitoring interface for detection visualization
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import asyncio
import logging
from typing import List, Dict, Any


class WebSocketManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.logger = logging.getLogger(__name__)
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def broadcast_data(self, data: dict):
        if not self.active_connections:
            return
            
        # Send to all connected clients
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception as e:
                self.logger.warning(f"Failed to send data to WebSocket: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


def create_dashboard_app(parking_service) -> FastAPI:
    """Create dashboard FastAPI application"""
    
    dashboard_app = FastAPI(title="Parking Monitor Dashboard")
    
    # Templates directory
    templates_dir = Path(__file__).parent / "templates"
    templates_dir.mkdir(exist_ok=True)
    templates = Jinja2Templates(directory=templates_dir)
    
    # WebSocket manager for real-time updates
    websocket_manager = WebSocketManager()
    
    # Background task for broadcasting updates
    async def broadcast_updates():
        """Background task to broadcast parking data updates"""
        while True:
            try:
                # Get latest data from parking service
                stats = await parking_service.get_detection_stats()
                health = await parking_service.get_health_status()
                
                # Prepare dashboard data
                dashboard_data = {
                    "timestamp": stats.get("last_update"),
                    "stats": {
                        "total_frames": stats.get("total_frames", 0),
                        "detections": stats.get("detections", 0),
                        "vehicles_detected": stats.get("vehicles_detected", 0),
                        "processing_fps": stats.get("processing_fps", 0),
                        "total_spaces": stats.get("total_spaces", 4),
                        "occupied_spaces": stats.get("occupied_spaces", 0),
                        "occupancy_rate": round(stats.get("occupancy_rate", 0) * 100, 1),
                        "uptime": stats.get("uptime_seconds", 0)
                    },
                    "health": {
                        "score": health.get("health_score", 0),
                        "status": health.get("running", False),
                        "cpu_percent": health.get("system", {}).get("cpu_percent", 0),
                        "memory_percent": health.get("system", {}).get("memory_percent", 0)
                    }
                }
                
                # Broadcast to all connected clients
                await websocket_manager.broadcast_data(dashboard_data)
                
            except Exception as e:
                logging.error(f"Broadcast update error: {e}")
            
            await asyncio.sleep(2)  # Update every 2 seconds
    
    # Store broadcast function for startup event
    dashboard_app.state.broadcast_updates = broadcast_updates
    
    @dashboard_app.get("/", response_class=HTMLResponse)
    async def dashboard_home(request: Request):
        """Main dashboard page"""
        # Get initial data
        try:
            stats = await parking_service.get_detection_stats()
            health = await parking_service.get_health_status()
        except:
            stats = {}
            health = {}
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "stats": stats,
            "health": health
        })
    
    @dashboard_app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time updates"""
        await websocket_manager.connect(websocket)
        try:
            while True:
                # Keep connection alive
                await websocket.receive_text()
        except WebSocketDisconnect:
            websocket_manager.disconnect(websocket)
    
    @dashboard_app.get("/api/data")
    async def get_dashboard_data():
        """API endpoint for dashboard data"""
        stats = await parking_service.get_detection_stats()
        health = await parking_service.get_health_status()
        
        return {
            "stats": stats,
            "health": health,
            "timestamp": stats.get("last_update")
        }
    
    # Add startup event to launch background task
    @dashboard_app.on_event("startup")
    async def startup_event():
        asyncio.create_task(broadcast_updates())
    
    return dashboard_app