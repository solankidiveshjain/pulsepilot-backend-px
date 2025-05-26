"""
AI-powered reply suggestions endpoints
"""

from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from models.database import Comment, Team, AiSuggestion
from utils.database import get_db
from utils.auth import get_current_team
from services.llm_service import LLMService
from services.vector_service import VectorService
from utils.token_tracker import TokenTracker


router = APIRouter()


class SuggestionResponse(BaseModel):
    suggestion_id: UUID
    suggested_reply: str
    score: float
    confidence: str


class SuggestionsResponse(BaseModel):
    comment_id: UUID
    suggestions: List[SuggestionResponse]
    context_used: str
    rag_contexts_count: int
    processing_time_ms: int
    job_id: Optional[str] = None
    status: Optional[str] = None


class SuggestionRequest(BaseModel):
    pass


@router.get("/{team_id}/comments/{comment_id}/suggestions")
async def get_suggestions(
    team_id: UUID,
    comment_id: UUID,
    request: SuggestionRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    current_team: Team = Depends(get_current_team)
) -> SuggestionsResponse:
    """Get AI-powered reply suggestions for a comment"""
    
    # Verify team access
    if current_team.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to team"
        )
    
    # Find comment
    stmt = select(Comment).where(
        Comment.comment_id == comment_id,
        Comment.team_id == team_id
    )
    result = await db.execute(stmt)
    comment = result.scalar_one_or_none()
    
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found"
        )
    
    # Check if suggestions already exist
    stmt = select(AiSuggestion).where(
        AiSuggestion.comment_id == comment_id
    )
    result = await db.execute(stmt)
    existing_suggestions = result.scalars().all()
    
    if existing_suggestions:
        return SuggestionsResponse(
            comment_id=comment_id,
            suggestions=[
                SuggestionResponse(
                    suggestion_id=suggestion.suggestion_id,
                    suggested_reply=suggestion.suggested_reply,
                    score=suggestion.score or 0.0,
                    confidence="high" if (suggestion.score or 0) > 0.8 else "medium" if (suggestion.score or 0) > 0.6 else "low"
                )
                for suggestion in existing_suggestions
            ],
            context_used="Previously generated",
            rag_contexts_count=0,
            processing_time_ms=0
        )
    
    # Queue suggestion generation task
    from utils.task_queue import task_queue
    job_id = await task_queue.enqueue_suggestion_generation(comment_id, team_id)
    
    return SuggestionsResponse(
        comment_id=comment_id,
        suggestions=[],
        context_used="Queued for processing",
        rag_contexts_count=0,
        processing_time_ms=0,
        job_id=job_id,
        status="processing"
    )
