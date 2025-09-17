"""
Cache Performance Metrics for oaParkingMonitor API

Tracks cache hit rates, bandwidth savings, and response time improvements
to measure the effectiveness of HTTP caching implementation.
"""

import time
import threading
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class CacheMetrics:
    """Cache performance metrics for a specific endpoint"""
    total_requests: int = 0
    cache_hits: int = 0  # 304 Not Modified responses
    cache_misses: int = 0  # New content served
    bytes_saved: int = 0  # Estimated bandwidth saved from 304 responses
    total_response_time: float = 0.0  # Total response time for metrics
    avg_response_time_cached: float = 0.0  # Average for cache hits
    avg_response_time_uncached: float = 0.0  # Average for cache misses
    last_reset: float = field(default_factory=time.time)


class CacheMonitor:
    """Thread-safe cache performance monitor"""
    
    def __init__(self):
        self._metrics: Dict[str, CacheMetrics] = defaultdict(CacheMetrics)
        self._lock = threading.Lock()
        self._start_time = time.time()
    
    def record_request(self, endpoint: str, was_cached: bool, response_size: int, 
                      response_time: float) -> None:
        """Record a request and its cache performance"""
        with self._lock:
            metrics = self._metrics[endpoint]
            metrics.total_requests += 1
            
            if was_cached:
                metrics.cache_hits += 1
                metrics.bytes_saved += response_size
                # Update cached response time average
                if metrics.cache_hits == 1:
                    metrics.avg_response_time_cached = response_time
                else:
                    metrics.avg_response_time_cached = (
                        (metrics.avg_response_time_cached * (metrics.cache_hits - 1) + response_time) 
                        / metrics.cache_hits
                    )
            else:
                metrics.cache_misses += 1
                # Update uncached response time average
                if metrics.cache_misses == 1:
                    metrics.avg_response_time_uncached = response_time
                else:
                    metrics.avg_response_time_uncached = (
                        (metrics.avg_response_time_uncached * (metrics.cache_misses - 1) + response_time) 
                        / metrics.cache_misses
                    )
            
            metrics.total_response_time += response_time
    
    def get_metrics(self, endpoint: Optional[str] = None) -> Dict[str, Any]:
        """Get cache metrics for specific endpoint or all endpoints"""
        with self._lock:
            if endpoint:
                if endpoint not in self._metrics:
                    return self._empty_metrics(endpoint)
                return self._format_metrics(endpoint, self._metrics[endpoint])
            
            # Return all metrics
            result = {}
            for ep, metrics in self._metrics.items():
                result[ep] = self._format_metrics(ep, metrics)
            
            # Add overall summary
            result["_summary"] = self._calculate_summary()
            return result
    
    def _format_metrics(self, endpoint: str, metrics: CacheMetrics) -> Dict[str, Any]:
        """Format metrics for JSON response"""
        cache_hit_rate = (metrics.cache_hits / metrics.total_requests * 100) if metrics.total_requests > 0 else 0
        avg_response_time = (metrics.total_response_time / metrics.total_requests) if metrics.total_requests > 0 else 0
        
        # Calculate time savings from caching
        time_saved = 0.0
        if metrics.cache_hits > 0 and metrics.avg_response_time_uncached > 0:
            time_saved = metrics.cache_hits * (metrics.avg_response_time_uncached - metrics.avg_response_time_cached)
        
        return {
            "endpoint": endpoint,
            "total_requests": metrics.total_requests,
            "cache_hits": metrics.cache_hits,
            "cache_misses": metrics.cache_misses,
            "cache_hit_rate_percent": round(cache_hit_rate, 2),
            "bytes_saved": metrics.bytes_saved,
            "bytes_saved_mb": round(metrics.bytes_saved / (1024 * 1024), 2),
            "avg_response_time_ms": round(avg_response_time * 1000, 2),
            "avg_response_time_cached_ms": round(metrics.avg_response_time_cached * 1000, 2),
            "avg_response_time_uncached_ms": round(metrics.avg_response_time_uncached * 1000, 2),
            "time_saved_seconds": round(time_saved, 2),
            "uptime_hours": round((time.time() - metrics.last_reset) / 3600, 2)
        }
    
    def _empty_metrics(self, endpoint: str) -> Dict[str, Any]:
        """Return empty metrics for non-existent endpoint"""
        return {
            "endpoint": endpoint,
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "cache_hit_rate_percent": 0.0,
            "bytes_saved": 0,
            "bytes_saved_mb": 0.0,
            "avg_response_time_ms": 0.0,
            "avg_response_time_cached_ms": 0.0,
            "avg_response_time_uncached_ms": 0.0,
            "time_saved_seconds": 0.0,
            "uptime_hours": round((time.time() - self._start_time) / 3600, 2)
        }
    
    def _calculate_summary(self) -> Dict[str, Any]:
        """Calculate overall cache performance summary"""
        total_requests = sum(m.total_requests for m in self._metrics.values())
        total_hits = sum(m.cache_hits for m in self._metrics.values())
        total_bytes_saved = sum(m.bytes_saved for m in self._metrics.values())
        total_time_saved = 0.0
        
        for metrics in self._metrics.values():
            if metrics.cache_hits > 0 and metrics.avg_response_time_uncached > 0:
                total_time_saved += metrics.cache_hits * (
                    metrics.avg_response_time_uncached - metrics.avg_response_time_cached
                )
        
        overall_hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "overall_cache_hit_rate_percent": round(overall_hit_rate, 2),
            "total_requests": total_requests,
            "total_cache_hits": total_hits,
            "total_bytes_saved": total_bytes_saved,
            "total_bytes_saved_mb": round(total_bytes_saved / (1024 * 1024), 2),
            "total_time_saved_seconds": round(total_time_saved, 2),
            "monitored_endpoints": len(self._metrics),
            "uptime_hours": round((time.time() - self._start_time) / 3600, 2)
        }
    
    def reset_metrics(self, endpoint: Optional[str] = None) -> bool:
        """Reset metrics for specific endpoint or all endpoints"""
        with self._lock:
            if endpoint:
                if endpoint in self._metrics:
                    self._metrics[endpoint] = CacheMetrics()
                    return True
                return False
            else:
                self._metrics.clear()
                self._start_time = time.time()
                return True


# Global cache monitor instance
cache_monitor = CacheMonitor()


class CacheMetricsMiddleware:
    """Middleware to automatically track cache performance"""
    
    @staticmethod
    def track_request(endpoint: str, status_code: int, response_size: int, 
                     response_time: float) -> None:
        """Track a request's cache performance"""
        was_cached = status_code == 304  # Not Modified
        cache_monitor.record_request(endpoint, was_cached, response_size, response_time)


def estimate_response_size(content: Any) -> int:
    """Estimate response size in bytes"""
    if isinstance(content, bytes):
        return len(content)
    elif isinstance(content, str):
        return len(content.encode('utf-8'))
    elif isinstance(content, dict):
        # Rough estimation for JSON content
        import json
        return len(json.dumps(content).encode('utf-8'))
    else:
        return len(str(content).encode('utf-8'))


# Context manager for tracking request performance
class RequestTracker:
    """Context manager to track request performance automatically"""
    
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.start_time = None
        self.status_code = 200
        self.response_size = 0
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            response_time = time.time() - self.start_time
            CacheMetricsMiddleware.track_request(
                self.endpoint, 
                self.status_code, 
                self.response_size, 
                response_time
            )
    
    def set_response_info(self, status_code: int, response_size: int):
        """Set response information for tracking"""
        self.status_code = status_code
        self.response_size = response_size


# Decorator for automatic cache metrics tracking
def track_cache_performance(endpoint_name: str = None):
    """Decorator to automatically track cache performance for endpoints"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            ep_name = endpoint_name or func.__name__
            
            with RequestTracker(ep_name) as tracker:
                start_time = time.time()
                result = func(*args, **kwargs)
                
                # Estimate response size and status code
                if hasattr(result, 'status_code'):
                    status_code = result.status_code
                    if hasattr(result, 'body'):
                        response_size = len(result.body)
                    else:
                        response_size = estimate_response_size(result)
                else:
                    status_code = 200
                    response_size = estimate_response_size(result)
                
                tracker.set_response_info(status_code, response_size)
                
            return result
        return wrapper
    return decorator


# Utility functions for reporting
def get_cache_performance_report() -> Dict[str, Any]:
    """Get comprehensive cache performance report"""
    return cache_monitor.get_metrics()


def get_endpoint_cache_stats(endpoint: str) -> Dict[str, Any]:
    """Get cache statistics for specific endpoint"""
    return cache_monitor.get_metrics(endpoint)


def reset_cache_metrics(endpoint: Optional[str] = None) -> bool:
    """Reset cache metrics"""
    return cache_monitor.reset_metrics(endpoint)