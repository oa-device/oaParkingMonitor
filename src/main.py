#!/usr/bin/env python3
"""
Simplified Parking Monitor Service
Focuses purely on AI vision and parking detection
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse

from .detector import ParkingDetector
from .dashboard.dashboard import create_dashboard_app
from .integrations import YHUIntegration
from .config import ConfigManager


class ParkingMonitorService:
    """Main service for parking detection - AI vision only"""
    
    def __init__(self):
        # Load configuration
        self.config_manager = ConfigManager()
        self.config = self.config_manager.config
        
        self.detector = ParkingDetector()
        self.running = False
        self.start_time = datetime.now()
        
        # Initialize YHU integration
        self.yhu_integration = None
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(__name__)

    async def start_detection(self):
        """Start parking detection processing"""
        self.running = True
        self.logger.info("Starting parking detection...")
        
        # Initialize YHU integration if enabled
        if self.config.yhu_integration.enabled:
            self.yhu_integration = YHUIntegration(self.config.yhu_integration)
            await self.yhu_integration.__aenter__()
            await self.yhu_integration.start()
            self.logger.info("YHU integration initialized")
        
        # Start detector in background task
        asyncio.create_task(self.detector.process_video_stream())
        
        # Start YHU sync loop if enabled
        if self.yhu_integration:
            asyncio.create_task(self._yhu_sync_loop())
        
    async def stop_detection(self):
        """Stop parking detection processing"""
        self.running = False
        await self.detector.stop()
        
        # Stop YHU integration
        if self.yhu_integration:
            await self.yhu_integration.stop()
            await self.yhu_integration.__aexit__(None, None, None)
            self.yhu_integration = None
            self.logger.info("YHU integration stopped")
        
        self.logger.info("Parking detection stopped")

    async def get_detection_stats(self):
        """Get current detection statistics"""
        return await self.detector.get_stats()

    def get_uptime(self):
        """Get service uptime in seconds"""
        return (datetime.now() - self.start_time).total_seconds()
    
    async def _yhu_sync_loop(self):
        """Background task for YHU synchronization"""
        while self.running and self.yhu_integration:
            try:
                # Get current detection stats
                stats = await self.get_detection_stats()
                
                # Send to YHU integration
                await self.yhu_integration.process_detection_update(stats)
                
                # Wait for next sync interval
                await asyncio.sleep(self.config.yhu_integration.sync_interval)
                
            except Exception as e:
                self.logger.error(f"Error in YHU sync loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def get_yhu_status(self):
        """Get YHU integration status"""
        if not self.yhu_integration:
            return {"enabled": False, "status": "disabled"}
        return await self.yhu_integration.get_integration_status()

    async def get_health_status(self):
        """Get basic health status for dashboard compatibility"""
        return {
            "running": self.running,
            "uptime": self.get_uptime(),
            "health_score": 100 if self.running else 0,
            "system": {
                "cpu_percent": 0,  # Minimal implementation for dashboard
                "memory_percent": 0
            }
        }


# Global service instance
parking_service = ParkingMonitorService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    await parking_service.start_detection()
    yield
    # Shutdown  
    await parking_service.stop_detection()


# Create FastAPI application
app = FastAPI(
    title="Parking Monitor API",
    description="Standalone AI vision service for parking detection",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple health endpoint (minimal, not duplicating oaDeviceAPI functionality)
@app.get("/health")
async def health_check():
    """Simple health check - service running status only"""
    return JSONResponse({
        "status": "healthy" if parking_service.running else "stopped",
        "service": "parking-monitor", 
        "version": "2.0.0",
        "uptime": parking_service.get_uptime(),
        "timestamp": datetime.now().isoformat()
    })

# Core API endpoints for parking detection
@app.get("/api/stats")
async def get_stats():
    """Get parking detection statistics"""
    stats = await parking_service.get_detection_stats()
    return JSONResponse(stats)

@app.get("/api/detection") 
async def get_detection():
    """Get current parking detection results"""
    stats = await parking_service.get_detection_stats()
    return JSONResponse({
        "vehicles_detected": stats.get("vehicles_detected", 0),
        "total_spaces": stats.get("total_spaces", 4),
        "occupied_spaces": stats.get("occupied_spaces", 0), 
        "occupancy_rate": stats.get("occupancy_rate", 0.0),
        "last_detection": stats.get("last_detection"),
        "video_source": stats.get("video_source", ""),
        "processing_fps": stats.get("processing_fps", 0.0)
    })

@app.get("/api/spaces")
async def get_parking_spaces():
    """Get parking space definitions and status"""
    return await parking_service.detector.get_parking_spaces()

# YHU Integration endpoints
@app.get("/api/yhu/status")
async def get_yhu_status():
    """Get YHU integration status"""
    return await parking_service.get_yhu_status()

@app.get("/api/yhu/config")
async def get_yhu_config():
    """Get YHU integration configuration"""
    return JSONResponse({
        "enabled": parking_service.config.yhu_integration.enabled,
        "api_url": parking_service.config.yhu_integration.api_url,
        "lot_id": parking_service.config.yhu_integration.lot_id,
        "sync_interval": parking_service.config.yhu_integration.sync_interval
    })

@app.post("/api/yhu/test")
async def test_yhu_connection():
    """Test YHU Dashboard connection"""
    if not parking_service.yhu_integration:
        return JSONResponse(
            {"success": False, "error": "YHU integration not enabled"}, 
            status_code=400
        )
    
    try:
        success = await parking_service.yhu_integration._test_connection()
        return JSONResponse({"success": success})
    except Exception as e:
        return JSONResponse(
            {"success": False, "error": str(e)}, 
            status_code=500
        )

# Mount dashboard (standalone monitoring UI)
dashboard_app = create_dashboard_app(parking_service)
app.mount("/dashboard", dashboard_app)

# Root endpoint redirects to dashboard
@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint redirects to monitoring dashboard"""
    return HTMLResponse("""
    <html>
    <head><title>Parking Monitor</title></head>
    <body>
        <script>window.location.href = '/dashboard';</script>
        <p>Redirecting to <a href="/dashboard">Parking Monitor Dashboard</a></p>
    </body>
    </html>
    """)


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0", 
        port=9091,
        reload=False,
        log_level="info"
    )