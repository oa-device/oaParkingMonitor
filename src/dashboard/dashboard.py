"""
Real-time Parking Monitor Dashboard
Temporary monitoring interface for detection visualization
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import json
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
                health = {"running": parking_service.running, "uptime": parking_service.get_uptime()}
                
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
            health = {"running": parking_service.running, "uptime": parking_service.get_uptime()}
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
    
    # Create dashboard HTML template
    _create_dashboard_template(templates_dir)
    
    return dashboard_app


def _create_dashboard_template(templates_dir: Path):
    """Create the dashboard HTML template"""
    
    dashboard_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Parking Monitor Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .dashboard {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            font-weight: 300;
        }
        
        .status-indicator {
            display: inline-block;
            padding: 8px 20px;
            background: rgba(255,255,255,0.2);
            border-radius: 50px;
            font-size: 0.9rem;
            backdrop-filter: blur(10px);
        }
        
        .content {
            padding: 40px;
        }
        
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 30px;
            margin-bottom: 40px;
        }
        
        .metric-card {
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            border-left: 5px solid #4facfe;
            transition: transform 0.3s ease;
        }
        
        .metric-card:hover {
            transform: translateY(-5px);
        }
        
        .metric-title {
            color: #666;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }
        
        .metric-value {
            font-size: 2.5rem;
            font-weight: 700;
            color: #333;
            margin-bottom: 5px;
        }
        
        .metric-unit {
            color: #999;
            font-size: 0.9rem;
        }
        
        .parking-spaces {
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        
        .parking-title {
            font-size: 1.5rem;
            color: #333;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .spaces-container {
            display: flex;
            justify-content: center;
            gap: 20px;
            flex-wrap: wrap;
        }
        
        .parking-space {
            width: 100px;
            height: 60px;
            border: 3px solid #ddd;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            transition: all 0.3s ease;
        }
        
        .parking-space.occupied {
            background: #ff6b6b;
            border-color: #ff5252;
            color: white;
        }
        
        .parking-space.free {
            background: #51cf66;
            border-color: #40c057;
            color: white;
        }
        
        .system-health {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }
        
        .health-item {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            text-align: center;
        }
        
        .health-value {
            font-size: 1.5rem;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .health-label {
            color: #666;
            font-size: 0.8rem;
            text-transform: uppercase;
        }
        
        .footer {
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #666;
        }
        
        .last-update {
            font-size: 0.8rem;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .live-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            background: #51cf66;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
    </style>
</head>
<body>
    <div class="dashboard">
        <div class="header">
            <h1>🚗 Parking Monitor Dashboard</h1>
            <div class="status-indicator">
                <span class="live-indicator"></span>
                <span id="connectionStatus">Live Monitoring</span>
            </div>
        </div>
        
        <div class="content">
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-title">Vehicles Detected</div>
                    <div class="metric-value" id="vehiclesDetected">0</div>
                    <div class="metric-unit">vehicles</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-title">Occupancy Rate</div>
                    <div class="metric-value" id="occupancyRate">0</div>
                    <div class="metric-unit">%</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-title">Processing FPS</div>
                    <div class="metric-value" id="processingFps">0</div>
                    <div class="metric-unit">fps</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-title">Total Frames</div>
                    <div class="metric-value" id="totalFrames">0</div>
                    <div class="metric-unit">frames</div>
                </div>
            </div>
            
            <div class="parking-spaces">
                <h3 class="parking-title">Parking Spaces Status</h3>
                <div class="spaces-container" id="parkingSpaces">
                    <!-- Parking spaces will be populated by JavaScript -->
                </div>
            </div>
            
            <div class="system-health">
                <div class="health-item">
                    <div class="health-value" id="healthScore">0</div>
                    <div class="health-label">Health Score</div>
                </div>
                
                <div class="health-item">
                    <div class="health-value" id="cpuUsage">0%</div>
                    <div class="health-label">CPU Usage</div>
                </div>
                
                <div class="health-item">
                    <div class="health-value" id="memoryUsage">0%</div>
                    <div class="health-label">Memory Usage</div>
                </div>
                
                <div class="health-item">
                    <div class="health-value" id="uptime">0s</div>
                    <div class="health-label">Uptime</div>
                </div>
            </div>
        </div>
        
        <div class="footer">
            <div class="last-update">Last updated: <span id="lastUpdate">Never</span></div>
        </div>
    </div>

    <script>
        // WebSocket connection for real-time updates
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/dashboard/ws`;
        let ws;
        
        function connectWebSocket() {
            ws = new WebSocket(wsUrl);
            
            ws.onopen = function() {
                console.log('WebSocket connected');
                document.getElementById('connectionStatus').textContent = 'Live Monitoring';
            };
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                updateDashboard(data);
            };
            
            ws.onclose = function() {
                console.log('WebSocket disconnected');
                document.getElementById('connectionStatus').textContent = 'Disconnected';
                // Reconnect after 3 seconds
                setTimeout(connectWebSocket, 3000);
            };
            
            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
            };
        }
        
        function updateDashboard(data) {
            const stats = data.stats || {};
            const health = data.health || {};
            
            // Update metrics
            document.getElementById('vehiclesDetected').textContent = stats.vehicles_detected || 0;
            document.getElementById('occupancyRate').textContent = stats.occupancy_rate || 0;
            document.getElementById('processingFps').textContent = (stats.processing_fps || 0).toFixed(1);
            document.getElementById('totalFrames').textContent = (stats.total_frames || 0).toLocaleString();
            
            // Update parking spaces
            updateParkingSpaces(stats.total_spaces || 4, stats.occupied_spaces || 0);
            
            // Update health metrics
            document.getElementById('healthScore').textContent = Math.round(health.score || 0);
            document.getElementById('cpuUsage').textContent = Math.round(health.cpu_percent || 0) + '%';
            document.getElementById('memoryUsage').textContent = Math.round(health.memory_percent || 0) + '%';
            document.getElementById('uptime').textContent = formatUptime(stats.uptime || 0);
            
            // Update last update time
            document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
        }
        
        function updateParkingSpaces(totalSpaces, occupiedSpaces) {
            const container = document.getElementById('parkingSpaces');
            container.innerHTML = '';
            
            for (let i = 0; i < totalSpaces; i++) {
                const space = document.createElement('div');
                space.className = `parking-space ${i < occupiedSpaces ? 'occupied' : 'free'}`;
                space.textContent = `Space ${i + 1}`;
                container.appendChild(space);
            }
        }
        
        function formatUptime(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = Math.floor(seconds % 60);
            
            if (hours > 0) {
                return `${hours}h ${minutes}m`;
            } else if (minutes > 0) {
                return `${minutes}m ${secs}s`;
            } else {
                return `${secs}s`;
            }
        }
        
        // Initialize WebSocket connection
        connectWebSocket();
        
        // Initial load of data
        fetch('/dashboard/api/data')
            .then(response => response.json())
            .then(data => {
                updateDashboard({
                    stats: data.stats,
                    health: data.health
                });
            })
            .catch(error => console.error('Initial data load error:', error));
    </script>
</body>
</html>"""
    
    template_file = templates_dir / "dashboard.html"
    with open(template_file, "w") as f:
        f.write(dashboard_html)