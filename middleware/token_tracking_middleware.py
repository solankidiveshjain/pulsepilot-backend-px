"""
Middleware to automatically track token usage for all API operations
"""

import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from utils.token_tracker import TokenTracker
from utils.logging import get_logger

logger = get_logger(__name__)


class TokenTrackingMiddleware(BaseHTTPMiddleware):
    """Middleware to track token usage for billing"""
    
    def __init__(self, app):
        super().__init__(app)
        self.token_tracker = TokenTracker()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Track request start
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Track token usage for specific endpoints
        await self._track_endpoint_usage(request, response, time.time() - start_time)
        
        return response
    
    async def _track_endpoint_usage(self, request: Request, response: Response, duration: float):
        """Track token usage based on endpoint and request data"""
        
        try:
            # Extract team_id from path or headers
            team_id = request.path_params.get("team_id")
            if not team_id:
                return
            
            # Track based on endpoint patterns
            path = request.url.path
            method = request.method
            
            if method == "POST" and "/suggestions" in path:
                # Track suggestion generation requests
                await self.token_tracker.track_usage(
                    team_id=team_id,
                    usage_type="suggestion_request",
                    tokens_used=1,  # Base cost for request
                    metadata={
                        "endpoint": path,
                        "response_time": duration,
                        "status_code": response.status_code
                    }
                )
            
            elif method == "POST" and "/embeddings" in path:
                # Track embedding requests
                await self.token_tracker.track_usage(
                    team_id=team_id,
                    usage_type="embedding_request",
                    tokens_used=1,
                    metadata={
                        "endpoint": path,
                        "response_time": duration,
                        "status_code": response.status_code
                    }
                )
            
            elif method == "POST" and "/classify" in path:
                # Track classification requests
                await self.token_tracker.track_usage(
                    team_id=team_id,
                    usage_type="classification_request",
                    tokens_used=1,
                    metadata={
                        "endpoint": path,
                        "response_time": duration,
                        "status_code": response.status_code
                    }
                )
                
        except Exception as e:
            logger.error(f"Token tracking failed: {str(e)}")
