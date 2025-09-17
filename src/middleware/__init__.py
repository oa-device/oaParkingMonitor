"""
Middleware package for oaParkingMonitor
"""

from .compression import GzipCompressionMiddleware, OptimizedGzipMiddleware

__all__ = [
    "GzipCompressionMiddleware",
    "OptimizedGzipMiddleware"
]