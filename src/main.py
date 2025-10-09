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

# Load environment variables from .env file for local development
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure .env is loaded from the project root directory
project_root = Path(__file__).parent.parent
env_file = project_root / '.env'
load_dotenv(env_file, override=True)  # Override LaunchAgent env vars with .env values

from typing import Union, List

import uvicorn
from fastapi import FastAPI, Request, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPAuthorizationCredentials

# Import modular components
from .api.models import ConfigResponse
from .services.parking_monitor import ParkingMonitorService
from .services.camera_controller import CameraController

# Import camera preset models
from .models import CameraPresetsResponse, CameraOperationResponse

# Import edge components
from .models.edge import (
    DetectionBatch, DetectionSnapshot, HealthResponse,
    ErrorResponse, OperationResponse, CameraStatus, ConfirmUploadRequest,
    ConfirmUploadResponse, ZoneChange, DeltaResponse, ConfigUpdateRequest,
    ProcessingConfigUpdate
)
from .storage.edge_storage import EdgeStorage

# Import middleware
from .middleware.compression import OptimizedGzipMiddleware
from .middleware.auth import validate_api_key, security

# Import caching utilities
from .utils.cache import (
    CacheMiddleware, CachePolicy, create_config_response, 
    create_detection_response, create_health_response, create_image_response
)
from .utils.cache_metrics import get_cache_performance_report, reset_cache_metrics


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

## Key Endpoints
- **`GET /health`** - Service status
- **`GET /detection`** - Current parking state
- **`GET /detections`** - Historical data batch
- **`GET /snapshot`** - Visual detection image
- **`GET /camera/presets`** - Available camera presets
- **`POST /camera/preset/{name}`** - Apply lighting preset

## Dashboard
- **`GET /`** - Web interface
    """,
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    tags_metadata=[
        {
            "name": "Core",
            "description": "Essential edge device functionality - Primary API endpoints for production use"
        },
        {
            "name": "Core - Health & Status",
            "description": "Service health monitoring and operational status"
        },
        {
            "name": "Core - Detection Data",
            "description": "Parking detection results and historical data retrieval"
        },
        {
            "name": "Core - Configuration",
            "description": "System configuration management and remote updates"
        },
        {
            "name": "Debug",
            "description": "Operational debugging and troubleshooting - Development and diagnostic tools"
        },
        {
            "name": "Debug - Visual",
            "description": "Image snapshots and visual debugging tools"
        },
        {
            "name": "Debug - Camera Control",
            "description": "Camera hardware management and preset configuration"
        },
        {
            "name": "Debug - System",
            "description": "Upload monitoring, cache management, and system diagnostics"
        },
        {
            "name": "Dashboard",
            "description": "Web interface for device debugging and service overview"
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

# Add gzip compression middleware for JSON endpoints
# Targets /detections, /health, /detection, /config for 60-70% payload reduction
app.add_middleware(OptimizedGzipMiddleware)


# Core API Endpoints
@app.get("/health", response_model=HealthResponse, tags=["Core - Health & Status"])
async def health_check(request: Request):
    """Service health check - minimal 2-field response per edge simplification with caching

    Returns only essential health status and timestamp for monitoring systems.
    Edge device provides minimal data as per simplification philosophy.
    Health includes parking service and upload service status.
    
    Caching: 30-second cache with ETag support to reduce redundant health polls.
    """
    # Check both parking service and upload service health
    parking_healthy = parking_service.running
    upload_healthy = True

    # Check upload service health if enabled
    if parking_service.upload_service.config.enabled:
        upload_stats = parking_service.upload_service.get_upload_stats()
        upload_healthy = upload_stats.get("is_healthy", True)

    overall_healthy = parking_healthy and upload_healthy

    health_data = HealthResponse(
        status="ok" if overall_healthy else "error"
    ).model_dump()

    # Return cached response with health policy (30-second cache)
    return create_health_response(health_data, request)


@app.get("/detection", tags=["Core - Detection Data"])
async def get_detection(request: Request):
    """Current parking state snapshot (minimal data for real-time monitoring) with caching

    Returns only essential data: timestamp, total spaces, and occupied spaces.
    Edge device provides minimal current state as per simplification plan.
    
    Caching: No-cache with ETag support based on last detection timestamp.
    Returns 304 Not Modified if data unchanged since last request.
    """
    try:
        stats = await parking_service.get_detection_stats()
        
        detection_data = DetectionSnapshot(
            totalSpaces=stats.get("total_zones", parking_service.config.get_total_zones()),
            occupiedSpaces=stats.get("occupied_zones", 0)
        ).model_dump()

        # Get last detection timestamp for cache validation
        last_detection_ts = stats.get("last_detection_epoch", time.time())

        # Return cached response with detection policy (no-cache + ETag)
        return create_detection_response(detection_data, request, last_detection_ts)

    except Exception as e:
        logging.error(f"Detection stats error: {e}")
        return JSONResponse(
            content=ErrorResponse(
                error="Detection Error",
                message="Failed to get detection stats"
            ).model_dump(),
            status_code=500
        )


@app.get("/detection/changes", response_model=DeltaResponse, tags=["Core - Detection Data"])
async def get_detection_changes(
    since: int = Query(..., description="Timestamp in milliseconds since epoch to get changes from"),
    limit: int = Query(100, description="Maximum number of changes to return (default: 100, max: 1000)", le=1000, ge=1)
):
    """Get incremental parking zone changes since specified timestamp

    This endpoint provides delta updates for clients that poll frequently,
    returning only zones that have changed since the specified timestamp.
    This significantly reduces data transfer compared to full state requests.
    
    Key Benefits:
    - Minimal payload: Only changed zones are returned
    - Reduced bandwidth: Up to 95% less data for incremental updates
    - Efficient polling: Clients can poll frequently without waste
    - Change history: Includes previous and current state for each change
    
    Retention: Changes are kept in memory for 10 minutes.
    """
    try:
        # Validate timestamp
        if since < 0:
            return JSONResponse(
                content=ErrorResponse(
                    error="Invalid Timestamp",
                    message="Timestamp must be a positive number (milliseconds since epoch)"
                ).model_dump(),
                status_code=400
            )
        
        current_time = int(time.time() * 1000)
        
        # Check if timestamp is too old (beyond retention window)
        retention_ms = 10 * 60 * 1000  # 10 minutes
        if since < (current_time - retention_ms):
            return JSONResponse(
                content=ErrorResponse(
                    error="Timestamp Too Old",
                    message=f"Timestamp is beyond retention window of 10 minutes. Use /detection for full state."
                ).model_dump(),
                status_code=400
            )
        
        # Get changes from detector
        changes_data = parking_service.detector.get_zone_changes_since(since)
        
        # Apply limit
        if len(changes_data) > limit:
            changes_data = changes_data[:limit]
        
        # Convert to response models
        zone_changes = [ZoneChange(**change_data) for change_data in changes_data]
        
        # Check if there might be more changes beyond what we returned
        tracker_stats = parking_service.detector.get_change_tracker_stats()
        has_more_changes = len(changes_data) == limit and tracker_stats.get("total_changes", 0) > limit
        
        return DeltaResponse(
            changes=zone_changes,
            sinceTimestamp=since,
            totalChanges=len(zone_changes),
            hasMoreChanges=has_more_changes
        )
        
    except Exception as e:
        logging.error(f"Delta changes error: {e}")
        return JSONResponse(
            content=ErrorResponse(
                error="Delta Changes Error",
                message="Failed to retrieve zone changes"
            ).model_dump(),
            status_code=500
        )


@app.get("/snapshot", tags=["Debug - Visual"])
async def get_snapshot(request: Request, quality: int = Query(95, ge=10, le=100, description="JPEG quality (10-100, default 95)")):
    """Get processed snapshot with detection overlays

    Returns the latest processed frame with vehicle detection bounding boxes
    and zone overlays for visual verification of detection accuracy.
    
    Caching: No-cache with proper timestamp headers for real-time images.
    
    Args:
        quality: JPEG quality level for bandwidth optimization (10-100, default 95)
    """
    try:
        image_bytes = parking_service.get_snapshot_image(quality)
        if image_bytes is None:
            return JSONResponse(
                content=ErrorResponse(
                    error="Snapshot Not Available",
                    message="No processed snapshot available yet"
                ).model_dump(),
                status_code=404
            )

        # Create image response with proper cache headers
        response = create_image_response(image_bytes, request, "image/jpeg", "snapshot")
        response.headers["Content-Disposition"] = "inline; filename=parking_snapshot.jpg"
        response.headers["X-Image-Quality"] = str(quality)
        
        return response
    except Exception as e:
        logging.error(f"Snapshot error: {e}")
        return JSONResponse(
            content=ErrorResponse(
                error="Snapshot Error",
                message="Failed to retrieve processed snapshot"
            ).model_dump(),
            status_code=500
        )


@app.get("/frame", tags=["Debug - Visual"])
async def get_raw_frame(request: Request, quality: int = Query(95, ge=10, le=100, description="JPEG quality (10-100, default 95)")):
    """Get raw camera frame without processing

    Returns the unprocessed camera frame for troubleshooting camera
    settings, focus, and exposure without AI detection overlays.
    
    Caching: No-cache with proper timestamp headers for real-time images.
    
    Args:
        quality: JPEG quality level for bandwidth optimization (10-100, default 95)
    """
    try:
        image_bytes = parking_service.get_raw_frame_image(quality)
        if image_bytes is None:
            return JSONResponse(
                content=ErrorResponse(
                    error="Frame Not Available",
                    message="No raw camera frame available yet"
                ).model_dump(),
                status_code=404
            )

        # Create image response with proper cache headers
        response = create_image_response(image_bytes, request, "image/jpeg", "frame")
        response.headers["Content-Disposition"] = "inline; filename=parking_raw_frame.jpg"
        response.headers["X-Image-Quality"] = str(quality)
        
        return response
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
@app.get("/camera/status", response_model=CameraStatus, tags=["Debug - Camera Control"])
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



@app.post("/camera/restart", response_model=OperationResponse, tags=["Debug - Camera Control"])
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


# Camera Preset API Endpoints
@app.get("/camera/presets", response_model=CameraPresetsResponse, tags=["Debug - Camera Control"])
async def get_camera_presets():
    """Get available camera presets for different lighting conditions

    Returns all available camera presets with their descriptions and settings.
    Useful for selecting appropriate settings for current environmental conditions.
    """
    try:
        presets = camera_controller.get_available_presets()
        current_preset = parking_service.config.camera.active_preset or "none"

        return CameraPresetsResponse(
            presets=presets,
            current_preset=current_preset,
            server_time_epoch=time.time()
        )

    except Exception as e:
        logging.error(f"Camera presets error: {e}")
        return JSONResponse(
            content=ErrorResponse(
                error="Camera Presets Error",
                message="Failed to retrieve camera presets"
            ).model_dump(),
            status_code=500
        )


@app.post("/camera/preset/{preset_name}", response_model=CameraOperationResponse, tags=["Debug - Camera Control"])
async def apply_camera_preset(preset_name: str):
    """Apply a camera preset for specific lighting conditions

    Applies the specified camera preset to optimize image quality for current conditions.
    Available presets: auto, manual_outdoor, outdoor_bright, outdoor_normal, outdoor_overcast, outdoor_harsh

    Args:
        preset_name: Name of the preset to apply (e.g., "outdoor_harsh" for very bright conditions)
    """
    try:
        result = await camera_controller.apply_preset(preset_name)

        if result.success:
            # Update the active preset in configuration
            parking_service.config.camera.active_preset = preset_name
            logging.info(f"Applied camera preset: {preset_name}")

        return result

    except Exception as e:
        logging.error(f"Apply preset error: {e}")
        return JSONResponse(
            content=ErrorResponse(
                error="Apply Preset Error",
                message=f"Failed to apply camera preset: {preset_name}"
            ).model_dump(),
            status_code=500
        )


@app.get("/camera/preset/current", tags=["Debug - Camera Control"])
async def get_current_preset():
    """Get currently active camera preset

    Returns the name of the currently active camera preset and its settings.
    """
    try:
        current_preset = parking_service.config.camera.active_preset or "none"

        if current_preset != "none":
            presets = camera_controller.get_available_presets()
            preset_info = presets.get(current_preset)

            return JSONResponse(
                content={
                    "current_preset": current_preset,
                    "preset_info": preset_info.model_dump() if preset_info else None,
                    "camera_settings": camera_controller.get_current_settings()
                },
                status_code=200
            )
        else:
            return JSONResponse(
                content={
                    "current_preset": "none",
                    "preset_info": None,
                    "camera_settings": camera_controller.get_current_settings()
                },
                status_code=200
            )

    except Exception as e:
        logging.error(f"Current preset error: {e}")
        return JSONResponse(
            content=ErrorResponse(
                error="Current Preset Error",
                message="Failed to retrieve current camera preset"
            ).model_dump(),
            status_code=500
        )


@app.get("/upload/status", tags=["Debug - System"])
async def get_upload_status():
    """Get AWS upload service status and statistics

    Returns comprehensive upload monitoring information including:
    - Upload success/failure rates
    - Time since last upload attempt and success
    - Batch configuration and health status
    - Total detections uploaded
    """
    try:
        # Get upload stats from the upload service
        upload_stats = parking_service.upload_service.get_upload_stats()

        return JSONResponse(
            content=upload_stats,
            status_code=200
        )

    except Exception as e:
        logging.error(f"Upload status error: {e}")
        return JSONResponse(
            content=ErrorResponse(
                error="Upload Status Error",
                message="Failed to retrieve upload service status"
            ).model_dump(),
            status_code=500
        )


@app.get("/detections", tags=["Core - Detection Data"])
async def get_detections_batch(
    request: Request,
    start: int = Query(None, description="Start timestamp (epoch milliseconds)"),
    end: int = Query(None, description="End timestamp (epoch milliseconds)"),
    limit: int = Query(100, description="Maximum number of detections (default: 100, max: 10000)", le=10000, ge=1),
    sort: str = Query("desc", description="Sort order: 'asc' (oldest first) or 'desc' (newest first)"),
    uploaded: bool = Query(None, description="Filter by upload status (true/false, null for all)"),
    id: str = Query(None, description="Comma-separated detection IDs"),
    cameraId: str = Query(None, description="Comma-separated camera IDs"),
    siteId: str = Query(None, description="Comma-separated site IDs"),
    zoneId: str = Query(None, description="Comma-separated zone IDs")
):
    """Professional batch retrieval with cloud-pull architecture support

    Enhanced Features:
    - Timestamp range filtering: start/end parameters (milliseconds since epoch)
    - Upload status filtering: uploaded parameter for cloud polling
    - Comma-separated filtering: id, cameraId, siteId, zoneId support
    - Configurable sorting (newest/oldest first)
    - Pagination support with cursors

    Cloud Pull Examples:
    - GET /detections?uploaded=false -> Get unuploaded detections for cloud
    - GET /detections?id=abc,def,ghi -> Get specific detections by ID
    - GET /detections?cameraId=cam1,cam2 -> Filter by multiple cameras

    """
    try:
        # Apply professional defaults
        current_time_ms = int(time.time() * 1000)

        # Default to last 24 hours if no time range specified
        if start is None and end is None:
            start = current_time_ms - (24 * 60 * 60 * 1000)  # 24 hours ago
            end = current_time_ms

        # Validate sort parameter
        if sort not in ["asc", "desc"]:
            return JSONResponse(
                content=ErrorResponse(
                    error="Invalid Sort Parameter",
                    message="Sort parameter must be 'asc' or 'desc'"
                ).model_dump(),
                status_code=400
            )

        # Parse comma-separated values
        detection_ids = id.split(',') if id else None
        camera_ids = cameraId.split(',') if cameraId else None
        site_ids = siteId.split(',') if siteId else None
        zone_ids = zoneId.split(',') if zoneId else None

        # Clean up empty strings from splitting
        if detection_ids:
            detection_ids = [did.strip() for did in detection_ids if did.strip()]
        if camera_ids:
            camera_ids = [cid.strip() for cid in camera_ids if cid.strip()]
        if site_ids:
            site_ids = [sid.strip() for sid in site_ids if sid.strip()]
        if zone_ids:
            zone_ids = [zid.strip() for zid in zone_ids if zid.strip()]

        # Get detections from local storage using enhanced method
        detections = await edge_storage.get_detections_enhanced(
            from_ts=start,
            to_ts=end,
            limit=limit,
            uploaded=uploaded,
            detection_ids=detection_ids,
            camera_ids=camera_ids,
            site_ids=site_ids,
            zone_ids=zone_ids,
            sort_order=sort
        )



        # Calculate pagination info for non-binned response
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
            fromTs=start,
            toTs=end,
            hasMore=has_more,
            nextFromTs=next_from_ts
        )

        # Get newest detection timestamp for cache validation
        newest_ts = max((d.ts for d in detections), default=time.time() * 1000) / 1000
        
        batch_data = detection_batch.model_dump()
        
        # Return cached response with detection policy (no-cache + ETag)
        return create_detection_response(batch_data, request, newest_ts)

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


@app.post("/detections/confirm", response_model=ConfirmUploadResponse, tags=["Core - Detection Data"])
async def confirm_detections_uploaded(request: ConfirmUploadRequest):
    """Confirm that detections have been successfully uploaded to cloud

    This endpoint allows the cloud API to confirm receipt of detections,
    marking them as uploaded in local storage. This is part of the cloud-pull
    architecture where the cloud polls for new data and confirms receipt.

    Args:
        request: List of detection IDs that were successfully uploaded

    Returns:
        Confirmation response with count of successful confirmations
    """
    try:
        if not request.ids:
            return JSONResponse(
                content=ErrorResponse(
                    error="Invalid Request",
                    message="No detection IDs provided for confirmation"
                ).model_dump(),
                status_code=400
            )

        # Mark detections as uploaded in storage
        success = await edge_storage.mark_as_uploaded(request.ids)

        if success:
            logging.info(f"Confirmed {len(request.ids)} detections as uploaded")
            return ConfirmUploadResponse(
                success=True,
                confirmedCount=len(request.ids),
                failedIds=[]
            )
        else:
            logging.error("Failed to confirm detections as uploaded")
            return JSONResponse(
                content=ErrorResponse(
                    error="Confirmation Failed",
                    message="Failed to update upload status in local storage"
                ).model_dump(),
                status_code=500
            )

    except Exception as e:
        logging.error(f"Error confirming detections: {e}")
        return JSONResponse(
            content=ErrorResponse(
                error="Confirmation Error",
                message="Failed to process upload confirmation"
            ).model_dump(),
            status_code=500
        )


@app.get("/config", response_model=ConfigResponse, tags=["Core - Configuration"])
async def get_full_configuration(request: Request):
    """Get complete system configuration with caching
    
    Caching: 5-minute cache with ETag support for static configuration data.
    Returns 304 Not Modified if configuration unchanged since last request.
    """
    try:
        config_data = parking_service.get_config_data()

        current_epoch = time.time()
        config_response = ConfigResponse(
            configuration=config_data,
            metadata={
                "config_loaded_from": getattr(parking_service.config, 'config_loaded_from', None),
                "total_zones": parking_service.config.get_total_zones(),
                "modular_architecture": True,
                "version": "2.0.0"
            },
            data_epoch=current_epoch,
            request_epoch=current_epoch
        ).model_dump()

        # Return cached response with config policy (5-minute cache)
        return create_config_response(config_response, request)

    except Exception as e:
        logging.error(f"Configuration error: {e}")
        return JSONResponse(
            content=ErrorResponse(
                error="Configuration Error",
                message="Failed to retrieve system configuration"
            ).model_dump(),
            status_code=500
        )


@app.post("/config", response_model=OperationResponse, tags=["Core - Configuration"])
async def update_configuration(
    request: ConfigUpdateRequest,
    http_request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update runtime configuration - API key protected

    Allows dynamic updates to processing parameters like snapshot_interval,
    confidence_threshold, and other runtime settings.

    Supports:
    - Processing configuration: snapshot_interval, confidence_threshold, nms_threshold, max_detections
    - Deployment configuration: customerId, siteId, zoneId, cameraId (future implementation)

    Authentication: Bearer token or x-api-key header required
    """
    try:
        # Validate API key
        await validate_api_key(http_request, credentials)

        # Process processing configuration updates
        if request.processing:
            processing_dict = request.processing.model_dump(exclude_unset=True)
            if processing_dict:
                # Update runtime configuration
                result = parking_service.update_runtime_config(processing_dict)

                if result["success"]:
                    logging.info(f"Runtime configuration updated: {result['updated_fields']}")
                    return OperationResponse(
                        status="success",
                        message=f"Configuration updated: {result['message']}"
                    )
                else:
                    logging.error(f"Runtime configuration update failed: {result['error']}")
                    return JSONResponse(
                        content=ErrorResponse(
                            error="Configuration Update Failed",
                            message=result["error"]
                        ).model_dump(),
                        status_code=400
                    )

        # Process deployment configuration updates (future implementation)
        if request.deployment:
            # TODO: Implement deployment configuration updates
            logging.warning("Deployment configuration updates not yet implemented")
            return JSONResponse(
                content=ErrorResponse(
                    error="Not Implemented",
                    message="Deployment configuration updates coming soon"
                ).model_dump(),
                status_code=501
            )

        # No valid configuration provided
        return JSONResponse(
            content=ErrorResponse(
                error="Invalid Request",
                message="No valid configuration updates provided. Include 'processing' or 'deployment' sections."
            ).model_dump(),
            status_code=400
        )

    except HTTPException:
        # Re-raise HTTP exceptions (like authentication errors)
        raise
    except Exception as e:
        logging.error(f"Configuration update error: {e}")
        return JSONResponse(
            content=ErrorResponse(
                error="Configuration Update Error",
                message="Failed to update configuration"
            ).model_dump(),
            status_code=500
        )


# Cache Performance Monitoring Endpoint
@app.get("/cache/metrics", tags=["Debug - System"])
async def get_cache_metrics():
    """Get cache performance metrics and statistics
    
    Returns comprehensive caching performance data including:
    - Cache hit rates by endpoint
    - Bandwidth savings from 304 responses
    - Response time improvements
    - Overall caching effectiveness
    """
    try:
        metrics = get_cache_performance_report()
        return JSONResponse(
            content=metrics,
            status_code=200,
            headers={
                "Cache-Control": "no-cache, must-revalidate",
                "Content-Type": "application/json"
            }
        )
    except Exception as e:
        logging.error(f"Cache metrics error: {e}")
        return JSONResponse(
            content=ErrorResponse(
                error="Cache Metrics Error",
                message="Failed to retrieve cache performance metrics"
            ).model_dump(),
            status_code=500
        )


@app.post("/cache/reset", response_model=OperationResponse, tags=["Debug - System"])
async def reset_cache_metrics_endpoint():
    """Reset cache performance metrics
    
    Clears all cache performance statistics and starts fresh tracking.
    Useful for measuring cache effectiveness over specific time periods.
    """
    try:
        success = reset_cache_metrics()
        if success:
            return OperationResponse(
                status="success",
                message="Cache metrics reset successfully"
            )
        else:
            return JSONResponse(
                content=ErrorResponse(
                    error="Reset Failed",
                    message="Failed to reset cache metrics"
                ).model_dump(),
                status_code=500
            )
    except Exception as e:
        logging.error(f"Cache metrics reset error: {e}")
        return JSONResponse(
            content=ErrorResponse(
                error="Cache Reset Error",
                message="Failed to reset cache metrics"
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
    logging.info("[OK] oaParkingMonitor v2.0 - Modular Architecture")
    logging.info(f"[OK] Python: {sys.version}")
    logging.info(f"[OK] Platform: {platform.system()} {platform.machine()}")
    logging.info(f"[OK] Working directory: {os.getcwd()}")
    logging.info(f"[OK] Service available at: http://0.0.0.0:9091")
    logging.info(f"[OK] API docs at: http://0.0.0.0:9091/docs")
    logging.info("[OK] Modular architecture: Service Layer + Camera Controller + API Models")
    
    return True


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Validate environment
    if not validate_startup_environment():
        logging.error("[FAIL] Startup validation failed - exiting")
        exit(1)
    
    # Get configuration from service
    api_port = parking_service.config.api.port
    api_host = parking_service.config.api.host
    
    try:
        logging.info(f"[OK] Starting modular service on {api_host}:{api_port}")
        uvicorn.run(
            "src.main:app",
            host=api_host,
            port=api_port,
            reload=False,
            log_level="info"
        )
    except Exception as e:
        logging.error(f"[FAIL] Failed to start server: {e}")
        exit(1)