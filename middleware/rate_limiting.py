"""
API rate limiting middleware for team and user quotas
"""

import time
from typing import Dict, Optional, Tuple
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis

from utils.config import get_config
from utils.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)
config = get_config()


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware with Redis backend"""
    
    def __init__(self, app):
        """
        Initialize rate limiting middleware
        
        Args:
            app: FastAPI application instance
        """
        super().__init__(app)
        self.redis_client: Optional[redis.Redis] = None
        
        # Rate limit configurations per endpoint type
        self.rate_limits = {
            # AI/LLM endpoints (expensive)
            "/api/v1/suggestions": {"requests": 10, "window": 60},  # 10 per minute
            "/api/v1/replies": {"requests": 50, "window": 60},      # 50 per minute
            
            # Platform endpoints
            "/api/v1/platforms": {"requests": 100, "window": 60},   # 100 per minute
            
            # Webhook endpoints (high volume)
            "/api/v1/webhooks": {"requests": 1000, "window": 60},   # 1000 per minute
            
            # Analytics endpoints
            "/api/v1/analytics": {"requests": 30, "window": 60},    # 30 per minute
        }
    
    async def get_redis_client(self) -> redis.Redis:
        """
        Get Redis client for rate limiting storage
        
        Returns:
            Redis client instance
        """
        if not self.redis_client:
            self.redis_client = redis.from_url(config.redis_url)
        return self.redis_client
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request with rate limiting
        
        Args:
            request: HTTP request
            call_next: Next middleware in chain
            
        Returns:
            HTTP response
        """
        # Skip rate limiting for health checks and docs
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
        
        # Extract team ID from request
        team_id = self._extract_team_id(request)
        if not team_id:
            # Skip rate limiting if no team context
            return await call_next(request)
        
        # Check rate limits
        endpoint_pattern = self._get_endpoint_pattern(request.url.path)
        if endpoint_pattern and endpoint_pattern in self.rate_limits:
            is_allowed, remaining, reset_time = await self._check_rate_limit(
                team_id, endpoint_pattern, self.rate_limits[endpoint_pattern]
            )
            
            if not is_allowed:
                logger.warning("Rate limit exceeded",
                             team_id=team_id,
                             endpoint=endpoint_pattern,
                             remaining=remaining)
                
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "RATE_LIMIT_EXCEEDED",
                        "message": "Rate limit exceeded for this endpoint",
                        "retry_after": reset_time
                    }
                )
            
            # Add rate limit headers to response
            response = await call_next(request)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(reset_time)
            
            return response
        
        return await call_next(request)
    
    async def _check_rate_limit(
        self,
        team_id: str,
        endpoint: str,
        limit_config: Dict[str, int]
    ) -> Tuple[bool, int, int]:
        """
        Check if request is within rate limits
        
        Args:
            team_id: Team identifier
            endpoint: Endpoint pattern
            limit_config: Rate limit configuration
            
        Returns:
            Tuple of (is_allowed, remaining_requests, reset_timestamp)
        """
        redis_client = await self.get_redis_client()
        
        key = f"rate_limit:{team_id}:{endpoint}"
        window = limit_config["window"]
        max_requests = limit_config["requests"]
        
        current_time = int(time.time())
        window_start = current_time - (current_time % window)
        
        try:
            # Use Redis pipeline for atomic operations
            pipe = redis_client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start - window)
            pipe.zcard(key)
            pipe.zadd(key, {str(current_time): current_time})
            pipe.expire(key, window * 2)
            
            results = await pipe.execute()
            current_requests = results[1]
            
            remaining = max(0, max_requests - current_requests)
            reset_time = window_start + window
            
            is_allowed = current_requests < max_requests
            
            return is_allowed, remaining, reset_time
            
        except Exception as e:
            logger.error("Rate limiting check failed", error=str(e))
            # Fail open - allow request if Redis is down
            return True, max_requests, current_time + window
    
    def _extract_team_id(self, request: Request) -> Optional[str]:
        """
        Extract team ID from request path or headers
        
        Args:
            request: HTTP request
            
        Returns:
            Team ID if found
        """
        # Try to extract from path parameters
        if "team_id" in request.path_params:
            return request.path_params["team_id"]
        
        # Try to extract from headers (for webhook endpoints)
        return request.headers.get("X-Team-ID")
    
    def _get_endpoint_pattern(self, path: str) -> Optional[str]:
        """
        Get endpoint pattern for rate limiting
        
        Args:
            path: Request path
            
        Returns:
            Endpoint pattern if matches configured patterns
        """
        for pattern in self.rate_limits.keys():
            if path.startswith(pattern):
                return pattern
        return None
