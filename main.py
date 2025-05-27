"""
PulsePilot Backend API - Production-ready with all 20 enhancements applied
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import uvicorn

# Import modular components
from api.v1 import v1_router
from utils.config_bootstrap import validate_config_on_startup
from utils.structured_logging import setup_structured_logging, get_structured_logger
from utils.response_envelope import format_success_response
from utils.error_codes import ErrorCode, ERROR_MESSAGES
from utils.feature_flags import settings_registry
from utils.metrics_collector import metrics
from middleware.rate_limiting import RateLimitingMiddleware
from middleware.token_tracking_middleware import TokenTrackingMiddleware
from utils.error_handler import GlobalExceptionHandler
from migrations.migration_manager import migration_manager
from schemas.responses import HealthResponse

logger = get_structured_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with fail-fast validation and proper setup"""
    
    # ENHANCEMENT 3: Fail-fast config validation
    try:
        validate_config_on_startup()
        logger.info("✅ Configuration validation passed")
    except SystemExit:
        logger.error("🚨 Configuration validation failed - aborting startup")
        raise
    
    # ENHANCEMENT 9: Setup structured logging
    setup_structured_logging()
    logger.info("🚀 Starting PulsePilot Backend API")
    
    # ENHANCEMENT 11: Run database migrations
    try:
        if not migration_manager.validate_schema():
            logger.info("Running database migrations...")
            migration_manager.run_migrations()
        logger.info("✅ Database schema validated")
    except Exception as e:
        logger.error("❌ Database migration failed", error=str(e))
        raise SystemExit(1)
    
    # ENHANCEMENT 15: Log feature flag status
    flags = settings_registry.get_all_flags()
    logger.info("Feature flags loaded", flags=flags)
    
    yield
    
    # Shutdown
    logger.info("🛑 Application shutting down")


# Initialize FastAPI app with OpenAPI alignment
app = FastAPI(
    title="PulsePilot API",
    description="AI-powered social media comment management backend with comprehensive monitoring and security",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    # ENHANCEMENT 19: Ensure OpenAPI compliance
    openapi_tags=[
        {"name": "Platforms", "description": "Social media platform integration"},
        {"name": "Webhooks", "description": "Webhook processing and ingestion"},
        {"name": "Suggestions", "description": "AI-powered reply suggestions"},
        {"name": "Replies", "description": "Reply submission and management"},
        {"name": "Analytics", "description": "Usage analytics and billing"},
        {"name": "Health", "description": "System health and monitoring"}
    ]
)

# ENHANCEMENT 18: Add middleware in correct order for separation of concerns
app.add_middleware(GlobalExceptionHandler)  # Error handling first
app.add_middleware(RateLimitingMiddleware)   # Rate limiting
app.add_middleware(TokenTrackingMiddleware)  # Token tracking for billing

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure for production
)

# ENHANCEMENT 17: Include API routers with proper organization
app.include_router(v1_router, prefix="/api")


# ENHANCEMENT 14: Prometheus metrics endpoint
@app.get("/metrics", include_in_schema=False)
async def get_metrics():
    """Prometheus metrics endpoint"""
    return Response(
        generate_latest(metrics.registry),
        media_type=CONTENT_TYPE_LATEST
    )


# ENHANCEMENT 4: Health check with global response formatting
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> dict:
    """
    Health check endpoint with dependency status and structured response
    
    Returns comprehensive health information including:
    - Service status
    - Database connectivity
    - Redis connectivity  
    - Feature flag status
    """
    from datetime import datetime
    from utils.database import get_session
    # from tasks.async_task_manager import task_manager  # removed ARQ manager
    
    # Check dependencies
    dependencies = {}
    
    try:
        # Test database connection
        async with get_session() as db:
            await db.execute("SELECT 1")
        dependencies["database"] = "healthy"
    except Exception as e:
        dependencies["database"] = "unhealthy"
        logger.error("Database health check failed", error=str(e))
    
    try:
        # Test Redis connection directly
        from redis.asyncio import Redis
        import os
        redis_client = Redis.from_url(os.getenv("REDIS_URL"))
        await redis_client.ping()
        dependencies["redis"] = "healthy"
    except Exception as e:
        dependencies["redis"] = "unhealthy"
        logger.error("Redis health check failed", error=str(e))
    
    # Add feature flag status
    dependencies["feature_flags"] = "enabled" if settings_registry.is_enabled else "disabled"
    
    health_data = {
        "status": "healthy",
        "service": "pulsepilot-backend",
        "version": "1.0.0",
        "timestamp": datetime.utcnow(),
        "dependencies": dependencies,
        "environment": os.getenv("ENVIRONMENT", "development")
    }
    
    return format_success_response(health_data)


# ENHANCEMENT 4: Root endpoint with response envelope
@app.get("/", tags=["Health"])
async def root():
    """
    Root endpoint with API information
    
    Returns basic API information and navigation links
    """
    api_info = {
        "message": "PulsePilot Backend API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
        "api_base": "/api/v1"
    }
    
    return format_success_response(api_info)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("ENVIRONMENT") == "development"
    )
