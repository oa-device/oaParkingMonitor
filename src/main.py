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
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

from .detector import ParkingDetector
from .dashboard.dashboard import create_dashboard_app
from .integrations import YHUIntegration
from .config import ConfigManager


# Pydantic response models for API documentation
class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    service: str
    version: str
    uptime: float
    timestamp: str

class DetectionStatsResponse(BaseModel):
    """Parking detection statistics response"""
    vehicles_detected: int
    total_spaces: int
    occupied_spaces: int
    occupancy_rate: float
    last_detection: Optional[str]
    video_source: str
    processing_fps: float

class ParkingSpaceResponse(BaseModel):
    """Individual parking space information"""
    id: int
    occupied: bool
    confidence: float
    coordinates: List[int]

class ParkingSpacesResponse(BaseModel):
    """All parking spaces response"""
    spaces: List[ParkingSpaceResponse]
    total_spaces: int
    occupied_count: int
    available_count: int

class YHUStatusResponse(BaseModel):
    """YHU integration status response"""
    enabled: bool
    status: str
    last_sync: Optional[str] = None
    sync_interval: Optional[int] = None

class YHUConfigResponse(BaseModel):
    """YHU integration configuration response"""
    enabled: bool
    api_url: Optional[str]
    lot_id: Optional[str]
    sync_interval: int

class YHUTestResponse(BaseModel):
    """YHU connection test response"""
    success: bool
    error: Optional[str] = None


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


# Create FastAPI application with comprehensive documentation
app = FastAPI(
    title="OrangeAd Parking Monitor API",
    description="""**Standalone AI vision service for parking detection and monitoring**
    
    This API provides real-time parking space detection using YOLOv11m AI models.
    
    ## Features
    - **Real-time Detection**: Live video processing for parking occupancy
    - **YHU Integration**: Sync with YHU Dashboard for centralized monitoring
    - **RESTful API**: Complete parking analytics and status endpoints
    - **WebSocket Support**: Live updates and streaming capabilities
    
    ## Quick Start
    - **Health Check**: `GET /health` - Service status and uptime
    - **Detection Stats**: `GET /api/stats` - Current parking statistics  
    - **Live Data**: `GET /api/detection` - Real-time occupancy data
    - **Space Details**: `GET /api/spaces` - Individual parking space information
    
    ## Dashboard
    - **Web Interface**: `/dashboard` - Visual monitoring interface
    - **API Documentation**: `/docs` - Interactive API explorer (you are here!)
    """,
    version="2.0.0",
    lifespan=lifespan,
    contact={
        "name": "OrangeAd Support",
        "email": "support@orangead.ca",
    },
    license_info={
        "name": "Proprietary",
        "identifier": "Proprietary",
    },
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Endpoints with comprehensive documentation
@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    description="""Get the current health status of the Parking Monitor service.
    
    Returns service status, uptime, and basic system information.
    Useful for monitoring and load balancer health checks.
    """,
    responses={
        200: {
            "description": "Service is running normally",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "service": "parking-monitor",
                        "version": "2.0.0",
                        "uptime": 3600.5,
                        "timestamp": "2025-01-15T10:30:00Z"
                    }
                }
            }
        }
    },
    tags=["Health"]
)
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
@app.get(
    "/api/stats",
    response_model=DetectionStatsResponse,
    summary="Get Detection Statistics",
    description="""Retrieve comprehensive parking detection statistics.
    
    Returns real-time metrics including vehicle counts, occupancy rates,
    processing performance, and video source information.
    """,
    responses={
        200: {
            "description": "Current detection statistics",
            "content": {
                "application/json": {
                    "example": {
                        "vehicles_detected": 3,
                        "total_spaces": 4,
                        "occupied_spaces": 3,
                        "occupancy_rate": 0.75,
                        "last_detection": "2025-01-15T10:30:45Z",
                        "video_source": "parking_lot_camera_01",
                        "processing_fps": 15.2
                    }
                }
            }
        }
    },
    tags=["Parking Detection"]
)
async def get_stats():
    """Get parking detection statistics"""
    stats = await parking_service.get_detection_stats()
    return JSONResponse(stats)

@app.get(
    "/api/detection",
    response_model=DetectionStatsResponse,
    summary="Get Real-time Detection Results",
    description="""Get current parking detection results and occupancy data.
    
    This endpoint provides the same data as /api/stats but with a focus on 
    real-time detection results. Ideal for dashboards and monitoring systems
    that need current occupancy information.
    """,
    responses={
        200: {
            "description": "Current detection results",
            "content": {
                "application/json": {
                    "example": {
                        "vehicles_detected": 2,
                        "total_spaces": 4,
                        "occupied_spaces": 2,
                        "occupancy_rate": 0.50,
                        "last_detection": "2025-01-15T10:31:15Z",
                        "video_source": "parking_lot_camera_01",
                        "processing_fps": 14.8
                    }
                }
            }
        }
    },
    tags=["Parking Detection"]
)
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

@app.get(
    "/api/spaces",
    response_model=ParkingSpacesResponse,
    summary="Get Parking Space Details",
    description="""Get detailed information about individual parking spaces.
    
    Returns the status, coordinates, and detection confidence for each
    defined parking space in the monitored area.
    """,
    responses={
        200: {
            "description": "Parking space details",
            "content": {
                "application/json": {
                    "example": {
                        "spaces": [
                            {
                                "id": 1,
                                "occupied": True,
                                "confidence": 0.92,
                                "coordinates": [100, 150, 200, 300]
                            },
                            {
                                "id": 2,
                                "occupied": False,
                                "confidence": 0.88,
                                "coordinates": [250, 150, 350, 300]
                            }
                        ],
                        "total_spaces": 4,
                        "occupied_count": 2,
                        "available_count": 2
                    }
                }
            }
        }
    },
    tags=["Parking Detection"]
)
async def get_parking_spaces():
    """Get parking space definitions and status"""
    return await parking_service.detector.get_parking_spaces()

# YHU Integration endpoints
@app.get(
    "/api/yhu/status",
    response_model=YHUStatusResponse,
    summary="Get YHU Integration Status",
    description="""Get the current status of YHU Dashboard integration.
    
    Returns whether YHU sync is enabled, connection status, and last sync time.
    """,
    responses={
        200: {
            "description": "YHU integration status",
            "content": {
                "application/json": {
                    "example": {
                        "enabled": True,
                        "status": "connected",
                        "last_sync": "2025-01-15T10:29:30Z",
                        "sync_interval": 30
                    }
                }
            }
        }
    },
    tags=["YHU Integration"]
)
async def get_yhu_status():
    """Get YHU integration status"""
    return await parking_service.get_yhu_status()

@app.get(
    "/api/yhu/config",
    response_model=YHUConfigResponse,
    summary="Get YHU Configuration",
    description="""Get YHU Dashboard integration configuration settings.
    
    Returns API endpoint, lot ID, and synchronization settings.
    """,
    responses={
        200: {
            "description": "YHU configuration settings",
            "content": {
                "application/json": {
                    "example": {
                        "enabled": True,
                        "api_url": "https://yhu-dashboard.example.com/api",
                        "lot_id": "parking_lot_001",
                        "sync_interval": 30
                    }
                }
            }
        }
    },
    tags=["YHU Integration"]
)
async def get_yhu_config():
    """Get YHU integration configuration"""
    return JSONResponse({
        "enabled": parking_service.config.yhu_integration.enabled,
        "api_url": parking_service.config.yhu_integration.api_url,
        "lot_id": parking_service.config.yhu_integration.lot_id,
        "sync_interval": parking_service.config.yhu_integration.sync_interval
    })

@app.post(
    "/api/yhu/test",
    response_model=YHUTestResponse,
    summary="Test YHU Connection",
    description="""Test connectivity to YHU Dashboard API.
    
    Attempts to establish a connection to the configured YHU Dashboard
    and returns success status with any error details.
    """,
    responses={
        200: {
            "description": "Connection test result",
            "content": {
                "application/json": {
                    "examples": {
                        "success": {
                            "summary": "Successful connection",
                            "value": {"success": True}
                        },
                        "failure": {
                            "summary": "Connection failed",
                            "value": {
                                "success": False,
                                "error": "Connection timeout to YHU API"
                            }
                        }
                    }
                }
            }
        },
        400: {
            "description": "YHU integration not enabled",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "error": "YHU integration not enabled"
                    }
                }
            }
        }
    },
    tags=["YHU Integration"]
)
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