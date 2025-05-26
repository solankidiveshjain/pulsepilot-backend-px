"""
Token usage tracking and billing endpoints
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from models.database import TokenUsage, Team
from utils.database import get_db
from utils.auth import get_current_team
from utils.token_tracker import TokenTracker


router = APIRouter()


class TokenTrackingRequest(BaseModel):
    team_id: UUID
    usage_type: str  # embedding, classification, generation
    tokens_used: int
    cost: float


class TokenTrackingResponse(BaseModel):
    usage_id: int
    team_id: UUID
    tokens_used: int
    cost: float
    status: str


@router.post("/track")
async def track_token_usage(
    request: TokenTrackingRequest,
    db: AsyncSession = Depends(get_db),
    token_tracker: TokenTracker = Depends()
) -> TokenTrackingResponse:
    """Track token usage for billing"""
    
    # Validate usage type
    valid_types = ["embedding", "classification", "generation"]
    if request.usage_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid usage_type. Must be one of: {valid_types}"
        )
    
    try:
        # Track usage
        usage_record = await token_tracker.track_usage(
            team_id=request.team_id,
            usage_type=request.usage_type,
            tokens_used=request.tokens_used,
            cost=request.cost
        )
        
        return TokenTrackingResponse(
            usage_id=usage_record.usage_id,
            team_id=usage_record.team_id,
            tokens_used=usage_record.tokens_used,
            cost=usage_record.cost or 0.0,
            status="tracked"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to track token usage: {str(e)}"
        )
