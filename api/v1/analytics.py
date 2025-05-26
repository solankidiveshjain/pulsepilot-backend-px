"""
RESTful analytics endpoints for token usage and performance metrics
"""

from uuid import UUID
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Team
from utils.database import get_db
from utils.auth import get_current_team
from utils.token_tracker import TokenTracker
from schemas.responses import TokenQuotaResponse

router = APIRouter()


@router.get("/teams/{team_id}/token-usage", response_model=TokenQuotaResponse)
async def get_team_token_usage(
    team_id: UUID,
    current_team: Team = Depends(get_current_team)
) -> TokenQuotaResponse:
    """Get current token usage and quota status for team"""
    
    if current_team.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to team"
        )
    
    token_tracker = TokenTracker()
    quota_status = await token_tracker.check_quota(team_id)
    
    return TokenQuotaResponse(
        team_id=team_id,
        quota_limit=quota_status["quota_limit"],
        tokens_used=quota_status["tokens_used"],
        tokens_remaining=quota_status["tokens_remaining"],
        quota_exceeded=quota_status["quota_exceeded"],
        usage_breakdown=quota_status["usage_breakdown"]
    )


@router.get("/teams/{team_id}/usage-analytics")
async def get_usage_analytics(
    team_id: UUID,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_team: Team = Depends(get_current_team)
) -> Dict[str, Any]:
    """Get detailed usage analytics for team"""
    
    if current_team.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to team"
        )
    
    token_tracker = TokenTracker()
    analytics = await token_tracker.get_usage_analytics(team_id, days)
    
    return analytics


@router.get("/teams/{team_id}/performance-metrics")
async def get_performance_metrics(
    team_id: UUID,
    current_team: Team = Depends(get_current_team)
) -> Dict[str, Any]:
    """Get performance metrics for team operations"""
    
    if current_team.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to team"
        )
    
    # Get performance metrics from database
    from sqlalchemy import select, func
    from models.database import Comment, Reply, AiSuggestion
    
    async with get_session() as db:
        # Comment processing metrics
        comment_stats = await db.execute(
            select(
                func.count(Comment.comment_id).label('total_comments'),
                func.count(Comment.embedding).label('comments_with_embeddings'),
                func.avg(func.extract('epoch', Comment.updated_at - Comment.created_at)).label('avg_processing_time')
            ).where(Comment.team_id == team_id)
        )
        comment_row = comment_stats.first()
        
        # Reply metrics
        reply_stats = await db.execute(
            select(
                func.count(Reply.reply_id).label('total_replies'),
                func.avg(func.length(Reply.message)).label('avg_reply_length')
            ).join(Comment).where(Comment.team_id == team_id)
        )
        reply_row = reply_stats.first()
        
        # AI suggestion metrics
        suggestion_stats = await db.execute(
            select(
                func.count(AiSuggestion.suggestion_id).label('total_suggestions'),
                func.avg(AiSuggestion.score).label('avg_suggestion_score')
            ).join(Comment).where(Comment.team_id == team_id)
        )
        suggestion_row = suggestion_stats.first()
        
        return {
            "team_id": str(team_id),
            "comments": {
                "total": comment_row.total_comments or 0,
                "with_embeddings": comment_row.comments_with_embeddings or 0,
                "avg_processing_time_seconds": float(comment_row.avg_processing_time or 0)
            },
            "replies": {
                "total": reply_row.total_replies or 0,
                "avg_length": float(reply_row.avg_reply_length or 0)
            },
            "suggestions": {
                "total": suggestion_row.total_suggestions or 0,
                "avg_score": float(suggestion_row.avg_suggestion_score or 0)
            }
        }
