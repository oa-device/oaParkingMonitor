#!/usr/bin/env python3
"""
MVP Parking Monitor Service
Simplified snapshot-based parking detection with epoch timestamps
"""

import asyncio
import logging
import os
import platform
import time
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .detector import MVPParkingDetector
from .config import MVPConfigManager


# Pydantic response models for MVP API
class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    service: str
    version: str
    uptime: float
    timestamp: str


class MVPParkingMonitorService:
    """Simplified MVP service for snapshot-based parking detection"""
    
    def __init__(self):
        # Load MVP configuration
        self.config_manager = MVPConfigManager()
        self.config = self.config_manager.config
        
        self.detector = MVPParkingDetector()
        self.running = False
        self.start_time = datetime.now()
        
        # Setup logging
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(f"MVP Service initialized with snapshot interval: {self.config.snapshot_interval}s")
    
    def _setup_logging(self):
        """Setup simplified logging"""
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler()]
        )
    
    async def start_detection(self):
        """Start snapshot processing"""
        try:
            self.running = True
            self.logger.info("Starting snapshot-based parking detection...")
            
            # Start detector snapshot loop in background
            detection_task = asyncio.create_task(self.detector.start_snapshot_loop())
            
            self.logger.info("MVP Parking detection service started successfully")
            
        except Exception as e:
            self.logger.error(f"Service startup failed: {e}")
            self.running = False
            raise
    
    async def stop_detection(self):
        """Stop detection processing"""
        try:
            self.logger.info("Stopping MVP parking detection service...")
            self.running = False
            
            await self.detector.stop()
            
            self.logger.info("MVP Parking detection service stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Service shutdown error: {e}")
            raise

    async def get_detection_stats(self):
        """Get current detection statistics with epoch timestamps"""
        stats = await self.detector.get_stats()
        
        # Add epoch timestamps for MVP
        stats["last_update_epoch"] = self.config.last_snapshot_epoch
        stats["server_time_epoch"] = time.time()
        
        return stats

    def get_uptime(self):
        """Get service uptime in seconds"""
        return (datetime.now() - self.start_time).total_seconds()
    
    def get_snapshot_image(self) -> Optional[bytes]:
        """Get last processed snapshot as JPEG bytes"""
        return self.detector.get_last_snapshot_image()
    
    async def get_zones_data(self):
        """Get parking zones data"""
        return self.config.get_zones_data()
    
    def get_config_data(self):
        """Get configuration data"""
        return self.config.to_dict()


# Global MVP service instance
parking_service = MVPParkingMonitorService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    await parking_service.start_detection()
    yield
    # Shutdown  
    await parking_service.stop_detection()


# Create FastAPI application for MVP
app = FastAPI(
    title="oaParkingMonitor MVP API",
    description="Simplified snapshot-based parking detection with 5-second intervals and epoch timestamps",
    version="1.0.0",
    lifespan=lifespan,
)

# Setup templates for dashboard
templates = Jinja2Templates(directory="templates")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# MVP API Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Simple health check for MVP"""
    return JSONResponse({
        "status": "healthy" if parking_service.running else "stopped",
        "service": "parking-monitor-mvp", 
        "version": "1.0.0",
        "uptime": parking_service.get_uptime(),
        "timestamp": datetime.now().isoformat()
    })


@app.get("/api/detection")
async def get_detection():
    """Get current parking detection results with epoch timestamps"""
    stats = await parking_service.get_detection_stats()
    return JSONResponse({
        "vehicles_detected": stats.get("vehicles_detected", 0),
        "total_spaces": stats.get("total_zones", 11),
        "occupied_spaces": stats.get("occupied_zones", 0), 
        "occupancy_rate": stats.get("occupancy_rate", 0.0),
        "last_detection": stats.get("last_detection"),
        "video_source": stats.get("video_source", "staging_video"),
        "processing_fps": stats.get("processing_fps", 0.2),
        "last_update_epoch": stats.get("last_update_epoch", 0.0),
        "server_time_epoch": stats.get("server_time_epoch", time.time()),
        "snapshot_interval": stats.get("snapshot_interval", 5)
    })


@app.get("/api/snapshot")
async def get_snapshot():
    """Get last processed snapshot image with detection overlays"""
    image_bytes = parking_service.get_snapshot_image()
    if image_bytes is None:
        return JSONResponse(
            {"error": "No snapshot processed yet"}, 
            status_code=404
        )
    
    return Response(
        content=image_bytes, 
        media_type="image/jpeg",
        headers={
            "Content-Disposition": "inline; filename=parking_snapshot.jpg",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@app.get("/api/zones")
async def get_zones():
    """Get parking zone definitions and status"""
    zones_data = await parking_service.get_zones_data()
    
    return JSONResponse({
        "zones": zones_data,
        "total_zones": len(zones_data),
        "server_time_epoch": time.time()
    })


@app.get("/api/status")
async def get_status():
    """Get processing status and timing information"""
    config_data = parking_service.get_config_data()
    current_time = time.time()
    
    # Calculate when next snapshot will happen
    time_since_last = current_time - config_data.get("last_snapshot_epoch", 0)
    next_snapshot_in = max(0, config_data.get("snapshot_interval", 5) - time_since_last)
    
    return JSONResponse({
        "processing_enabled": config_data.get("processing_enabled", True),
        "snapshot_interval": config_data.get("snapshot_interval", 5),
        "last_snapshot_epoch": config_data.get("last_snapshot_epoch", 0),
        "server_time_epoch": current_time,
        "uptime_seconds": parking_service.get_uptime(),
        "next_snapshot_in": round(next_snapshot_in, 1),
        "model_loaded": parking_service.detector.stats.get("model_loaded", False),
        "device": parking_service.detector.device,
        "total_zones": config_data.get("total_zones", 11)
    })


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Simple dashboard for viewing parking snapshots and zone status"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint redirects to dashboard"""
    return HTMLResponse("""
    <html>
    <head><title>Parking Monitor MVP</title></head>
    <body>
        <script>window.location.href = '/dashboard';</script>
        <p>Redirecting to <a href="/dashboard">Parking Monitor Dashboard</a></p>
    </body>
    </html>
    """)


def validate_startup_environment():
    """Validate runtime environment and dependencies before starting service."""
    import sys
    from pathlib import Path
    
    # Check Python version
    if sys.version_info < (3, 12):
        logging.error(f"Python 3.12+ required, got {sys.version_info}")
        return False
        
    # Check working directory has required files
    required_files = ["pyproject.toml", "src/__init__.py", "config", "templates"]
    for file_path in required_files:
        if not Path(file_path).exists():
            logging.error(f"Required file/directory missing: {file_path}")
            logging.info(f"Current working directory: {os.getcwd()}")
            logging.info(f"Directory contents: {list(Path('.').iterdir())}")
            return False
    
    # Check for Apple Silicon for Metal/MPS optimizations
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        logging.info("Apple Silicon detected - Metal Performance Shaders available")
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    
    # Log environment info
    logging.info("oaParkingMonitor MVP starting")
    logging.info(f"Python: {sys.version}")
    logging.info(f"Platform: {platform.system()} {platform.machine()}")
    logging.info(f"Working directory: {os.getcwd()}")
    logging.info("Service will be available at http://0.0.0.0:9091")
    
    return True


if __name__ == "__main__":
    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Validate environment before starting
    if not validate_startup_environment():
        logging.error("Startup validation failed - exiting")
        exit(1)
    
    # Start the service
    try:
        uvicorn.run(
            "src.main:app",
            host="0.0.0.0", 
            port=9091,
            reload=False,
            log_level="info"
        )
    except Exception as e:
        logging.error(f"Failed to start server: {e}")
        exit(1)