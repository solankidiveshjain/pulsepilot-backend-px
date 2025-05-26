"""
API v1 module initialization
"""

from fastapi import APIRouter
from .platforms import router as platforms_router
from .comments import router as comments_router
from .replies import router as replies_router
from .suggestions import router as suggestions_router
from .webhooks import router as webhooks_router
from .analytics import router as analytics_router
from .teams import router as teams_router

# Create v1 API router
v1_router = APIRouter(prefix="/v1")

# Include all sub-routers
v1_router.include_router(platforms_router, prefix="/platforms", tags=["Platforms"])
v1_router.include_router(comments_router, prefix="/comments", tags=["Comments"])
v1_router.include_router(replies_router, prefix="/replies", tags=["Replies"])
v1_router.include_router(suggestions_router, prefix="/suggestions", tags=["Suggestions"])
v1_router.include_router(webhooks_router, prefix="/webhooks", tags=["Webhooks"])
v1_router.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])
v1_router.include_router(teams_router, prefix="/teams", tags=["Teams"])
