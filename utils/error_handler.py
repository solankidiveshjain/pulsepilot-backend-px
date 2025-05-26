"""
Global error handler middleware
"""

import traceback
from typing import Union
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

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

logger = get_logger(__name__)


class GlobalExceptionHandler(BaseHTTPMiddleware):
    """Global exception handling middleware"""
    
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
        """Handle and log exceptions"""
        request_id = getattr(request.state, "request_id", "unknown")
        
        # Log the error with context
        logger.error(
            f"Unhandled exception in {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "traceback": traceback.format_exc()
            }
        )
        
        # Handle specific exception types
        if isinstance(exc, ConfigurationError):
            return self._create_error_response(
                500, "Configuration error", {"request_id": request_id}
            )
        elif isinstance(exc, PlatformError):
            return self._create_error_response(
                400, f"Platform error: {exc.message}", 
                {"request_id": request_id, **exc.details}
            )
        elif isinstance(exc, AuthenticationError):
            return self._create_error_response(
                401, "Authentication failed", {"request_id": request_id}
            )
        elif isinstance(exc, ValidationError):
            return self._create_error_response(
                422, f"Validation error: {exc.message}",
                {"request_id": request_id, **exc.details}
            )
        elif isinstance(exc, ExternalServiceError):
            return self._create_error_response(
                502, f"External service error: {exc.message}",
                {"request_id": request_id, **exc.details}
            )
        elif isinstance(exc, DatabaseError):
            return self._create_error_response(
                500, "Database error occurred",
                {"request_id": request_id}
            )
        else:
            # Generic error for unexpected exceptions
            return self._create_error_response(
                500, "Internal server error",
                {"request_id": request_id}
            )
    
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
                "status_code": status_code
            }
        )
