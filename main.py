"""
PulsePilot Backend API - Refactored with modular routing and comprehensive error handling
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
import uvicorn

# Import the new modular API
from api.v1 import v1_router
from utils.database import init_db
from utils.config import validate_config_on_startup
from utils.logging import setup_logging, get_logger
from utils.middleware import LoggingMiddleware
from utils.error_handler import GlobalExceptionHandler
from utils.monitoring import init_sentry
from schemas.responses import HealthResponse

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with fail-fast configuration"""
    # FAIL-FAST: Validate configuration before any other startup
    try:
        config = validate_config_on_startup()
    except Exception as e:
        logger.error(f"STARTUP FAILED: {str(e)}")
        raise SystemExit(1)
    
    # Continue with rest of startup...
    try:
        setup_logging()
        logger.info("Starting PulsePilot Backend API")
        
        # Initialize Sentry for error tracking
        init_sentry()
        
        # Initialize database
        await init_db()
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Application startup failed: {str(e)}")
        raise SystemExit(1)
    
    yield
    
    # Shutdown
    logger.info("Application shutting down")


# Initialize FastAPI app
app = FastAPI(
    title="PulsePilot API",
    description="AI-powered social media comment management backend",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add middleware in correct order
app.add_middleware(GlobalExceptionHandler)
app.add_middleware(LoggingMiddleware)

# Add token tracking middleware
from middleware.token_tracking_middleware import TokenTrackingMiddleware
app.add_middleware(TokenTrackingMiddleware)

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

# Add Prometheus metrics
instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app)

# Include API routers
app.include_router(v1_router, prefix="/api")


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint with dependency status"""
    from datetime import datetime
    
    # Check dependencies
    dependencies = {}
    
    try:
        # Test database connection
        from utils.database import get_session
        async with get_session() as db:
            await db.execute("SELECT 1")
        dependencies["database"] = "healthy"
    except Exception:
        dependencies["database"] = "unhealthy"
    
    try:
        # Test Redis connection
        from utils.task_queue import task_queue
        await task_queue.get_pool()
        dependencies["redis"] = "healthy"
    except Exception:
        dependencies["redis"] = "unhealthy"
    
    return HealthResponse(
        status="healthy",
        service="pulsepilot-backend",
        version="1.0.0",
        timestamp=datetime.utcnow(),
        dependencies=dependencies
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "PulsePilot Backend API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("ENVIRONMENT") == "development"
    )
