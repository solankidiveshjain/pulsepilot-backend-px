"""
RESTful comment management endpoints
"""

from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from models.database import Comment, Team
from utils.database import get_db
from utils.auth import get_current_team
from schemas.responses import CommentResponse, CommentListResponse

router = APIRouter()


class CommentResponse(BaseModel):
    """Comment response model"""
    comment_id: UUID
    platform: str
    author: Optional[str]
    message: Optional[str]
    created_at: datetime
    has_embedding: bool
    classification: Optional[Dict[str, Any]]
    reply_count: int


class CommentListResponse(BaseModel):
    """Comment list response model"""
    comments: List[CommentResponse]
    total: int
    page: int
    per_page: int
    has_next: bool


@router.get("/teams/{team_id}/comments", response_model=CommentListResponse)
async def list_team_comments(
    team_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    has_replies: Optional[bool] = Query(None, description="Filter by reply status"),
    current_team: Team = Depends(get_current_team),
    db: AsyncSession = Depends(get_db)
) -> CommentListResponse:
    """List comments for team with filtering and pagination"""
    
    if current_team.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to team"
        )
    
    # Build query with filters
    query = select(Comment).where(Comment.team_id == team_id)
    
    if platform:
        query = query.where(Comment.platform == platform)
    
    # Count total
    count_query = select(func.count(Comment.comment_id)).where(Comment.team_id == team_id)
    if platform:
        count_query = count_query.where(Comment.platform == platform)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page).order_by(Comment.created_at.desc())
    
    result = await db.execute(query)
    comments = result.scalars().all()
    
    # Convert to response format
    comment_responses = []
    for comment in comments:
        # Get reply count
        reply_count_query = select(func.count(Reply.reply_id)).where(Reply.comment_id == comment.comment_id)
        reply_count_result = await db.execute(reply_count_query)
        reply_count = reply_count_result.scalar() or 0
        
        comment_responses.append(CommentResponse(
            comment_id=comment.comment_id,
            platform=comment.platform,
            author=comment.author,
            message=comment.message,
            created_at=comment.created_at,
            has_embedding=comment.embedding is not None,
            classification=comment.metadata.get("classification") if comment.metadata else None,
            reply_count=reply_count
        ))
    
    return CommentListResponse(
        comments=comment_responses,
        total=total,
        page=page,
        per_page=per_page,
        has_next=(offset + per_page) < total
    )


@router.get("/teams/{team_id}/comments/{comment_id}", response_model=CommentResponse)
async def get_comment(
    team_id: UUID,
    comment_id: UUID,
    current_team: Team = Depends(get_current_team),
    db: AsyncSession = Depends(get_db)
) -> CommentResponse:
    """Get specific comment details"""
    
    if current_team.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to team"
        )
    
    stmt = select(Comment).where(
        and_(Comment.comment_id == comment_id, Comment.team_id == team_id)
    )
    result = await db.execute(stmt)
    comment = result.scalar_one_or_none()
    
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found"
        )
    
    # Get reply count
    reply_count_query = select(func.count(Reply.reply_id)).where(Reply.comment_id == comment_id)
    reply_count_result = await db.execute(reply_count_query)
    reply_count = reply_count_result.scalar() or 0
    
    return CommentResponse(
        comment_id=comment.comment_id,
        platform=comment.platform,
        author=comment.author,
        message=comment.message,
        created_at=comment.created_at,
        has_embedding=comment.embedding is not None,
        classification=comment.metadata.get("classification") if comment.metadata else None,
        reply_count=reply_count
    )
