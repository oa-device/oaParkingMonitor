"""
HTTP Caching Utilities for oaParkingMonitor API

Implements efficient caching headers to reduce network traffic while maintaining
real-time detection performance. Supports ETag generation, conditional requests,
and appropriate cache policies for different endpoint types.
"""

import hashlib
import time
from typing import Optional, Dict, Any, Union
from fastapi import Request, Response
from fastapi.responses import JSONResponse


class CachePolicy:
    """Cache policy definitions for different endpoint types"""
    
    # Static configuration data - cache for 5 minutes
    STATIC_CONFIG = {
        "max_age": 300,  # 5 minutes
        "must_revalidate": True,
        "etag_enabled": True
    }
    
    # Dynamic detection data - no cache but ETag support
    DYNAMIC_DETECTION = {
        "max_age": 0,
        "no_cache": True,
        "etag_enabled": True
    }
    
    # Images and snapshots - no cache with timestamps
    IMAGE_DATA = {
        "max_age": 0,
        "no_cache": True,
        "no_store": True,
        "etag_enabled": False
    }
    
    # Health endpoints - brief cache (30 seconds)
    HEALTH_STATUS = {
        "max_age": 30,
        "must_revalidate": True,
        "etag_enabled": True
    }


class ETagGenerator:
    """ETag generation for various data types"""
    
    @staticmethod
    def generate_content_etag(content: Union[str, bytes, Dict[str, Any]]) -> str:
        """Generate ETag from content hash"""
        if isinstance(content, dict):
            # Sort keys for consistent hashing
            content_str = str(sorted(content.items()))
        elif isinstance(content, str):
            content_str = content
        elif isinstance(content, bytes):
            content_str = content.decode('utf-8', errors='ignore')
        else:
            content_str = str(content)
        
        return hashlib.md5(content_str.encode('utf-8')).hexdigest()
    
    @staticmethod
    def generate_timestamp_etag(timestamp: Union[int, float]) -> str:
        """Generate ETag from timestamp for detection data"""
        return hashlib.md5(str(int(timestamp * 1000)).encode()).hexdigest()
    
    @staticmethod
    def generate_combined_etag(*values) -> str:
        """Generate ETag from multiple values"""
        combined = ''.join(str(v) for v in values)
        return hashlib.md5(combined.encode('utf-8')).hexdigest()


class CacheHeaders:
    """Generate appropriate cache headers for responses"""
    
    @staticmethod
    def get_cache_control(policy: Dict[str, Any]) -> str:
        """Generate Cache-Control header from policy"""
        directives = []
        
        if policy.get("no_cache"):
            directives.append("no-cache")
        if policy.get("no_store"):
            directives.append("no-store")
        if policy.get("must_revalidate"):
            directives.append("must-revalidate")
        
        max_age = policy.get("max_age")
        if max_age is not None:
            directives.append(f"max-age={max_age}")
        
        return ", ".join(directives) if directives else "no-cache"
    
    @staticmethod
    def get_expires_header(max_age: int) -> str:
        """Generate Expires header"""
        if max_age <= 0:
            return "0"
        
        expires_time = time.time() + max_age
        return time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(expires_time))
    
    @staticmethod
    def apply_headers(response: Response, policy: Dict[str, Any], 
                     etag: Optional[str] = None, 
                     last_modified: Optional[Union[int, float]] = None) -> None:
        """Apply caching headers to response"""
        
        # Cache-Control header
        response.headers["Cache-Control"] = CacheHeaders.get_cache_control(policy)
        
        # Expires header
        max_age = policy.get("max_age", 0)
        response.headers["Expires"] = CacheHeaders.get_expires_header(max_age)
        
        # ETag header
        if etag and policy.get("etag_enabled", False):
            response.headers["ETag"] = f'"{etag}"'
        
        # Last-Modified header
        if last_modified:
            last_modified_time = time.gmtime(last_modified if isinstance(last_modified, (int, float)) else time.time())
            response.headers["Last-Modified"] = time.strftime("%a, %d %b %Y %H:%M:%S GMT", last_modified_time)
        
        # Additional headers for reliability
        response.headers["Pragma"] = "no-cache" if policy.get("no_cache") else "cache"


class ConditionalRequests:
    """Handle conditional HTTP requests (If-None-Match, If-Modified-Since)"""
    
    @staticmethod
    def check_if_none_match(request: Request, etag: str) -> bool:
        """Check If-None-Match header against current ETag"""
        if_none_match = request.headers.get("If-None-Match")
        if not if_none_match:
            return False
        
        # Handle multiple ETags and weak/strong validation
        etags = [tag.strip(' "') for tag in if_none_match.split(',')]
        return etag in etags or "*" in etags
    
    @staticmethod
    def check_if_modified_since(request: Request, last_modified: Union[int, float]) -> bool:
        """Check If-Modified-Since header against last modified time"""
        if_modified_since = request.headers.get("If-Modified-Since")
        if not if_modified_since:
            return True  # Consider as modified if header not present
        
        try:
            # Parse HTTP date format
            since_time = time.mktime(time.strptime(if_modified_since, "%a, %d %b %Y %H:%M:%S GMT"))
            return last_modified > since_time
        except (ValueError, TypeError):
            return True  # Consider as modified if parsing fails


class CacheMiddleware:
    """Main caching middleware for handling cache policies and conditional requests"""
    
    @staticmethod
    def create_cached_response(
        content: Any,
        policy: Dict[str, Any],
        request: Request,
        status_code: int = 200,
        last_modified: Optional[Union[int, float]] = None,
        custom_etag: Optional[str] = None,
        endpoint_name: Optional[str] = None
    ) -> Union[Response, JSONResponse]:
        """
        Create a response with appropriate caching headers and handle conditional requests
        
        Args:
            content: Response content
            policy: Cache policy from CachePolicy
            request: FastAPI request object
            status_code: HTTP status code
            last_modified: Last modified timestamp
            custom_etag: Custom ETag (if not provided, generated from content)
            endpoint_name: Endpoint name for metrics tracking
        
        Returns:
            Response with appropriate headers or 304 Not Modified
        """
        start_time = time.time()
        
        # Generate ETag if not provided
        if not custom_etag and policy.get("etag_enabled", False):
            if isinstance(content, dict):
                etag = ETagGenerator.generate_content_etag(content)
            elif last_modified:
                etag = ETagGenerator.generate_timestamp_etag(last_modified)
            else:
                etag = ETagGenerator.generate_content_etag(content)
        else:
            etag = custom_etag
        
        # Check conditional requests
        not_modified = False
        
        if etag and policy.get("etag_enabled", False):
            not_modified = ConditionalRequests.check_if_none_match(request, etag)
        
        if not not_modified and last_modified:
            not_modified = not ConditionalRequests.check_if_modified_since(request, last_modified)
        
        # Calculate estimated response size
        response_size = 0
        if isinstance(content, bytes):
            response_size = len(content)
        elif isinstance(content, str):
            response_size = len(content.encode('utf-8'))
        elif isinstance(content, dict):
            import json
            response_size = len(json.dumps(content).encode('utf-8'))
        
        # Return 304 Not Modified if content hasn't changed
        if not_modified:
            response = Response(status_code=304)
            CacheHeaders.apply_headers(response, policy, etag, last_modified)
            
            # Track cache hit performance
            if endpoint_name:
                try:
                    from .cache_metrics import CacheMetricsMiddleware
                    response_time = time.time() - start_time
                    CacheMetricsMiddleware.track_request(endpoint_name, 304, response_size, response_time)
                except ImportError:
                    pass  # Metrics not available
            
            return response
        
        # Create normal response with content
        if isinstance(content, dict):
            response = JSONResponse(content=content, status_code=status_code)
        else:
            response = Response(content=content, status_code=status_code)
        
        # Apply caching headers
        CacheHeaders.apply_headers(response, policy, etag, last_modified)
        
        # Track cache miss performance
        if endpoint_name:
            try:
                from .cache_metrics import CacheMetricsMiddleware
                response_time = time.time() - start_time
                CacheMetricsMiddleware.track_request(endpoint_name, status_code, response_size, response_time)
            except ImportError:
                pass  # Metrics not available
        
        return response


# Convenience decorators and functions
def cached_endpoint(policy: Dict[str, Any]):
    """Decorator for applying cache policy to endpoints"""
    def decorator(func):
        func._cache_policy = policy
        return func
    return decorator


def get_endpoint_policy(endpoint_type: str) -> Dict[str, Any]:
    """Get cache policy for specific endpoint type"""
    policies = {
        "config": CachePolicy.STATIC_CONFIG,
        "detection": CachePolicy.DYNAMIC_DETECTION,
        "health": CachePolicy.HEALTH_STATUS,
        "image": CachePolicy.IMAGE_DATA
    }
    return policies.get(endpoint_type, CachePolicy.DYNAMIC_DETECTION)


# Example usage functions
def create_config_response(content: Dict[str, Any], request: Request) -> Union[Response, JSONResponse]:
    """Create cached response for configuration endpoints"""
    return CacheMiddleware.create_cached_response(
        content=content,
        policy=CachePolicy.STATIC_CONFIG,
        request=request,
        last_modified=time.time(),
        endpoint_name="config"
    )


def create_detection_response(content: Dict[str, Any], request: Request, 
                            detection_timestamp: Optional[float] = None) -> Union[Response, JSONResponse]:
    """Create cached response for detection endpoints"""
    endpoint_name = "detections" if "detections" in content else "detection"
    return CacheMiddleware.create_cached_response(
        content=content,
        policy=CachePolicy.DYNAMIC_DETECTION,
        request=request,
        last_modified=detection_timestamp or time.time(),
        endpoint_name=endpoint_name
    )


def create_health_response(content: Dict[str, Any], request: Request) -> Union[Response, JSONResponse]:
    """Create cached response for health endpoints"""
    return CacheMiddleware.create_cached_response(
        content=content,
        policy=CachePolicy.HEALTH_STATUS,
        request=request,
        last_modified=time.time(),
        endpoint_name="health"
    )


def create_image_response(content: bytes, request: Request, 
                         media_type: str = "image/jpeg", 
                         endpoint_name: str = "image") -> Response:
    """Create non-cached response for image endpoints"""
    start_time = time.time()
    response = Response(content=content, media_type=media_type)
    CacheHeaders.apply_headers(response, CachePolicy.IMAGE_DATA)
    
    # Track image endpoint performance (always cache miss for images)
    try:
        from .cache_metrics import CacheMetricsMiddleware
        response_time = time.time() - start_time
        CacheMetricsMiddleware.track_request(endpoint_name, 200, len(content), response_time)
    except ImportError:
        pass  # Metrics not available
    
    return response