"""
PulsePilot Backend API
FastAPI application for AI-powered social media comment management
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
import uvicorn

from api.social import router as social_router
from api.suggestions import router as suggestions_router
from api.replies import router as replies_router
from api.webhooks import router as webhooks_router
from api.embeddings import router as embeddings_router
from api.classification import router as classification_router
from api.billing import router as billing_router
from api.users import router as users_router
from utils.database import init_db
from utils.logging import setup_logging, get_logger
from utils.middleware import LoggingMiddleware, ErrorHandlingMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    setup_logging()
    
    # Initialize database with Supabase
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        # Don't fail startup for database issues in production
        if os.getenv("ENVIRONMENT") != "production":
            raise
    
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

# Add middleware
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

app.add_middleware(LoggingMiddleware)
app.add_middleware(ErrorHandlingMiddleware)

# Add Prometheus metrics
instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app)

# Include routers
app.include_router(social_router, prefix="/teams", tags=["Social Connections"])
app.include_router(suggestions_router, prefix="/teams", tags=["Suggestions"])
app.include_router(replies_router, prefix="/teams", tags=["Replies"])
app.include_router(webhooks_router, prefix="/webhooks", tags=["Webhooks"])
app.include_router(embeddings_router, prefix="/api/embeddings", tags=["Embeddings"])
app.include_router(classification_router, prefix="/api", tags=["Classification"])
app.include_router(billing_router, prefix="/api/tokens", tags=["Billing"])
app.include_router(users_router, prefix="/api", tags=["Users"])


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "pulsepilot-backend"}


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "PulsePilot Backend API", "version": "1.0.0"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("ENVIRONMENT") == "development"
    )
