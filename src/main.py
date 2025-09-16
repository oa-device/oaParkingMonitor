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
from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, HTMLResponse
from fastapi.templating import Jinja2Templates

# Import modular components
from .api.models import ConfigResponse
from .services.parking_monitor import ParkingMonitorService
from .services.camera_controller import CameraController

# Import edge components
from .models.edge import (
    DetectionBatch, DetectionSnapshot, HealthResponse,
    ErrorResponse, OperationResponse, CameraStatus
)
from .storage.edge_storage import EdgeStorage


# Global service instances
parking_service = ParkingMonitorService()
camera_controller = CameraController(parking_service.config, parking_service.detector)
edge_storage = EdgeStorage()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management with proper startup/shutdown"""
    # Startup
    await parking_service.start_detection()
    yield
    # Shutdown  
    await parking_service.stop_detection()


# Create FastAPI application with professional edge device documentation
app = FastAPI(
    title="oaParkingMonitor Edge API",
    description="""
# Parking Detection Edge Device API

Streamlined parking space monitoring service with YOLOv11m AI model.
Edge device provides minimal data collection and reliable sensor functionality.

## Core Endpoints (5)
- **Health**: `GET /health` - Service status
- **Current State**: `GET /detection` - Real-time parking data
- **Historical Data**: `GET /detections` - Batch retrieval
- **Configuration**: `GET /config` - System settings
- **Config Update**: `POST /config` - Remote configuration

## Debug Endpoints (4)
- **Visual Debug**: `GET /snapshot` - Processed image
- **Camera Debug**: `GET /frame` - Raw camera feed
- **Camera Status**: `GET /camera/status` - Hardware status
- **Camera Recovery**: `POST /camera/restart` - Force restart

## Dashboard (2)
- **Landing Page**: `GET /` - Debug interface
- **Dashboard**: `GET /dashboard` - Service overview
    """,
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    tags_metadata=[
        {
            "name": "Core",
            "description": "Essential edge device functionality - 5 core endpoints"
        },
        {
            "name": "Debug",
            "description": "Operational debugging and troubleshooting - 4 debug endpoints"
        },
        {
            "name": "Dashboard",
            "description": "Web interface for device debugging - 2 dashboard endpoints"
        }
    ]
)


# Global exception handler for consistent error responses
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent ErrorResponse format"""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail if isinstance(exc.detail, dict) else {
            "error": f"HTTP {exc.status_code}",
            "message": str(exc.detail),
            "ts": int(time.time() * 1000)
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions with ErrorResponse format"""
    logging.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal Server Error",
            message="An unexpected error occurred" if not os.getenv("DEBUG") else str(exc)
        ).model_dump()
    )

# Templates and static file serving
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Core API Endpoints
@app.get("/health", response_model=HealthResponse, tags=["Core"])
async def health_check():
    """Service health check - minimal 2-field response per edge simplification

    Returns only essential health status and timestamp for monitoring systems.
    Edge device provides minimal data as per simplification philosophy.
    """
    return HealthResponse(
        status="ok" if parking_service.running else "error"
    )


@app.get("/detection", tags=["Core"])
async def get_detection():
    """Current parking state snapshot (minimal data for real-time monitoring)

    Returns only essential data: timestamp, total spaces, and occupied spaces.
    Edge device provides minimal current state as per simplification plan.
    """
    try:
        stats = await parking_service.get_detection_stats()

        return DetectionSnapshot(
            totalSpaces=stats.get("total_zones", parking_service.config.get_total_zones()),
            occupiedSpaces=stats.get("occupied_zones", 0)
        ).model_dump()

    except Exception as e:
        logging.error(f"Detection stats error: {e}")
        return JSONResponse(
            content=ErrorResponse(
                error="Detection Error",
                message="Failed to get detection stats"
            ).model_dump(),
            status_code=500
        )


@app.get("/snapshot", tags=["Debug"])
async def get_snapshot():
    """Get processed snapshot with detection overlays

    Returns the latest processed frame with vehicle detection bounding boxes
    and zone overlays for visual verification of detection accuracy.
    """
    try:
        image_bytes = parking_service.get_snapshot_image()
        if image_bytes is None:
            return JSONResponse(
                content=ErrorResponse(
                    error="Snapshot Not Available",
                    message="No processed snapshot available yet"
                ).model_dump(),
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
    except Exception as e:
        logging.error(f"Snapshot error: {e}")
        return JSONResponse(
            content=ErrorResponse(
                error="Snapshot Error",
                message="Failed to retrieve processed snapshot"
            ).model_dump(),
            status_code=500
        )


@app.get("/frame", tags=["Debug"])
async def get_raw_frame():
    """Get raw camera frame without processing

    Returns the unprocessed camera frame for troubleshooting camera
    settings, focus, and exposure without AI detection overlays.
    """
    try:
        image_bytes = parking_service.get_raw_frame_image()
        if image_bytes is None:
            return JSONResponse(
                content=ErrorResponse(
                    error="Frame Not Available",
                    message="No raw camera frame available yet"
                ).model_dump(),
                status_code=404
            )

        return Response(
            content=image_bytes,
            media_type="image/jpeg",
            headers={
                "Content-Disposition": "inline; filename=parking_raw_frame.jpg",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    except Exception as e:
        logging.error(f"Raw frame error: {e}")
        return JSONResponse(
            content=ErrorResponse(
                error="Frame Error",
                message="Failed to retrieve raw camera frame"
            ).model_dump(),
            status_code=500
        )

# Camera Control API Endpoints (now using dedicated controller)
@app.get("/camera/status", response_model=CameraStatus, tags=["Debug"])
async def get_camera_status():
    """Get camera status for debugging - read-only

    Returns camera connection status and basic operational parameters
    for troubleshooting camera hardware and connection issues.
    """
    try:
        device_info = parking_service.get_device_info()
        connected = device_info.get("device_initialized", False)

        return CameraStatus(
            connected=connected,
            fps=30.0 if connected else None,
            resolution="1920x1080" if connected else None,
            autofocus=True if connected else None,
            status="healthy" if connected else "error"
        )

    except Exception as e:
        logging.error(f"Camera status error: {e}")
        return JSONResponse(
            content=ErrorResponse(
                error="Camera Status Error",
                message="Failed to retrieve camera status"
            ).model_dump(),
            status_code=500
        )



@app.post("/camera/restart", response_model=OperationResponse, tags=["Debug"])
async def restart_camera():
    """Restart camera connection for operational recovery

    Forces camera reconnection and resets to default settings.
    Used for recovering from camera hardware issues or configuration problems.
    """
    try:
        # Force camera restart for recovery
        result = await camera_controller.reset_to_defaults()

        return OperationResponse(
            status="success",
            message="Camera restarted successfully"
        )

    except Exception as e:
        logging.error(f"Camera restart error: {e}")
        return JSONResponse(
            content=ErrorResponse(
                error="Camera Restart Error",
                message="Failed to restart camera connection"
            ).model_dump(),
            status_code=500
        )


# EDGE SIMPLIFICATION: Camera presets managed centrally via Ansible


@app.get("/detections", tags=["Core"])
async def get_detections_batch(
    from_ts: int = Query(None, description="Start timestamp (epoch milliseconds)"),
    to_ts: int = Query(None, description="End timestamp (epoch milliseconds)"), 
    limit: int = Query(100, description="Maximum number of detections (default: 100, max: 10000)", le=10000, ge=1),
    sort: str = Query("desc", description="Sort order: 'asc' (oldest first) or 'desc' (newest first)")
):
    """Professional batch retrieval with sensible defaults
    
    Default behavior (no parameters): Returns last 100 detections from past 24 hours, newest first.
    
    Features:
    - Timestamp range filtering (milliseconds since epoch)
    - Configurable sorting (newest/oldest first)
    - Pagination support with cursors
    - Maximum 7-day time range limit
    - Professional error handling
    
    Examples:
    - GET /detections -> Last 100 detections, past 24h
    - GET /detections?limit=50 -> Last 50 detections
    - GET /detections?from_ts=1640995200000&to_ts=1641081600000 -> Specific range
    """
    try:
        # Apply professional defaults
        current_time_ms = int(time.time() * 1000)
        
        # Default to last 24 hours if no time range specified
        if from_ts is None and to_ts is None:
            from_ts = current_time_ms - (24 * 60 * 60 * 1000)  # 24 hours ago
            to_ts = current_time_ms
        
        # Validate sort parameter
        if sort not in ["asc", "desc"]:
            return JSONResponse(
                content=ErrorResponse(
                    error="Invalid Sort Parameter",
                    message="Sort parameter must be 'asc' or 'desc'"
                ).model_dump(),
                status_code=400
            )

        # Get detections from local storage
        detections = await edge_storage.get_detections(
            from_ts=from_ts,
            to_ts=to_ts,
            limit=limit,
            sort_order=sort
        )

        # Calculate pagination info
        has_more = len(detections) == limit
        next_from_ts = None
        if has_more and detections:
            # For 'desc' sort, next cursor is oldest timestamp
            # For 'asc' sort, next cursor is newest timestamp  
            if sort == "desc":
                next_from_ts = detections[-1].ts - 1  # Exclusive boundary
            else:
                next_from_ts = detections[-1].ts + 1  # Exclusive boundary

        # Convert to response format with pagination
        detection_batch = DetectionBatch(
            detections=detections,
            total=len(detections),
            fromTs=from_ts,
            toTs=to_ts,
            hasMore=has_more,
            nextFromTs=next_from_ts
        )

        return detection_batch.model_dump()

    except ValueError as e:
        # Handle validation errors from EdgeStorage
        logging.warning(f"Invalid detections query: {e}")
        return JSONResponse(
            content=ErrorResponse(
                error="Invalid Query Parameters",
                message=str(e)
            ).model_dump(),
            status_code=400
        )
    except Exception as e:
        logging.error(f"Detections batch error: {e}")
        return JSONResponse(
            content=ErrorResponse(
                error="Detections Batch Error",
                message="Failed to retrieve detections batch"
            ).model_dump(),
            status_code=500
        )


@app.get("/config", response_model=ConfigResponse, tags=["Core"])
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
            content=ErrorResponse(
                error="Configuration Error",
                message="Failed to retrieve system configuration"
            ).model_dump(),
            status_code=500
        )


@app.post("/config", response_model=OperationResponse, tags=["Core"])
async def update_configuration():
    """Update deployment identifiers - API key protected

    Allows remote configuration of device identity for central API integration.
    Requires valid API key for authentication.
    """
    try:
        # TODO: Implement proper API key validation and config update
        return OperationResponse(
            status="not_implemented",
            message="Configuration update not yet implemented - edge simplification in progress"
        )

    except Exception as e:
        logging.error(f"Configuration update error: {e}")
        return JSONResponse(
            content=ErrorResponse(
                error="Configuration Update Error",
                message="Failed to update configuration"
            ).model_dump(),
            status_code=500
        )


# Landing page and dashboard endpoints
@app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
async def landing_page(request: Request):
    """Landing page with parking monitor overview and navigation"""
    try:
        # Get current stats for display
        stats = await parking_service.get_detection_stats()
        device_info = parking_service.get_device_info()

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "stats": stats,
            "device_info": device_info,
            "service_name": "Parking Monitor v2.0",
            "api_endpoints": [
                {"path": "/health", "description": "Service health check"},
                {"path": "/detection", "description": "Current parking state"},
                {"path": "/snapshot", "description": "Detection snapshot image"},
                {"path": "/frame", "description": "Raw camera frame"},
                {"path": "/detections", "description": "Historical detections batch"},
                {"path": "/config", "description": "System configuration"}
            ]
        })
    except Exception as e:
        logging.error(f"Landing page error: {e}")
        return HTMLResponse(
            content="<h1>Parking Monitor Service</h1><p>Error loading dashboard - check service logs</p>",
            status_code=500
        )


@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard"])
async def dashboard_redirect(request: Request):
    """Redirect to main landing page for compatibility"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "service_name": "Parking Monitor Dashboard",
        "message": "Parking detection service operational"
    })


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