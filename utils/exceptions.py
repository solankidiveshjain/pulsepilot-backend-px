"""
Centralized exception handling and custom exceptions
"""

from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class PulsePilotException(Exception):
    """Base exception for PulsePilot application"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ConfigurationError(PulsePilotException):
    """Configuration or setup error"""
    pass


class PlatformError(PulsePilotException):
    """Platform-specific error"""
    pass


class AuthenticationError(PulsePilotException):
    """Authentication/authorization error"""
    pass


class ValidationError(PulsePilotException):
    """Data validation error"""
    pass


class ExternalServiceError(PulsePilotException):
    """External service integration error"""
    pass


class DatabaseError(PulsePilotException):
    """Database operation error"""
    pass


def create_http_exception(
    status_code: int,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> HTTPException:
    """Create standardized HTTP exception"""
    return HTTPException(
        status_code=status_code,
        detail={
            "error": message,
            "details": details or {},
            "status_code": status_code
        }
    )


def handle_platform_error(e: Exception, platform: str) -> HTTPException:
    """Handle platform-specific errors"""
    if isinstance(e, PlatformError):
        return create_http_exception(
            status.HTTP_400_BAD_REQUEST,
            f"Platform error: {e.message}",
            {"platform": platform, **e.details}
        )
    elif isinstance(e, ValueError):
        return create_http_exception(
            status.HTTP_400_BAD_REQUEST,
            f"Invalid {platform} configuration: {str(e)}",
            {"platform": platform}
        )
    else:
        return create_http_exception(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Unexpected error with {platform} integration",
            {"platform": platform}
        )


def handle_database_error(e: Exception) -> HTTPException:
    """Handle database errors"""
    if isinstance(e, DatabaseError):
        return create_http_exception(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Database operation failed",
            e.details
        )
    else:
        return create_http_exception(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Database error occurred",
            {}
        )


def handle_external_service_error(e: Exception, service: str) -> HTTPException:
    """Handle external service errors"""
    if isinstance(e, ExternalServiceError):
        return create_http_exception(
            status.HTTP_502_BAD_GATEWAY,
            f"External service error: {e.message}",
            {"service": service, **e.details}
        )
    else:
        return create_http_exception(
            status.HTTP_502_BAD_GATEWAY,
            f"Failed to communicate with {service}",
            {"service": service}
        )
