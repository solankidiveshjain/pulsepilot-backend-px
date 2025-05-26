"""
AI-powered reply suggestions endpoints
"""

from uuid import UUID
from typing import List
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


@router.get("/{team_id}/comments/{comment_id}/suggestions")
async def get_suggestions(
    team_id: UUID,
    comment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_team: Team = Depends(get_current_team),
    llm_service: LLMService = Depends(),
    vector_service: VectorService = Depends(),
    token_tracker: TokenTracker = Depends()
) -> List[SuggestionResponse]:
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
        return [
            SuggestionResponse(
                suggestion_id=suggestion.suggestion_id,
                suggested_reply=suggestion.suggested_reply,
                score=suggestion.score or 0.0,
                confidence="high" if (suggestion.score or 0) > 0.8 else "medium" if (suggestion.score or 0) > 0.6 else "low"
            )
            for suggestion in existing_suggestions
        ]
    
    try:
        # Generate embeddings if not exists
        if not comment.embedding:
            embedding = await vector_service.generate_embedding(comment.message or "")
            comment.embedding = embedding
            await db.commit()
        
        # Find similar comments and replies for context
        similar_comments = await vector_service.find_similar_comments(
            comment.embedding,
            team_id,
            limit=5
        )
        
        # Generate suggestions using LLM
        suggestions_data = await llm_service.generate_reply_suggestions(
            comment=comment,
            similar_comments=similar_comments,
            team_id=team_id
        )
        
        # Track token usage
        await token_tracker.track_usage(
            team_id=team_id,
            usage_type="generation",
            tokens_used=suggestions_data.get("tokens_used", 0),
            cost=suggestions_data.get("cost", 0.0)
        )
        
        # Save suggestions to database
        suggestions = []
        for suggestion_text, score in suggestions_data["suggestions"]:
            suggestion = AiSuggestion(
                comment_id=comment_id,
                suggested_reply=suggestion_text,
                score=score
            )
            db.add(suggestion)
            suggestions.append(suggestion)
        
        await db.commit()
        
        # Refresh to get IDs
        for suggestion in suggestions:
            await db.refresh(suggestion)
        
        return [
            SuggestionResponse(
                suggestion_id=suggestion.suggestion_id,
                suggested_reply=suggestion.suggested_reply,
                score=suggestion.score or 0.0,
                confidence="high" if (suggestion.score or 0) > 0.8 else "medium" if (suggestion.score or 0) > 0.6 else "low"
            )
            for suggestion in suggestions
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate suggestions: {str(e)}"
        )
