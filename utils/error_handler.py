"""
Global error handler middleware
"""

import traceback
import sentry_sdk
from typing import Union
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime

from utils.exceptions import (
    PulsePilotException, 
    ConfigurationError,
    PlatformError,
    AuthenticationError,
    ValidationError,
    ExternalServiceError,
    DatabaseError,
    create_http_exception
)
from utils.logging import get_logger
from utils.monitoring import track_request_metrics

logger = get_logger(__name__)


class GlobalExceptionHandler(BaseHTTPMiddleware):
    """Global exception handling middleware with Sentry integration"""
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as e:
            return await self._handle_exception(request, e)
    
    async def _handle_exception(self, request: Request, exc: Exception) -> JSONResponse:
        """Handle and log exceptions with Sentry integration"""
        request_id = getattr(request.state, "request_id", "unknown")
        
        # Capture exception in Sentry
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("request_id", request_id)
            scope.set_context("request", {
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers)
            })
            sentry_sdk.capture_exception(exc)
        
        # Log the error with context
        logger.error(
            f"Unhandled exception in {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "traceback": traceback.format_exc(),
                "user_agent": request.headers.get("user-agent"),
                "ip_address": request.client.host if request.client else None
            }
        )
        
        # Handle specific exception types
        if isinstance(exc, ConfigurationError):
            status_code = 500
            message = "Configuration error"
        elif isinstance(exc, PlatformError):
            status_code = 400
            message = f"Platform error: {exc.message}"
        elif isinstance(exc, AuthenticationError):
            status_code = 401
            message = "Authentication failed"
        elif isinstance(exc, ValidationError):
            status_code = 422
            message = f"Validation error: {exc.message}"
        elif isinstance(exc, ExternalServiceError):
            status_code = 502
            message = f"External service error: {exc.message}"
        elif isinstance(exc, DatabaseError):
            status_code = 500
            message = "Database error occurred"
        else:
            status_code = 500
            message = "Internal server error"
        
        # Track error metrics
        track_request_metrics(
            method=request.method,
            endpoint=request.url.path,
            status_code=status_code,
            duration=0  # Duration not available in error case
        )
        
        return self._create_error_response(status_code, message, {"request_id": request_id})
    
    def _create_error_response(
        self, 
        status_code: int, 
        message: str, 
        details: dict
    ) -> JSONResponse:
        """Create standardized error response"""
        return JSONResponse(
            status_code=status_code,
            content={
                "error": message,
                "details": details,
                "status_code": status_code,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
