"""
Custom middleware for logging and error handling
"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from utils.logging import StructuredLogger
from utils.database import get_session
from models.database import ApiLog


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging API requests and responses"""
    
    def __init__(self, app):
        super().__init__(app)
        self.logger = StructuredLogger("api")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Start timer
        start_time = time.time()
        
        # Extract team_id from path if available
        team_id = request.path_params.get("team_id")
        
        # Log request
        self.logger.log_api_request(
            method=request.method,
            endpoint=request.url.path,
            team_id=team_id,
            request_id=request_id
        )
        
        # Process request
        response = await call_next(request)
        
        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Log response
        self.logger.log_api_response(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code,
            response_time_ms=response_time_ms,
            team_id=team_id,
            request_id=request_id
        )
        
        # Store API log in database (async)
        try:
            await self._store_api_log(
                team_id=team_id,
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                response_time_ms=response_time_ms
            )
        except Exception:
            # Don't fail the request if logging fails
            pass
        
        return response
    
    async def _store_api_log(
        self,
        team_id: str,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: int,
        error_message: str = None
    ):
        """Store API log in database"""
        async with get_session() as db:
            log = ApiLog(
                team_id=team_id,
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                response_time_ms=response_time_ms,
                error_message=error_message
            )
            db.add(log)
            await db.commit()


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for global error handling"""
    
    def __init__(self, app):
        super().__init__(app)
        self.logger = StructuredLogger("errors")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            # Log error
            self.logger.log_error(
                error=e,
                context={
                    "method": request.method,
                    "endpoint": request.url.path,
                    "request_id": getattr(request.state, "request_id", None)
                }
            )
            
            # Return error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "message": "An unexpected error occurred",
                    "request_id": getattr(request.state, "request_id", None)
                }
            )
