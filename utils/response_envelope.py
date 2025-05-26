"""
Global response envelope formatting
"""

from typing import Any, Optional, Dict
from pydantic import BaseModel
from fastapi import Response
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException


class ApiResponse(BaseModel):
    """Standard API response envelope"""
    success: bool
    data: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None


class ResponseFormatter:
    """Global response formatter"""
    
    @staticmethod
    def success(data: Any = None, meta: Dict[str, Any] = None) -> ApiResponse:
        """Format successful response"""
        return ApiResponse(
            success=True,
            data=data,
            meta=meta
        )
    
    @staticmethod
    def error(
        message: str,
        code: str = "UNKNOWN_ERROR",
        details: Dict[str, Any] = None,
        status_code: int = 500
    ) -> JSONResponse:
        """Format error response"""
        error_data = {
            "code": code,
            "message": message,
            "details": details or {}
        }
        
        response = ApiResponse(
            success=False,
            error=error_data
        )
        
        return JSONResponse(
            status_code=status_code,
            content=response.dict()
        )


def format_success_response(data: Any = None, meta: Dict[str, Any] = None) -> Dict[str, Any]:
    """Helper function to format success responses"""
    return ResponseFormatter.success(data, meta).dict()


# Alias for Pydantic response model
ResponseEnvelope = ApiResponse


def success_response(data: Any = None, meta: Dict[str, Any] = None) -> ResponseEnvelope:
    """Helper to create a success ResponseEnvelope"""
    return ResponseFormatter.success(data, meta)


def error_response(
    error_code: Any,
    message: str = None,
    details: Dict[str, Any] = None
) -> ResponseEnvelope:
    """Helper to create an error ResponseEnvelope"""
    # Determine code and message
    code = getattr(error_code, 'code', None) or str(error_code)
    msg = message if message is not None else getattr(error_code, 'message', None) or ''
    # Build error body
    error_body: Dict[str, Any] = {
        'code': code,
        'message': msg
    }
    if details is not None:
        error_body['details'] = details

    return ApiResponse(
        success=False,
        data=None,
        error=error_body
    )


def handle_api_exception(
    exc: Exception,
    debug: bool = False
) -> ResponseEnvelope:
    """Convert exceptions into a standardized ResponseEnvelope"""
    if isinstance(exc, HTTPException):
        code = f'HTTP_{exc.status_code}'
        msg = exc.detail
        return ApiResponse(
            success=False,
            data=None,
            error={'code': code, 'message': msg}
        )
    else:
        # Generic errors
        if debug:
            msg = str(exc)
        else:
            msg = 'Internal server error'
        return ApiResponse(
            success=False,
            data=None,
            error={'code': 'INTERNAL_ERROR', 'message': msg}
        )
