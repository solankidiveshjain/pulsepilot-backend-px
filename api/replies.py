"""
Reply submission endpoints
"""

from uuid import UUID
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime

from models.database import Comment, Reply, User, Team
from utils.database import get_db
from utils.auth import get_current_team, get_current_user
from services.social_platforms import get_platform_service
from utils.task_queue import task_queue


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
    submitted_at: datetime = None
    job_id: str


class BulkReplyValidatedRequest(BaseModel):
    replies: List[BulkReplyItem]


class BulkReplyValidatedResponse(BaseModel):
    total_submitted: int
    successful: List[ReplyResponse]
    failed: List[Dict[str, Any]]
    job_ids: List[str]


@router.post("/{team_id}/comments/{comment_id}/reply")
async def submit_reply(
    team_id: UUID,
    comment_id: UUID,
    request: ReplyRequest,
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
    
    # Track token usage for reply processing
    from utils.token_tracker import TokenTracker
    token_tracker = TokenTracker()

    await token_tracker.track_usage(
        team_id=team_id,
        usage_type="reply_processing",
        tokens_used=len(request.message.split()),  # Estimate based on message length
        metadata={
            "operation": "reply_submission",
            "comment_id": str(comment_id),
            "message_length": len(request.message),
            "platform": comment.platform
        }
    )
    
    # Enqueue reply submission to background worker
    job_id = await task_queue.enqueue_reply_submission(
        reply.reply_id,
        comment.platform,
        team_id
    )
    
    return ReplyResponse(
        reply_id=reply.reply_id,
        message=reply.message,
        status="submitted",
        job_id=job_id
    )


@router.post("/{team_id}/comments/bulk-reply")
async def submit_bulk_replies(
    team_id: UUID,
    request: BulkReplyValidatedRequest,
    db: AsyncSession = Depends(get_db),
    current_team: Team = Depends(get_current_team),
    current_user: User = Depends(get_current_user)
) -> BulkReplyValidatedResponse:
    """Submit replies to multiple comments with strict validation"""
    
    # Verify team access
    if current_team.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to team"
        )
    
    successful_replies = []
    failed_replies = []
    job_ids = []
    
    for reply_item in request.replies:
        try:
            # Validate comment exists and belongs to team
            stmt = select(Comment).where(
                Comment.comment_id == reply_item.comment_id,
                Comment.team_id == team_id
            )
            result = await db.execute(stmt)
            comment = result.scalar_one_or_none()
            
            if not comment:
                failed_replies.append({
                    "comment_id": str(reply_item.comment_id),
                    "error": "Comment not found or access denied"
                })
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
            
            # Queue reply submission
            job_id = await task_queue.enqueue_reply_submission(
                reply.reply_id, 
                comment.platform, 
                team_id
            )
            job_ids.append(job_id)
            
            successful_replies.append(ReplyResponse(
                reply_id=reply.reply_id,
                message=reply.message,
                status="queued",
                submitted_at=reply.created_at
            ))
            
        except Exception as e:
            failed_replies.append({
                "comment_id": str(reply_item.comment_id),
                "error": str(e)
            })
    
    return BulkReplyValidatedResponse(
        total_submitted=len(successful_replies),
        successful=successful_replies,
        failed=failed_replies,
        job_ids=job_ids
    )
