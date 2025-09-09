#!/usr/bin/env python3
#!/usr/bin/env python
"""
Production-Ready Parking Monitor Service
Optimized for macOS Metal/MPS with comprehensive monitoring
"""

import asyncio
import logging
import os
import platform
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
        self.health_score = 100
        self.error_count = 0
        self.last_error = None
        
        # Initialize YHU integration
        self.yhu_integration = None
        
        # Setup enhanced logging
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Performance monitoring
        self.performance_monitor = {
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "error_rate": 0.0,
            "uptime": 0.0
        }
        
        self.logger.info(f"Service initialized with environment: {self.config_manager.get_environment()}")
    
    def _setup_logging(self):
        """Setup production-ready logging configuration"""
        log_level = getattr(logging, self.config_manager.get_raw_config().get('service', {}).get('log_level', 'INFO').upper())
        
        # Create log directory if it doesn't exist
        log_dir = Path.home() / "orangead" / "parking-monitor" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure root logger
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(
                    log_dir / "parking_monitor.log",
                    mode='a'
                )
            ]
        )
        
        # Set specific logger levels for third-party libraries
        logging.getLogger("ultralytics").setLevel(logging.WARNING)
        logging.getLogger("torch").setLevel(logging.WARNING)
        logging.getLogger("cv2").setLevel(logging.WARNING)

    async def start_detection(self):
        """Start parking detection processing with comprehensive error handling"""
        try:
            self.running = True
            self.logger.info("Starting parking detection...")
            
            # Initialize YHU integration if enabled
            if self.config.yhu_integration.enabled:
                try:
                    self.yhu_integration = YHUIntegration(self.config.yhu_integration)
                    await self.yhu_integration.__aenter__()
                    await self.yhu_integration.start()
                    self.logger.info("YHU integration initialized")
                except Exception as e:
                    self._handle_error(e, "YHU integration initialization")
                    # Continue without YHU integration
                    self.yhu_integration = None
            
            # Start detector in background task with error handling
            detection_task = asyncio.create_task(self._run_detection_with_recovery())
            
            # Start YHU sync loop if enabled
            if self.yhu_integration:
                yhu_sync_task = asyncio.create_task(self._yhu_sync_loop())
            
            # Start health monitoring task
            health_task = asyncio.create_task(self._health_monitoring_loop())
            
            self.logger.info("Parking detection service started successfully")
            
        except Exception as e:
            self._handle_error(e, "Service startup")
            self.running = False
            raise
    
    async def _run_detection_with_recovery(self):
        """Run detection with automatic recovery on errors"""
        retry_count = 0
        max_retries = 3
        
        while self.running:
            try:
                await self.detector.process_video_stream()
            except Exception as e:
                self._handle_error(e, f"Detection processing (retry {retry_count + 1})")
                
                retry_count += 1
                if retry_count >= max_retries:
                    self.logger.critical("Maximum retries exceeded, stopping detection")
                    self.running = False
                    break
                
                # Wait before retry
                await asyncio.sleep(min(2 ** retry_count, 30))  # Exponential backoff, max 30s
            else:
                # Reset retry count on success
                retry_count = 0
    
    async def _health_monitoring_loop(self):
        """Background task for continuous health monitoring"""
        while self.running:
            try:
                await self._update_health_metrics()
                
                # Log health alerts
                if self.health_score < 50:
                    self.logger.warning(f"Health score critically low: {self.health_score}")
                elif self.health_score < 75:
                    self.logger.info(f"Health score degraded: {self.health_score}")
                
                # Wait 30 seconds before next check
                await asyncio.sleep(30)
                
            except Exception as e:
                self._handle_error(e, "Health monitoring")
                await asyncio.sleep(60)  # Wait longer on error
        
    async def stop_detection(self):
        """Stop parking detection processing with graceful cleanup"""
        try:
            self.logger.info("Stopping parking detection service...")
            self.running = False
            
            # Stop detector
            try:
                await self.detector.stop()
                self.logger.info("Detector stopped")
            except Exception as e:
                self._handle_error(e, "Detector shutdown")
            
            # Stop YHU integration
            if self.yhu_integration:
                try:
                    await self.yhu_integration.stop()
                    await self.yhu_integration.__aexit__(None, None, None)
                    self.yhu_integration = None
                    self.logger.info("YHU integration stopped")
                except Exception as e:
                    self._handle_error(e, "YHU integration shutdown")
            
            # Final health metrics update
            await self._update_health_metrics()
            
            self.logger.info("Parking detection service stopped successfully")
            
        except Exception as e:
            self._handle_error(e, "Service shutdown")
            raise

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

    
    async def _update_health_metrics(self):
        """Update comprehensive health metrics"""
        try:
            import psutil
            
            # CPU and memory usage
            self.performance_monitor["cpu_usage"] = psutil.cpu_percent()
            self.performance_monitor["memory_usage"] = psutil.virtual_memory().percent
            self.performance_monitor["uptime"] = self.get_uptime()
            
            # Calculate error rate (errors per hour)
            uptime_hours = max(self.get_uptime() / 3600, 0.001)  # Avoid division by zero
            self.performance_monitor["error_rate"] = self.error_count / uptime_hours
            
            # Calculate health score
            self.health_score = self._calculate_health_score()
            
        except Exception as e:
            self.logger.warning(f"Health metrics update failed: {e}")
    
    def _calculate_health_score(self) -> int:
        """Calculate overall health score (0-100)"""
        try:
            score = 100
            
            # Deduct points for high resource usage
            if self.performance_monitor["cpu_usage"] > 80:
                score -= 20
            elif self.performance_monitor["cpu_usage"] > 60:
                score -= 10
                
            if self.performance_monitor["memory_usage"] > 90:
                score -= 25
            elif self.performance_monitor["memory_usage"] > 75:
                score -= 15
            
            # Deduct points for errors
            error_rate = self.performance_monitor["error_rate"]
            if error_rate > 10:  # More than 10 errors per hour
                score -= 30
            elif error_rate > 5:
                score -= 15
            elif error_rate > 1:
                score -= 5
            
            # Deduct points if detector is not running
            if not self.running:
                score -= 50
                
            # Deduct points if model failed to load
            if hasattr(self.detector, 'stats') and not self.detector.stats.get("model_loaded", False):
                score -= 25
            
            return max(0, min(100, score))
            
        except Exception as e:
            self.logger.error(f"Health score calculation failed: {e}")
            return 0
    
    def _handle_error(self, error: Exception, context: str = ""):
        """Centralized error handling with monitoring"""
        self.error_count += 1
        self.last_error = {
            "error": str(error),
            "context": context,
            "timestamp": datetime.now().isoformat(),
            "type": type(error).__name__
        }
        
        # Log error with context
        if context:
            self.logger.error(f"{context}: {error}")
        else:
            self.logger.error(f"Error occurred: {error}")
        
        # Update health metrics after error
        asyncio.create_task(self._update_health_metrics())
    
    async def get_yhu_status(self):
        """Get YHU integration status"""
        if not self.yhu_integration:
            return {"enabled": False, "status": "disabled"}
        return await self.yhu_integration.get_integration_status()

    async def get_health_status(self):
        """Get comprehensive health status for production monitoring"""
        await self._update_health_metrics()
        
        # Get detector performance metrics if available
        detector_metrics = {}
        try:
            detector_metrics = await self.detector.get_performance_metrics()
        except Exception as e:
            self.logger.debug(f"Failed to get detector metrics: {e}")
        
        health_status = {
            "running": self.running,
            "uptime": self.get_uptime(),
            "health_score": self.health_score,
            "status": self._get_status_text(),
            "system": {
                "cpu_percent": self.performance_monitor["cpu_usage"],
                "memory_percent": self.performance_monitor["memory_usage"],
                "error_count": self.error_count,
                "error_rate_per_hour": self.performance_monitor["error_rate"],
                "last_error": self.last_error
            },
            "detector": {
                "model_loaded": getattr(self.detector, 'stats', {}).get("model_loaded", False),
                "device": getattr(self.detector, 'device', 'unknown'),
                "metal_available": getattr(self.detector, 'is_apple_silicon', False),
                "performance": detector_metrics.get("performance", {})
            },
            "environment": {
                "config_env": self.config_manager.get_environment(),
                "log_level": self.config_manager.get_raw_config().get('service', {}).get('log_level', 'INFO'),
                "api_port": self.config.api_port
            }
        }
        
        # Add YHU integration status if available
        if self.yhu_integration:
            try:
                yhu_status = await self.yhu_integration.get_integration_status()
                health_status["yhu_integration"] = yhu_status
            except Exception as e:
                health_status["yhu_integration"] = {"enabled": True, "status": "error", "error": str(e)}
        else:
            health_status["yhu_integration"] = {"enabled": False, "status": "disabled"}
        
        return health_status
    
    def _get_status_text(self) -> str:
        """Get human-readable status text"""
        if not self.running:
            return "stopped"
        elif self.health_score >= 90:
            return "excellent"
        elif self.health_score >= 75:
            return "good"
        elif self.health_score >= 50:
            return "fair"
        elif self.health_score >= 25:
            return "poor"
        else:
            return "critical"


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

# Performance monitoring endpoints
@app.get(
    "/api/performance",
    summary="Get Performance Metrics",
    description="""Get detailed performance metrics including device utilization, inference timing,
    and system resource usage. Essential for monitoring production deployments.
    """,
    responses={
        200: {
            "description": "Detailed performance metrics",
            "content": {
                "application/json": {
                    "example": {
                        "device_info": {
                            "device": "mps",
                            "metal_available": True,
                            "platform": "macOS-13.4-arm64",
                            "python_version": "3.12.0"
                        },
                        "performance": {
                            "memory_usage_gb": 1.2,
                            "temperature": 45.0,
                            "avg_inference_ms": 25.3
                        },
                        "inference_stats": {
                            "avg_ms": 25.3,
                            "min_ms": 18.7,
                            "max_ms": 45.2,
                            "p95_ms": 38.1
                        }
                    }
                }
            }
        }
    },
    tags=["Performance Monitoring"]
)
async def get_performance_metrics():
    """Get detailed performance metrics"""
    try:
        metrics = await parking_service.detector.get_performance_metrics()
        return JSONResponse(metrics)
    except Exception as e:
        parking_service._handle_error(e, "Performance metrics collection")
        return JSONResponse(
            {"error": "Performance metrics unavailable", "details": str(e)}, 
            status_code=500
        )

@app.get(
    "/api/health/detailed",
    summary="Get Detailed Health Status",
    description="""Get comprehensive health status including system metrics, error tracking,
    and service diagnostics. Provides more detail than the basic /health endpoint.
    """,
    responses={
        200: {
            "description": "Detailed health information",
            "content": {
                "application/json": {
                    "example": {
                        "running": True,
                        "health_score": 95,
                        "status": "excellent",
                        "uptime": 3600.5,
                        "system": {
                            "cpu_percent": 15.2,
                            "memory_percent": 28.4,
                            "error_count": 0,
                            "error_rate_per_hour": 0.0
                        },
                        "detector": {
                            "model_loaded": True,
                            "device": "mps",
                            "metal_available": True
                        }
                    }
                }
            }
        }
    },
    tags=["Health Monitoring"]
)
async def get_detailed_health():
    """Get comprehensive health status"""
    try:
        health = await parking_service.get_health_status()
        return JSONResponse(health)
    except Exception as e:
        parking_service._handle_error(e, "Health status collection")
        return JSONResponse(
            {"error": "Health status unavailable", "details": str(e)}, 
            status_code=500
        )

@app.get(
    "/api/system/info",
    summary="Get System Information",
    description="""Get detailed system information including hardware specs, 
    software versions, and environmental configuration.
    """,
    responses={
        200: {
            "description": "System information",
            "content": {
                "application/json": {
                    "example": {
                        "hardware": {
                            "platform": "macOS-13.4-arm64",
                            "processor": "Apple M1",
                            "memory_gb": 16.0,
                            "architecture": "arm64"
                        },
                        "software": {
                            "python_version": "3.12.0",
                            "opencv_version": "4.8.1",
                            "torch_version": "2.1.0",
                            "ultralytics_version": "8.2.0"
                        },
                        "configuration": {
                            "environment": "production",
                            "api_port": 9091,
                            "log_level": "WARNING"
                        }
                    }
                }
            }
        }
    },
    tags=["System Information"]
)
async def get_system_info():
    """Get detailed system information"""
    try:
        import platform
        import psutil
        import cv2
        import torch
        from ultralytics import __version__ as ultralytics_version
        
        system_info = {
            "hardware": {
                "platform": platform.platform(),
                "processor": platform.processor(),
                "memory_gb": round(psutil.virtual_memory().total / (1024**3), 1),
                "architecture": platform.machine(),
                "cpu_count": psutil.cpu_count(),
                "cpu_count_logical": psutil.cpu_count(logical=True)
            },
            "software": {
                "python_version": platform.python_version(),
                "opencv_version": cv2.__version__,
                "torch_version": torch.__version__,
                "ultralytics_version": ultralytics_version,
                "mps_available": torch.backends.mps.is_available() if hasattr(torch.backends, 'mps') else False,
                "cuda_available": torch.cuda.is_available()
            },
            "configuration": {
                "environment": parking_service.config_manager.get_environment(),
                "api_port": parking_service.config.api_port,
                "log_level": parking_service.config_manager.get_raw_config().get('service', {}).get('log_level', 'INFO'),
                "model_path": str(parking_service.detector.model_path),
                "video_source": str(parking_service.detector.video_source)
            },
            "service": {
                "version": "2.0.0",
                "started_at": parking_service.start_time.isoformat(),
                "uptime_seconds": parking_service.get_uptime(),
                "process_id": os.getpid() if 'os' in globals() else None
            }
        }
        
        return JSONResponse(system_info)
        
    except Exception as e:
        parking_service._handle_error(e, "System info collection")
        return JSONResponse(
            {"error": "System information unavailable", "details": str(e)}, 
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


def validate_startup_environment():
    """Validate runtime environment and dependencies before starting service."""
    import sys
    from pathlib import Path
    
    # Check Python version
    if sys.version_info < (3, 12):
        logging.error(f"Python 3.12+ required, got {sys.version_info}")
        return False
        
    # Check working directory has required files
    required_files = ["pyproject.toml", "src/__init__.py", "config"]
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
    logging.info("oaParkingMonitor starting")
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