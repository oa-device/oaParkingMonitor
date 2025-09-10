#!/usr/bin/env python3
"""
Refactored oaParkingMonitor - Clean Modular Architecture
Professional parking detection service with proper separation of concerns
"""

import asyncio
import logging
import os
import platform
import time
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, HTMLResponse
from fastapi.templating import Jinja2Templates

# Import modular components
from .api.models import (
    HealthResponse, CameraSettingsRequest, CameraSettingsResponse,
    CameraOperationResponse, CameraPresetsResponse, DetectionResponse,
    ZonesResponse, StatusResponse, ConfigResponse, ErrorResponse
)
from .services.parking_monitor import ParkingMonitorService
from .services.camera_controller import CameraController


# Global service instances
parking_service = ParkingMonitorService()
camera_controller = CameraController(parking_service.config, parking_service.detector)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management with proper startup/shutdown"""
    # Startup
    await parking_service.start_detection()
    yield
    # Shutdown  
    await parking_service.stop_detection()


# Create FastAPI application with enhanced documentation
app = FastAPI(
    title="oaParkingMonitor - Modular Architecture",
    description="""
    **Professional Parking Detection Service with Clean Architecture**
    
    ✨ **New Modular Design:**
    - 🏗️ **Clean Architecture** - Proper separation of concerns with modular components
    - 🔧 **Service Layer** - Dedicated business logic orchestration
    - 🎛️ **Camera Controller** - Specialized camera settings management
    - 📊 **API Models** - Centralized request/response validation
    - 🔒 **Enhanced Configuration** - Pydantic-based with automatic validation
    
    **Key Features:**
    - 📷 **Real-time parking detection** with YOLOv11m AI model
    - 🎯 **Camera presets** optimized for different lighting conditions
    - 📡 **Professional REST API** with comprehensive documentation
    - 🔧 **Manual camera controls** for exposure, quality, and enhancement
    - 📊 **Live dashboard** with real-time updates
    
    **Architecture Benefits:**
    - **Maintainable**: Easy to locate and fix issues
    - **Testable**: Services can be tested independently
    - **Extensible**: Add features without touching core logic
    - **Professional**: Industry-standard patterns and practices
    """,
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Setup templates
templates = Jinja2Templates(directory="templates")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Core API Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Enhanced health check with service status"""
    return HealthResponse(
        status="healthy" if parking_service.running else "stopped",
        service="parking-monitor-modular",
        version="2.0.0",
        uptime=parking_service.get_uptime(),
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S")
    )


@app.get("/api/detection", response_model=DetectionResponse)
async def get_detection():
    """Get current parking detection results with enhanced statistics"""
    try:
        stats = await parking_service.get_detection_stats()
        
        return DetectionResponse(
            vehicles_detected=stats.get("vehicles_detected", 0),
            total_spaces=stats.get("total_zones", parking_service.config.get_total_zones()),
            occupied_spaces=stats.get("occupied_zones", 0),
            occupancy_rate=stats.get("occupancy_rate", 0.0),
            last_detection=stats.get("last_detection"),
            video_source=stats.get("video_source", "staging_video"),
            processing_fps=stats.get("processing_fps", 0.2),
            last_update_epoch=stats.get("last_update_epoch", 0.0),
            server_time_epoch=stats.get("server_time_epoch", time.time()),
            snapshot_interval=stats.get("snapshot_interval", 5),
            easy_zones_count=stats.get("easy_zones_count", 0),
            hard_zones_count=stats.get("hard_zones_count", 0)
        )
        
    except Exception as e:
        logging.error(f"Detection stats error: {e}")
        return JSONResponse(
            content={"error": "Failed to get detection stats", "message": str(e)},
            status_code=500
        )


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


@app.get("/api/raw-snapshot")
async def get_raw_snapshot():
    """Get current raw frame without detection overlays"""
    image_bytes = parking_service.get_raw_frame_image()
    if image_bytes is None:
        return JSONResponse(
            {"error": "No raw frame available yet"}, 
            status_code=404
        )
    
    return Response(
        content=image_bytes, 
        media_type="image/jpeg",
        headers={
            "Content-Disposition": "inline; filename=parking_raw_snapshot.jpg",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@app.get("/api/zones", response_model=ZonesResponse)
async def get_zones():
    """Get parking zone definitions and current status"""
    try:
        zones_data = await parking_service.get_zones_data()
        
        return ZonesResponse(
            zones=zones_data,
            total_zones=len(zones_data),
            server_time_epoch=time.time()
        )
        
    except Exception as e:
        logging.error(f"Zones data error: {e}")
        return JSONResponse(
            content={"error": "Failed to get zones data", "message": str(e)},
            status_code=500
        )


@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    """Get comprehensive system status and timing information"""
    try:
        status_info = parking_service.get_status_info()
        
        return StatusResponse(**status_info)
        
    except Exception as e:
        logging.error(f"Status info error: {e}")
        return JSONResponse(
            content={"error": "Failed to get status info", "message": str(e)},
            status_code=500
        )


# Camera Control API Endpoints (now using dedicated controller)
@app.get("/api/camera/settings", response_model=CameraSettingsResponse)
async def get_camera_settings():
    """Get current camera settings using modular controller"""
    try:
        camera_settings = camera_controller.get_current_settings()
        device_info = parking_service.get_device_info()
        
        return CameraSettingsResponse(
            camera_settings=camera_settings,
            is_camera_device=device_info["is_camera_device"],
            device_initialized=device_info["device_initialized"],
            server_time_epoch=time.time()
        )
        
    except Exception as e:
        logging.error(f"Camera settings error: {e}")
        return JSONResponse(
            content={"error": "Failed to get camera settings", "message": str(e)},
            status_code=500
        )


@app.post("/api/camera/settings", response_model=CameraOperationResponse)
async def update_camera_settings(settings: CameraSettingsRequest):
    """Update camera settings using dedicated controller with validation"""
    return await camera_controller.update_settings(settings)


@app.post("/api/camera/reset", response_model=CameraOperationResponse)
async def reset_camera_settings():
    """Reset camera settings to optimal defaults"""
    return await camera_controller.reset_to_defaults()


@app.get("/api/camera/presets", response_model=CameraPresetsResponse)
async def get_camera_presets():
    """Get available camera presets optimized for different conditions"""
    try:
        presets = camera_controller.get_available_presets()
        
        return CameraPresetsResponse(
            presets=presets,
            current_preset="custom",  # Could be enhanced to track current preset
            server_time_epoch=time.time()
        )
        
    except Exception as e:
        logging.error(f"Camera presets error: {e}")
        return JSONResponse(
            content={"error": "Failed to get camera presets", "message": str(e)},
            status_code=500
        )


@app.post("/api/camera/presets/{preset_name}", response_model=CameraOperationResponse)
async def apply_camera_preset(preset_name: str):
    """Apply a predefined camera preset"""
    return await camera_controller.apply_preset(preset_name)


@app.get("/api/config", response_model=ConfigResponse)
async def get_full_configuration():
    """Get complete system configuration"""
    try:
        config_data = parking_service.get_config_data()
        
        return ConfigResponse(
            configuration=config_data,
            metadata={
                "config_loaded_from": getattr(parking_service.config, 'config_loaded_from', None),
                "total_zones": parking_service.config.get_total_zones(),
                "modular_architecture": True,
                "version": "2.0.0"
            }
        )
        
    except Exception as e:
        logging.error(f"Configuration error: {e}")
        return JSONResponse(
            content={"error": "Failed to get configuration", "message": str(e)},
            status_code=500
        )


# Dashboard and Root Endpoints
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Parking monitor dashboard with camera controls"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with service information"""
    return HTMLResponse(f"""
    <html>
    <head><title>oaParkingMonitor - Modular Architecture</title></head>
    <body>
        <h1>🚀 oaParkingMonitor v2.0 - Modular Architecture</h1>
        <p><strong>Architecture Improvements:</strong></p>
        <ul>
            <li>🏗️ Clean Modular Design - Separated concerns and responsibilities</li>
            <li>🔧 Service Layer - Dedicated business logic orchestration</li>
            <li>🎛️ Camera Controller - Specialized settings management</li>
            <li>📊 API Models - Centralized validation and documentation</li>
            <li>🔒 Enhanced Configuration - Pydantic-based with automatic validation</li>
        </ul>
        <p><strong>Navigation:</strong></p>
        <ul>
            <li><a href="/dashboard">🎛️ Dashboard</a> - Camera controls and live view</li>
            <li><a href="/docs">📚 API Documentation</a> - Complete API reference</li>
            <li><a href="/health">❤️ Health Check</a> - Service status</li>
            <li><a href="/api/detection">📊 Detection Stats</a> - Current parking data</li>
        </ul>
        <p><strong>Service Status:</strong> {"🟢 Running" if parking_service.running else "🔴 Stopped"}</p>
        <p><strong>Uptime:</strong> {parking_service.get_uptime():.1f} seconds</p>
    </body>
    </html>
    """)


def validate_startup_environment():
    """Validate runtime environment and dependencies"""
    import sys
    
    # Check Python version
    if sys.version_info < (3.8):
        logging.error(f"Python 3.8+ required, got {sys.version_info}")
        return False
        
    # Check required files
    required_files = ["pyproject.toml", "src/__init__.py", "config", "templates"]
    for file_path in required_files:
        if not Path(file_path).exists():
            logging.error(f"Required file/directory missing: {file_path}")
            logging.info(f"Current working directory: {os.getcwd()}")
            return False
    
    # Enhanced environment info
    logging.info("🚀 oaParkingMonitor v2.0 - Modular Architecture")
    logging.info(f"✅ Python: {sys.version}")
    logging.info(f"🖥️  Platform: {platform.system()} {platform.machine()}")
    logging.info(f"📁 Working directory: {os.getcwd()}")
    logging.info(f"🌐 Service available at: http://0.0.0.0:9091")
    logging.info(f"📚 API docs at: http://0.0.0.0:9091/docs")
    logging.info("🏗️ Modular architecture: Service Layer + Camera Controller + API Models")
    
    return True


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Validate environment
    if not validate_startup_environment():
        logging.error("❌ Startup validation failed - exiting")
        exit(1)
    
    # Get configuration from service
    api_port = parking_service.config.api.port
    api_host = parking_service.config.api.host
    
    try:
        logging.info(f"🚀 Starting modular service on {api_host}:{api_port}")
        uvicorn.run(
            "src.main:app",
            host=api_host,
            port=api_port,
            reload=False,
            log_level="info"
        )
    except Exception as e:
        logging.error(f"❌ Failed to start server: {e}")
        exit(1)