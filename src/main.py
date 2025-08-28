#!/usr/bin/env python3
"""
Simplified Parking Monitor Service
Focuses purely on AI vision and parking detection
"""

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse

from .detector import ParkingDetector
from .dashboard.dashboard import create_dashboard_app


class ParkingMonitorService:
    """Main service for parking detection - AI vision only"""
    
    def __init__(self):
        self.detector = ParkingDetector()
        self.running = False
        self.start_time = datetime.now()
        
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
        
        # Start detector in background task
        asyncio.create_task(self.detector.process_video_stream())
        
    async def stop_detection(self):
        """Stop parking detection processing"""
        self.running = False
        await self.detector.stop()
        self.logger.info("Parking detection stopped")

    async def get_detection_stats(self):
        """Get current detection statistics"""
        return await self.detector.get_stats()

    def get_uptime(self):
        """Get service uptime in seconds"""
        return (datetime.now() - self.start_time).total_seconds()


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