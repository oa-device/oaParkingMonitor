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
        :root {
            --color-primary: #1e293b;
            --color-secondary: #475569;
            --color-accent: #3b82f6;
            --color-success: #10b981;
            --color-warning: #f59e0b;
            --color-danger: #ef4444;
            --color-bg-primary: #f8fafc;
            --color-bg-secondary: #ffffff;
            --color-text-primary: #0f172a;
            --color-text-secondary: #64748b;
            --color-border: #e2e8f0;
            --color-border-light: #f1f5f9;
            --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
            --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
            --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
            --radius: 6px;
            --radius-lg: 8px;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', sans-serif;
            background-color: var(--color-bg-primary);
            color: var(--color-text-primary);
            line-height: 1.5;
            min-height: 100vh;
        }
        
        .dashboard-container {
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        .dashboard-header {
            background-color: var(--color-bg-secondary);
            border-bottom: 1px solid var(--color-border);
            padding: 1rem 2rem;
            position: sticky;
            top: 0;
            z-index: 10;
            box-shadow: var(--shadow-sm);
        }
        
        .header-content {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .dashboard-title {
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--color-text-primary);
        }
        
        .status-indicator {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            background-color: var(--color-bg-primary);
            border: 1px solid var(--color-border);
            border-radius: var(--radius);
            font-size: 0.875rem;
            color: var(--color-text-secondary);
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: var(--color-success);
            animation: pulse 2s infinite;
        }
        
        .status-dot.disconnected {
            background-color: var(--color-danger);
            animation: none;
        }
        
        .dashboard-content {
            flex: 1;
            padding: 2rem;
            max-width: 1400px;
            margin: 0 auto;
            width: 100%;
        }
        
        .metrics-section {
            margin-bottom: 2rem;
        }
        
        .section-title {
            font-size: 1.125rem;
            font-weight: 600;
            color: var(--color-text-primary);
            margin-bottom: 1rem;
        }
        
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .metric-card {
            background-color: var(--color-bg-secondary);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-lg);
            padding: 1.5rem;
            box-shadow: var(--shadow-sm);
            transition: box-shadow 0.15s ease;
        }
        
        .metric-card:hover {
            box-shadow: var(--shadow-md);
        }
        
        .metric-header {
            display: flex;
            justify-content: between;
            align-items: flex-start;
            margin-bottom: 0.75rem;
        }
        
        .metric-title {
            font-size: 0.875rem;
            font-weight: 500;
            color: var(--color-text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.025em;
        }
        
        .metric-value {
            font-size: 2rem;
            font-weight: 700;
            color: var(--color-text-primary);
            font-variant-numeric: tabular-nums;
            line-height: 1;
            margin-bottom: 0.25rem;
        }
        
        .metric-unit {
            font-size: 0.75rem;
            color: var(--color-text-secondary);
            font-weight: 500;
        }
        
        .parking-section {
            background-color: var(--color-bg-secondary);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-lg);
            padding: 1.5rem;
            box-shadow: var(--shadow-sm);
            margin-bottom: 2rem;
        }
        
        .parking-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }
        
        .parking-space {
            aspect-ratio: 3/2;
            border: 2px solid var(--color-border);
            border-radius: var(--radius);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.875rem;
            font-weight: 600;
            transition: all 0.15s ease;
            position: relative;
        }
        
        .parking-space.occupied {
            background-color: #fef2f2;
            border-color: var(--color-danger);
            color: var(--color-danger);
        }
        
        .parking-space.available {
            background-color: #f0fdf4;
            border-color: var(--color-success);
            color: var(--color-success);
        }
        
        .system-health {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
        }
        
        .health-card {
            background-color: var(--color-bg-secondary);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-lg);
            padding: 1.25rem;
            box-shadow: var(--shadow-sm);
            text-align: center;
        }
        
        .health-value {
            font-size: 1.5rem;
            font-weight: 700;
            font-variant-numeric: tabular-nums;
            margin-bottom: 0.25rem;
        }
        
        .health-label {
            font-size: 0.75rem;
            color: var(--color-text-secondary);
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.025em;
        }
        
        .dashboard-footer {
            background-color: var(--color-bg-secondary);
            border-top: 1px solid var(--color-border);
            padding: 1rem 2rem;
            text-align: center;
        }
        
        .last-update {
            font-size: 0.75rem;
            color: var(--color-text-secondary);
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        /* Status indicators */
        .health-value.excellent { color: var(--color-success); }
        .health-value.good { color: var(--color-success); }
        .health-value.warning { color: var(--color-warning); }
        .health-value.critical { color: var(--color-danger); }
        
        /* Responsive design */
        @media (max-width: 768px) {
            .dashboard-content {
                padding: 1rem;
            }
            
            .header-content {
                flex-direction: column;
                gap: 1rem;
                align-items: flex-start;
            }
            
            .metrics-grid {
                grid-template-columns: 1fr;
            }
            
            .parking-grid {
                grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
            }
        }
        
        /* Loading states */
        .loading {
            animation: pulse 1.5s ease-in-out infinite;
        }
    </style>
</head>
<body>
    <div class="dashboard-container">
        <header class="dashboard-header">
            <div class="header-content">
                <h1 class="dashboard-title">Parking Monitor System</h1>
                <div class="status-indicator">
                    <div class="status-dot" id="statusDot"></div>
                    <span id="connectionStatus">Connecting...</span>
                </div>
            </div>
        </header>
        
        <main class="dashboard-content">
            <section class="metrics-section">
                <h2 class="section-title">System Metrics</h2>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-header">
                            <div class="metric-title">Vehicles Detected</div>
                        </div>
                        <div class="metric-value" id="vehiclesDetected">--</div>
                        <div class="metric-unit">total count</div>
                    </div>
                    
                    <div class="metric-card">
                        <div class="metric-header">
                            <div class="metric-title">Occupancy Rate</div>
                        </div>
                        <div class="metric-value" id="occupancyRate">--</div>
                        <div class="metric-unit">percentage</div>
                    </div>
                    
                    <div class="metric-card">
                        <div class="metric-header">
                            <div class="metric-title">Processing Rate</div>
                        </div>
                        <div class="metric-value" id="processingFps">--</div>
                        <div class="metric-unit">fps</div>
                    </div>
                    
                    <div class="metric-card">
                        <div class="metric-header">
                            <div class="metric-title">Frames Processed</div>
                        </div>
                        <div class="metric-value" id="totalFrames">--</div>
                        <div class="metric-unit">total</div>
                    </div>
                </div>
            </section>
            
            <section class="parking-section">
                <h2 class="section-title">Parking Space Status</h2>
                <div class="parking-grid" id="parkingSpaces">
                    <!-- Parking spaces populated by JavaScript -->
                </div>
            </section>
            
            <section class="metrics-section">
                <h2 class="section-title">System Health</h2>
                <div class="system-health">
                    <div class="health-card">
                        <div class="health-value" id="healthScore">--</div>
                        <div class="health-label">Health Score</div>
                    </div>
                    
                    <div class="health-card">
                        <div class="health-value" id="cpuUsage">--</div>
                        <div class="health-label">CPU Usage</div>
                    </div>
                    
                    <div class="health-card">
                        <div class="health-value" id="memoryUsage">--</div>
                        <div class="health-label">Memory Usage</div>
                    </div>
                    
                    <div class="health-card">
                        <div class="health-value" id="uptime">--</div>
                        <div class="health-label">System Uptime</div>
                    </div>
                </div>
            </section>
        </main>
        
        <footer class="dashboard-footer">
            <div class="last-update">Last updated: <span id="lastUpdate">Never</span></div>
        </footer>
    </div>

    <script>
        // WebSocket connection for real-time updates
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/dashboard/ws`;
        let ws;
        let reconnectAttempts = 0;
        const maxReconnectAttempts = 5;
        
        function updateConnectionStatus(connected) {
            const statusDot = document.getElementById('statusDot');
            const connectionStatus = document.getElementById('connectionStatus');
            
            if (connected) {
                statusDot.classList.remove('disconnected');
                connectionStatus.textContent = 'Live Monitoring';
                reconnectAttempts = 0;
            } else {
                statusDot.classList.add('disconnected');
                connectionStatus.textContent = 'Disconnected';
            }
        }
        
        function connectWebSocket() {
            if (reconnectAttempts >= maxReconnectAttempts) {
                console.log('Max reconnection attempts reached');
                return;
            }
            
            ws = new WebSocket(wsUrl);
            
            ws.onopen = function() {
                console.log('WebSocket connected');
                updateConnectionStatus(true);
            };
            
            ws.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    updateDashboard(data);
                } catch (error) {
                    console.error('Error parsing WebSocket data:', error);
                }
            };
            
            ws.onclose = function() {
                console.log('WebSocket disconnected');
                updateConnectionStatus(false);
                reconnectAttempts++;
                
                if (reconnectAttempts < maxReconnectAttempts) {
                    setTimeout(connectWebSocket, Math.pow(2, reconnectAttempts) * 1000);
                }
            };
            
            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
                updateConnectionStatus(false);
            };
        }
        
        function updateDashboard(data) {
            const stats = data.stats || {};
            const health = data.health || {};
            
            // Update metrics with proper formatting
            document.getElementById('vehiclesDetected').textContent = 
                (stats.vehicles_detected || 0).toLocaleString();
            document.getElementById('occupancyRate').textContent = 
                Math.round(stats.occupancy_rate || 0) + '%';
            document.getElementById('processingFps').textContent = 
                (stats.processing_fps || 0).toFixed(1);
            document.getElementById('totalFrames').textContent = 
                (stats.total_frames || 0).toLocaleString();
            
            // Update parking spaces
            updateParkingSpaces(stats.total_spaces || 8, stats.occupied_spaces || 0);
            
            // Update health metrics with color coding
            const healthScore = Math.round(health.score || 0);
            const healthElement = document.getElementById('healthScore');
            healthElement.textContent = healthScore + '%';
            healthElement.className = 'health-value ' + getHealthClass(healthScore);
            
            const cpuUsage = Math.round(health.cpu_percent || 0);
            const cpuElement = document.getElementById('cpuUsage');
            cpuElement.textContent = cpuUsage + '%';
            cpuElement.className = 'health-value ' + getUsageClass(cpuUsage);
            
            const memoryUsage = Math.round(health.memory_percent || 0);
            const memoryElement = document.getElementById('memoryUsage');
            memoryElement.textContent = memoryUsage + '%';
            memoryElement.className = 'health-value ' + getUsageClass(memoryUsage);
            
            document.getElementById('uptime').textContent = formatUptime(stats.uptime || 0);
            
            // Update last update time
            document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
        }
        
        function getHealthClass(score) {
            if (score >= 90) return 'excellent';
            if (score >= 75) return 'good';
            if (score >= 50) return 'warning';
            return 'critical';
        }
        
        function getUsageClass(usage) {
            if (usage >= 90) return 'critical';
            if (usage >= 75) return 'warning';
            return 'good';
        }
        
        function updateParkingSpaces(totalSpaces, occupiedSpaces) {
            const container = document.getElementById('parkingSpaces');
            container.innerHTML = '';
            
            for (let i = 1; i <= totalSpaces; i++) {
                const space = document.createElement('div');
                const isOccupied = i <= occupiedSpaces;
                
                space.className = `parking-space ${isOccupied ? 'occupied' : 'available'}`;
                space.textContent = `${i.toString().padStart(2, '0')}`;
                space.title = `Space ${i} - ${isOccupied ? 'Occupied' : 'Available'}`;
                
                container.appendChild(space);
            }
        }
        
        function formatUptime(seconds) {
            if (seconds < 60) return `${seconds}s`;
            
            const minutes = Math.floor(seconds / 60);
            if (minutes < 60) return `${minutes}m`;
            
            const hours = Math.floor(minutes / 60);
            const remainingMinutes = minutes % 60;
            if (hours < 24) return `${hours}h ${remainingMinutes}m`;
            
            const days = Math.floor(hours / 24);
            const remainingHours = hours % 24;
            return `${days}d ${remainingHours}h`;
        }
        
        // Initialize application
        function initializeDashboard() {
            // Connect WebSocket
            connectWebSocket();
            
            // Load initial data
            fetch('/dashboard/api/data')
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    updateDashboard({
                        stats: data.stats,
                        health: data.health
                    });
                })
                .catch(error => {
                    console.error('Initial data load error:', error);
                    // Show default values or error state
                    updateDashboard({ stats: {}, health: {} });
                });
        }
        
        // Start the dashboard when DOM is loaded
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initializeDashboard);
        } else {
            initializeDashboard();
        }
    </script>
</body>
</html>"""
    
    template_file = templates_dir / "dashboard.html"
    with open(template_file, "w") as f:
        f.write(dashboard_html)