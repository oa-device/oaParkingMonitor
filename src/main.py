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
from fastapi import FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, HTMLResponse
from fastapi.templating import Jinja2Templates

# Import modular components
from .api.models import (
    HealthResponse, CameraSettingsRequest, CameraSettingsResponse,
    CameraOperationResponse, CameraPresetsResponse, DetectionResponse,
    ZonesResponse, StatusResponse, ConfigResponse, ErrorResponse, HistoryResponse
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
    title="oaParkingMonitor API",
    description="""
# Parking Detection API

Real-time parking space monitoring with YOLOv11m AI model.

## Quick Start
- **Health Check**: `GET /health`
- **Detection Data**: `GET /api/detection` 
- **Live Dashboard**: `GET /dashboard`
- **Camera Settings**: `GET/POST /api/camera/settings`

## Key Features
- Real-time vehicle detection and parking zone monitoring
- Camera settings management with presets for different lighting
- Live snapshots with detection overlays
- Comprehensive status and configuration endpoints
    """,
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    tags_metadata=[
        {
            "name": "Health",
            "description": "Service health monitoring and system status endpoints."
        },
        {
            "name": "Detection", 
            "description": "Real-time parking detection and zone monitoring endpoints."
        },
        {
            "name": "Camera",
            "description": "Camera settings management, presets, and hardware control."
        },
        {
            "name": "Configuration",
            "description": "System configuration and operational parameters."
        },
        {
            "name": "Dashboard",
            "description": "Web interface and user-facing pages."
        }
    ]
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
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Service health check with uptime and status information
    
    Returns comprehensive health information including service status,
    version, uptime, and current timestamp for monitoring purposes.
    """
    current_epoch = time.time()
    return HealthResponse(
        status="healthy" if parking_service.running else "stopped",
        service="parking-monitor-modular",
        version="2.0.0",
        uptime=parking_service.get_uptime(),
        data_epoch=current_epoch,
        request_epoch=current_epoch
    )


@app.get("/api/detection", response_model=DetectionResponse, tags=["Detection"])
async def get_detection():
    """Get real-time parking detection results
    
    Returns current parking space occupancy data including vehicle counts,
    zone status, occupancy rates, and detection confidence scores.
    """
    try:
        stats = await parking_service.get_detection_stats()
        
        return DetectionResponse(
            vehicles_detected=stats.get("vehicles_detected", 0),
            total_spaces=stats.get("total_zones", parking_service.config.get_total_zones()),
            occupied_spaces=stats.get("occupied_zones", 0),
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


@app.get("/api/snapshot", tags=["Detection"])
async def get_snapshot():
    """Get processed snapshot with detection overlays
    
    Returns the latest processed frame with vehicle detection bounding boxes
    and zone overlays for visual verification of detection accuracy.
    """
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


@app.get("/api/raw-snapshot", tags=["Detection"])
async def get_raw_snapshot():
    """Get raw camera frame without processing
    
    Returns the unprocessed camera frame for troubleshooting camera
    settings, focus, and exposure without AI detection overlays.
    """
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


@app.get("/api/zones", response_model=ZonesResponse, tags=["Detection"])
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


@app.get("/api/status", response_model=StatusResponse, tags=["Health"])
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
@app.get("/api/camera/settings", response_model=CameraSettingsResponse, tags=["Camera"])
async def get_camera_settings():
    """Get current camera configuration
    
    Returns comprehensive camera settings including resolution, exposure,
    gain, image quality parameters, and device initialization status.
    """
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


@app.post("/api/camera/settings", response_model=CameraOperationResponse, tags=["Camera"])
async def update_camera_settings(settings: CameraSettingsRequest):
    """Update camera settings with validation
    
    Applies new camera settings with automatic validation and error handling.
    Settings are applied immediately and persist across service restarts.
    """
    return await camera_controller.update_settings(settings)


@app.post("/api/camera/reset", response_model=CameraOperationResponse, tags=["Camera"])
async def reset_camera_settings():
    """Reset camera settings to optimal defaults"""
    return await camera_controller.reset_to_defaults()


@app.get("/api/camera/presets", response_model=CameraPresetsResponse, tags=["Camera"])
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


@app.post("/api/camera/presets/{preset_name}", response_model=CameraOperationResponse, tags=["Camera"])
async def apply_camera_preset(preset_name: str):
    """Apply a predefined camera preset"""
    return await camera_controller.apply_preset(preset_name)


@app.get("/api/config", response_model=ConfigResponse, tags=["Configuration"])
async def get_full_configuration():
    """Get complete system configuration"""
    try:
        config_data = parking_service.get_config_data()
        
        current_epoch = time.time()
        return ConfigResponse(
            configuration=config_data,
            metadata={
                "config_loaded_from": getattr(parking_service.config, 'config_loaded_from', None),
                "total_zones": parking_service.config.get_total_zones(),
                "modular_architecture": True,
                "version": "2.0.0"
            },
            data_epoch=current_epoch,
            request_epoch=current_epoch
        )
        
    except Exception as e:
        logging.error(f"Configuration error: {e}")
        return JSONResponse(
            content={"error": "Failed to get configuration", "message": str(e)},
            status_code=500
        )


# History and Analytics API Endpoints
@app.get("/api/history", response_model=HistoryResponse, tags=["Analytics"])
async def get_snapshot_history(
    from_epoch: int = Query(..., description="Start epoch timestamp"),
    to_epoch: int = Query(..., description="End epoch timestamp")
):
    """Get historical snapshot data within epoch range for airport demo
    
    Returns snapshots from the specified epoch range including JSON data
    and image references for the YHU dashboard integration.
    """
    try:
        # Import at function level to avoid circular imports
        from .utils.paths import get_data_paths
        
        data_paths = get_data_paths()
        current_epoch = time.time()
        
        # Get snapshots in the requested range
        snapshots = data_paths.get_snapshots_in_range(from_epoch, to_epoch)
        
        # Load JSON data for each snapshot
        snapshot_data = []
        for snapshot_info in snapshots:
            try:
                from .utils.paths import load_snapshot_json
                json_data = load_snapshot_json(snapshot_info["epoch"])
                if json_data:
                    # Add file existence info
                    json_data["has_image"] = snapshot_info["has_image"]
                    json_data["image_path"] = f"/api/snapshot/{snapshot_info['epoch']}"
                    snapshot_data.append(json_data)
            except Exception as e:
                logging.warning(f"Failed to load snapshot {snapshot_info['epoch']}: {e}")
        
        return HistoryResponse(
            snapshots=snapshot_data,
            count=len(snapshot_data),
            from_epoch=from_epoch,
            to_epoch=to_epoch,
            data_epoch=current_epoch,
            request_epoch=current_epoch
        )
        
    except Exception as e:
        logging.error(f"History retrieval error: {e}")
        return JSONResponse(
            content={"error": "Failed to get history", "message": str(e)},
            status_code=500
        )

@app.get("/api/snapshot/{epoch}", tags=["Analytics"])
async def get_historical_snapshot_image(epoch: int):
    """Get historical snapshot image by epoch timestamp for airport demo
    
    Returns the snapshot image file for the specified epoch timestamp.
    Used by YHU dashboard to display historical detection images.
    """
    try:
        from .utils.paths import load_snapshot_image
        
        image_bytes = load_snapshot_image(epoch)
        if image_bytes is None:
            return JSONResponse(
                content={"error": f"Snapshot image not found for epoch {epoch}"},
                status_code=404
            )
        
        return Response(
            content=image_bytes,
            media_type="image/jpeg",
            headers={
                "Content-Disposition": f"inline; filename=snapshot_{epoch}.jpg",
                "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
                "Last-Modified": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(epoch))
            }
        )
        
    except Exception as e:
        logging.error(f"Historical snapshot error for epoch {epoch}: {e}")
        return JSONResponse(
            content={"error": "Failed to get historical snapshot", "message": str(e)},
            status_code=500
        )


@app.get("/api/zones/{zone_id}/history", tags=["Analytics"])
async def get_zone_history(
    zone_id: int,
    hours: int = Query(24, ge=1, le=168, description="Hours of history to retrieve")
):
    """Get historical data for a specific parking zone
    
    Returns detailed occupancy history for a single zone including
    state changes, confidence trends, and detection patterns.
    """
    try:
        history = await parking_service.get_zone_history(zone_id, hours)
        return JSONResponse(content={
            "zone_id": zone_id,
            "hours": hours,
            "history": history,
            "data_points": len(history)
        })
        
    except Exception as e:
        logging.error(f"Zone history error: {e}")
        return JSONResponse(
            content={"error": f"Failed to get history for zone {zone_id}", "message": str(e)},
            status_code=500
        )


@app.get("/api/analytics", tags=["Analytics"])
async def get_analytics(
    hours: int = Query(24, ge=1, le=168, description="Hours of data to analyze")
):
    """Get comprehensive parking analytics
    
    Returns analytics including occupancy trends, zone performance,
    system health metrics, and usage patterns.
    """
    try:
        analytics = await parking_service.get_occupancy_analytics(hours)
        return JSONResponse(content=analytics)
        
    except Exception as e:
        logging.error(f"Analytics error: {e}")
        return JSONResponse(
            content={"error": "Failed to generate analytics", "message": str(e)},
            status_code=500
        )


@app.get("/api/export", tags=["Analytics"])
async def export_data(
    hours: int = Query(24, ge=1, le=168, description="Hours of data to export"),
    format: str = Query("json", enum=["json", "csv"], description="Export format")
):
    """Export historical detection data
    
    Downloads historical parking data in specified format for
    external analysis and reporting.
    """
    try:
        data = await parking_service.export_data(hours, format)
        
        if format == "csv":
            return Response(
                content=data,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=parking_data_{hours}h.csv"
                }
            )
        else:
            return Response(
                content=data,
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=parking_data_{hours}h.json"
                }
            )
            
    except Exception as e:
        logging.error(f"Export error: {e}")
        return JSONResponse(
            content={"error": "Failed to export data", "message": str(e)},
            status_code=500
        )


@app.get("/api/stats", tags=["Detection"])
async def get_detection_stats():
    """Get current detection statistics
    
    Returns real-time detection performance metrics including
    temporal smoothing stats, multi-scale detection performance,
    and tracking statistics.
    """
    try:
        stats = await parking_service.get_detection_stats()
        
        # Add temporal and tracking stats if available
        if hasattr(parking_service.detector, 'temporal_smoother'):
            stats["temporal_smoothing"] = parking_service.detector.temporal_smoother.get_stats()
        
        if hasattr(parking_service.detector, 'vehicle_tracker'):
            stats["vehicle_tracking"] = parking_service.detector.vehicle_tracker.get_stats()
        
        return JSONResponse(content=stats)
        
    except Exception as e:
        logging.error(f"Stats error: {e}")
        return JSONResponse(
            content={"error": "Failed to get stats", "message": str(e)},
            status_code=500
        )


# Dashboard and Root Endpoints
@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard"])
async def dashboard(request: Request):
    """Interactive parking monitor dashboard
    
    Web interface providing real-time parking status, camera controls,
    settings management, and live detection visualization.
    """
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
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
    if sys.version_info < (3, 8):
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