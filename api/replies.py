"""
Reply submission endpoints
"""

from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from models.database import Comment, Reply, User, Team
from utils.database import get_db
from utils.auth import get_current_team, get_current_user
from services.social_platforms import get_platform_service
from tasks.reply_tasks import submit_reply_to_platform


router = APIRouter()


class ReplyRequest(BaseModel):
    message: str


class BulkReplyItem(BaseModel):
    comment_id: UUID
    message: str


class BulkReplyRequest(BaseModel):
    replies: List[BulkReplyItem]


class ReplyResponse(BaseModel):
    reply_id: UUID
    message: str
    status: str


@router.post("/{team_id}/comments/{comment_id}/reply")
async def submit_reply(
    team_id: UUID,
    comment_id: UUID,
    request: ReplyRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_team: Team = Depends(get_current_team),
    current_user: User = Depends(get_current_user)
) -> ReplyResponse:
    """Submit a reply to a comment"""
    
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
    
    # Create reply record
    reply = Reply(
        comment_id=comment_id,
        user_id=current_user.user_id,
        message=request.message
    )
    
    db.add(reply)
    await db.commit()
    await db.refresh(reply)
    
    # Submit reply to platform in background
    background_tasks.add_task(
        submit_reply_to_platform,
        reply.reply_id,
        comment.platform,
        team_id
    )
    
    return ReplyResponse(
        reply_id=reply.reply_id,
        message=reply.message,
        status="submitted"
    )


@router.post("/{team_id}/comments/bulk-reply")
async def submit_bulk_replies(
    team_id: UUID,
    request: BulkReplyRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_team: Team = Depends(get_current_team),
    current_user: User = Depends(get_current_user)
) -> List[ReplyResponse]:
    """Submit replies to multiple comments"""
    
    # Verify team access
    if current_team.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to team"
        )
    
    responses = []
    
    for reply_item in request.replies:
        # Find comment
        stmt = select(Comment).where(
            Comment.comment_id == reply_item.comment_id,
            Comment.team_id == team_id
        )
        result = await db.execute(stmt)
        comment = result.scalar_one_or_none()
        
        if not comment:
            responses.append(ReplyResponse(
                reply_id=reply_item.comment_id,  # Using comment_id as placeholder
                message=reply_item.message,
                status="error: comment not found"
            ))
            continue
        
        # Create reply record
        reply = Reply(
            comment_id=reply_item.comment_id,
            user_id=current_user.user_id,
            message=reply_item.message
        )
        
        db.add(reply)
        await db.commit()
        await db.refresh(reply)
        
        # Submit reply to platform in background
        background_tasks.add_task(
            submit_reply_to_platform,
            reply.reply_id,
            comment.platform,
            team_id
        )
        
        responses.append(ReplyResponse(
            reply_id=reply.reply_id,
            message=reply.message,
            status="submitted"
        ))
    
    return responses
