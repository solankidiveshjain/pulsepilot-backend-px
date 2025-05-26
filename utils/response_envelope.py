"""
Global response envelope formatting
"""

from typing import Any, Optional, Dict
from pydantic import BaseModel
from fastapi import Response
from fastapi.responses import JSONResponse


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
