"""Health monitoring system for oaParkingMonitor."""

import asyncio
import time
import psutil
from typing import Dict, Any, Optional
import structlog

from .config_manager import ConfigManager


class HealthMonitor:
    """Monitors system and service health metrics."""
    
    def __init__(self, config: ConfigManager, detector=None, display_manager=None):
        """Initialize health monitor.
        
        Args:
            config: Configuration manager
            detector: Parking detector instance
            display_manager: Display manager instance
        """
        self.config = config
        self.detector = detector
        self.display_manager = display_manager
        self.logger = structlog.get_logger("health_monitor")
        
        self.is_running = False
        self.start_time = time.time()
        self.health_history = []
        
        # Health status
        self.current_health = {
            "overall_status": "unknown",
            "last_check": 0,
            "issues": [],
            "metrics": {}
        }
    
    async def start(self) -> None:
        """Start the health monitoring service."""
        if not self.config.health_monitoring.enabled:
            self.logger.info("Health monitoring disabled in configuration")
            return
        
        self.is_running = True
        self.logger.info("Starting health monitor",
                        check_interval=self.config.health_monitoring.check_interval)
        
        # Start monitoring loop
        asyncio.create_task(self._monitoring_loop())
    
    async def stop(self) -> None:
        """Stop the health monitoring service."""
        self.logger.info("Stopping health monitor")
        self.is_running = False
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get current health status.
        
        Returns:
            Dictionary containing current health metrics
        """
        return self.current_health.copy()
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics.
        
        Returns:
            Dictionary of system performance metrics
        """
        try:
            # CPU usage
            cpu_usage = psutil.cpu_percent(interval=0.1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_usage_gb = (memory.total - memory.available) / (1024**3)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage_percent = (disk.used / disk.total) * 100
            
            # Process info
            current_process = psutil.Process()
            process_memory = current_process.memory_info().rss / (1024**2)  # MB
            process_cpu = current_process.cpu_percent()
            
            return {
                "cpu_usage_percent": cpu_usage,
                "memory_usage_gb": memory_usage_gb,
                "memory_usage_percent": memory.percent,
                "disk_usage_percent": disk_usage_percent,
                "process_memory_mb": process_memory,
                "process_cpu_percent": process_cpu,
                "uptime_seconds": time.time() - self.start_time
            }
            
        except Exception as e:
            self.logger.error("Failed to get system metrics", error=str(e))
            return {}
    
    async def _monitoring_loop(self) -> None:
        """Main health monitoring loop."""
        while self.is_running:
            try:
                await self._perform_health_check()
                await asyncio.sleep(self.config.health_monitoring.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Health check failed", error=str(e))
                await asyncio.sleep(5)  # Short delay before retrying
    
    async def _perform_health_check(self) -> None:
        """Perform a complete health check."""
        start_time = time.time()
        issues = []
        
        try:
            # Get system metrics
            system_metrics = await self.get_system_metrics()
            
            # Check performance thresholds
            performance_issues = self._check_performance_thresholds(system_metrics)
            issues.extend(performance_issues)
            
            # Check detector health
            detector_issues = await self._check_detector_health()
            issues.extend(detector_issues)
            
            # Check display manager health
            display_issues = await self._check_display_health()
            issues.extend(display_issues)
            
            # Determine overall status
            if not issues:
                overall_status = "healthy"
            elif any(issue.get("severity") == "critical" for issue in issues):
                overall_status = "critical"
            else:
                overall_status = "warning"
            
            # Update current health
            self.current_health = {
                "overall_status": overall_status,
                "last_check": time.time(),
                "check_duration_ms": (time.time() - start_time) * 1000,
                "issues": issues,
                "metrics": system_metrics
            }
            
            # Store in history (keep last 100 checks)
            self.health_history.append(self.current_health.copy())
            if len(self.health_history) > 100:
                self.health_history = self.health_history[-50:]
            
            # Log health status
            self.logger.info("Health check completed",
                           status=overall_status,
                           issues_count=len(issues),
                           duration_ms=self.current_health["check_duration_ms"])
            
            # Log issues if any
            for issue in issues:
                level = "warning" if issue.get("severity") == "warning" else "error"
                getattr(self.logger, level)(issue["message"], **issue.get("details", {}))
        
        except Exception as e:
            self.logger.error("Health check failed", error=str(e))
            self.current_health = {
                "overall_status": "error",
                "last_check": time.time(),
                "issues": [{"message": f"Health check failed: {str(e)}", "severity": "critical"}],
                "metrics": {}
            }
    
    def _check_performance_thresholds(self, metrics: Dict[str, Any]) -> list:
        """Check performance metrics against configured thresholds."""
        issues = []
        thresholds = self.config.health_monitoring.performance_threshold
        alerts = self.config.health_monitoring.alerts
        
        # Check CPU usage
        if alerts.high_cpu and metrics.get("cpu_usage_percent", 0) > thresholds.max_cpu_percent:
            issues.append({
                "message": f"High CPU usage: {metrics['cpu_usage_percent']:.1f}%",
                "severity": "warning",
                "metric": "cpu_usage",
                "value": metrics["cpu_usage_percent"],
                "threshold": thresholds.max_cpu_percent
            })
        
        # Check memory usage
        if alerts.high_memory and metrics.get("memory_usage_gb", 0) > thresholds.max_memory_gb:
            issues.append({
                "message": f"High memory usage: {metrics['memory_usage_gb']:.1f}GB",
                "severity": "warning", 
                "metric": "memory_usage",
                "value": metrics["memory_usage_gb"],
                "threshold": thresholds.max_memory_gb
            })
        
        return issues
    
    async def _check_detector_health(self) -> list:
        """Check parking detector health."""
        issues = []
        
        if not self.detector:
            return issues
        
        try:
            # Get detector metrics
            detector_metrics = self.detector.get_performance_metrics()
            thresholds = self.config.health_monitoring.performance_threshold
            alerts = self.config.health_monitoring.alerts
            
            # Check FPS performance
            current_fps = detector_metrics.get("current_fps", 0)
            if alerts.low_fps and current_fps < thresholds.min_fps:
                issues.append({
                    "message": f"Low detection FPS: {current_fps:.1f}",
                    "severity": "warning",
                    "metric": "detection_fps",
                    "value": current_fps,
                    "threshold": thresholds.min_fps
                })
            
            # Check detection age
            detection_age = detector_metrics.get("last_detection_age", 0)
            if detection_age > 60:  # No detections for over 1 minute
                issues.append({
                    "message": f"Stale detections: {detection_age:.1f}s since last detection",
                    "severity": "warning" if detection_age < 300 else "critical",
                    "metric": "detection_age",
                    "value": detection_age
                })
        
        except Exception as e:
            issues.append({
                "message": f"Detector health check failed: {str(e)}",
                "severity": "critical"
            })
        
        return issues
    
    async def _check_display_health(self) -> list:
        """Check display manager health."""
        issues = []
        
        if not self.display_manager:
            return issues
        
        try:
            # Check if display manager is running
            if not getattr(self.display_manager, 'is_running', True):
                issues.append({
                    "message": "Display manager not running",
                    "severity": "warning",
                    "metric": "display_status"
                })
        
        except Exception as e:
            issues.append({
                "message": f"Display health check failed: {str(e)}",
                "severity": "warning"
            })
        
        return issues
    
    def get_health_history(self, limit: int = 50) -> list:
        """Get recent health check history.
        
        Args:
            limit: Maximum number of history entries to return
            
        Returns:
            List of recent health check results
        """
        return self.health_history[-limit:] if self.health_history else []
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary statistics.
        
        Returns:
            Dictionary with health summary metrics
        """
        if not self.health_history:
            return {"status": "no_data"}
        
        recent_checks = self.health_history[-10:]  # Last 10 checks
        
        # Calculate uptime percentage
        healthy_count = sum(1 for check in recent_checks if check["overall_status"] == "healthy")
        uptime_percent = (healthy_count / len(recent_checks)) * 100
        
        # Get most common issues
        all_issues = []
        for check in recent_checks:
            all_issues.extend(check.get("issues", []))
        
        issue_counts = {}
        for issue in all_issues:
            key = issue.get("metric", "unknown")
            issue_counts[key] = issue_counts.get(key, 0) + 1
        
        return {
            "current_status": self.current_health["overall_status"],
            "uptime_percent": uptime_percent,
            "total_checks": len(self.health_history),
            "recent_issues": len(all_issues),
            "common_issues": sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:5],
            "last_check": self.current_health["last_check"],
            "monitoring_duration": time.time() - self.start_time
        }