"""
Authentication middleware for oaParkingMonitor
Simple API key validation for POST endpoints
"""

import os
import logging
from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from ..models.edge import ErrorResponse

logger = logging.getLogger(__name__)

# Security scheme for OpenAPI documentation
security = HTTPBearer(auto_error=False)

# Environment variable for API key
EDGE_API_KEY = os.getenv("EDGE_API_KEY", "development-key-change-in-production")


async def validate_api_key(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = None) -> bool:
    """
    Validate API key from Authorization header

    Args:
        request: FastAPI request object
        credentials: HTTP Bearer credentials (optional)

    Returns:
        True if valid, raises HTTPException if invalid
    """
    try:
        # Extract token from Bearer header
        if credentials and credentials.scheme == "Bearer":
            provided_key = credentials.credentials
        else:
            # Also check for x-api-key header as fallback
            provided_key = request.headers.get("x-api-key")

        if not provided_key:
            logger.warning(f"API key missing for {request.method} {request.url.path}")
            raise HTTPException(
                status_code=401,
                detail=ErrorResponse(
                    error="Authentication Required",
                    message="API key required for this operation"
                ).model_dump()
            )

        if provided_key != EDGE_API_KEY:
            logger.warning(f"Invalid API key for {request.method} {request.url.path}")
            raise HTTPException(
                status_code=403,
                detail=ErrorResponse(
                    error="Authentication Failed",
                    message="Invalid API key provided"
                ).model_dump()
            )

        logger.debug(f"API key validated for {request.method} {request.url.path}")
        return True

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API key validation error: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Authentication Error",
                message="Failed to validate API key"
            ).model_dump()
        )


def require_api_key(func):
    """
    Decorator to require API key authentication for endpoint

    Usage:
        @require_api_key
        async def protected_endpoint():
            pass
    """
    async def wrapper(*args, **kwargs):
        # Find request object in arguments
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break

        if request is None:
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(
                    error="Internal Error",
                    message="Request object not found"
                ).model_dump()
            )

        # Validate API key
        await validate_api_key(request)

        # Call original function
        return await func(*args, **kwargs)

    return wrapper