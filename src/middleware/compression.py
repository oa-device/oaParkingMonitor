"""
Gzip compression middleware for oaParkingMonitor FastAPI application.

Optimized for edge device efficiency with selective compression of JSON responses
to achieve 60-70% network payload reduction while minimizing CPU overhead.
"""

import gzip
import io
import time
from typing import Set

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class GzipCompressionMiddleware(BaseHTTPMiddleware):
    """
    Lightweight gzip compression middleware optimized for edge devices.
    
    Features:
    - Selective compression based on content type and size
    - Configurable compression level (default: 6 for edge device efficiency)
    - Only compresses responses >1KB to avoid overhead
    - Handles Accept-Encoding header negotiation
    - Minimal performance impact on detection processing
    """
    
    def __init__(
        self,
        app: ASGIApp,
        minimum_size: int = 1024,  # Only compress responses >1KB
        compression_level: int = 6,  # Balanced compression for edge devices
        compressible_types: Set[str] = None
    ):
        """
        Initialize gzip compression middleware.
        
        Args:
            app: ASGI application
            minimum_size: Minimum response size to compress (bytes)
            compression_level: Gzip compression level (1-9, 6 is optimal for edge)
            compressible_types: Set of MIME types to compress
        """
        super().__init__(app)
        self.minimum_size = minimum_size
        self.compression_level = compression_level
        
        # Default compressible types optimized for API responses
        if compressible_types is None:
            self.compressible_types = {
                "application/json",
                "application/javascript", 
                "text/html",
                "text/css",
                "text/plain",
                "text/xml",
                "application/xml"
            }
        else:
            self.compressible_types = compressible_types
    
    def should_compress(self, request: Request, response: Response) -> bool:
        """
        Determine if response should be compressed.
        
        Args:
            request: Incoming HTTP request
            response: Outgoing HTTP response
            
        Returns:
            bool: True if response should be compressed
        """
        # Check if client accepts gzip encoding
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" not in accept_encoding.lower():
            return False
        
        # Check if response is already compressed
        if response.headers.get("content-encoding"):
            return False
        
        # Check content type
        content_type = response.headers.get("content-type", "")
        if not any(ct in content_type for ct in self.compressible_types):
            return False
        
        # Check if response has content-length header
        content_length = response.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) < self.minimum_size:
                    return False
            except (ValueError, TypeError):
                pass
        
        return True
    
    def compress_response(self, content: bytes) -> bytes:
        """
        Compress response content using gzip.
        
        Args:
            content: Response content to compress
            
        Returns:
            bytes: Compressed content
        """
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode='wb', compresslevel=self.compression_level) as gzf:
            gzf.write(content)
        return buffer.getvalue()
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request and apply compression if appropriate.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain
            
        Returns:
            Response: Processed response with optional compression
        """
        # Get response from downstream
        response = await call_next(request)
        
        # Skip compression for certain endpoints (images, already compressed)
        if not self.should_compress(request, response):
            return response
        
        # Read response body
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk
        
        # Check minimum size after reading body
        if len(response_body) < self.minimum_size:
            # Recreate response with original body
            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
        
        # Compress the response
        try:
            compressed_body = self.compress_response(response_body)
            
            # Only use compression if it actually reduces size
            if len(compressed_body) < len(response_body):
                # Update headers for compressed response
                headers = dict(response.headers)
                headers["content-encoding"] = "gzip"
                headers["content-length"] = str(len(compressed_body))
                headers["vary"] = "Accept-Encoding"
                
                return Response(
                    content=compressed_body,
                    status_code=response.status_code,
                    headers=headers,
                    media_type=response.media_type
                )
            else:
                # Return uncompressed if compression doesn't help
                return Response(
                    content=response_body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type
                )
                
        except Exception:
            # Return uncompressed response on compression error
            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )


class OptimizedGzipMiddleware(GzipCompressionMiddleware):
    """
    Optimized version specifically for oaParkingMonitor JSON endpoints.
    
    Targets high-payload endpoints:
    - /detections (batch data)
    - /health (JSON response)
    - /detection (JSON response) 
    - /config (configuration JSON)
    """
    
    def __init__(self, app: ASGIApp):
        """Initialize with edge device optimized settings."""
        super().__init__(
            app=app,
            minimum_size=512,  # Lower threshold for API responses
            compression_level=6,  # Optimal balance for edge devices
            compressible_types={
                "application/json",  # Primary target
                "text/html",         # Dashboard pages
                "text/plain"         # Text responses
            }
        )
        
        # High-priority endpoints for compression
        self.priority_endpoints = {
            "/detections",     # Largest payload - batch data
            "/config",         # Configuration JSON
            "/health",         # Health JSON
            "/detection",      # Detection JSON
            "/upload/status"   # Upload status JSON
        }
    
    def should_compress(self, request: Request, response: Response) -> bool:
        """Enhanced compression logic for API endpoints."""
        # Always attempt compression for priority endpoints
        request_path = request.url.path
        if any(endpoint in request_path for endpoint in self.priority_endpoints):
            accept_encoding = request.headers.get("accept-encoding", "")
            if "gzip" in accept_encoding.lower() and not response.headers.get("content-encoding"):
                return True
        
        # Use parent logic for other endpoints
        return super().should_compress(request, response)