"""
Comment classification endpoints
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel

from models.database import Comment
from utils.database import get_db
from services.classification_service import ClassificationService
from tasks.classification_tasks import classify_comment


router = APIRouter()


class ClassificationRequest(BaseModel):
    comment_id: UUID


class ClassificationResponse(BaseModel):
    comment_id: UUID
    status: str
    sentiment: str = None
    emotion: str = None
    category: str = None


@router.post("/classify")
async def classify_comment_endpoint(
    request: ClassificationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    classification_service: ClassificationService = Depends()
) -> ClassificationResponse:
    """Classify sentiment/emotion/category of a comment"""
    
    # Find comment
    stmt = select(Comment).where(
        Comment.comment_id == request.comment_id
    )
    result = await db.execute(stmt)
    comment = result.scalar_one_or_none()
    
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found"
        )
    
    if not comment.message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comment has no message to classify"
        )
    
    # Check if classification already exists in metadata
    if comment.metadata and "classification" in comment.metadata:
        classification = comment.metadata["classification"]
        return ClassificationResponse(
            comment_id=comment.comment_id,
            status="already_classified",
            sentiment=classification.get("sentiment"),
            emotion=classification.get("emotion"),
            category=classification.get("category")
        )
    
    # Classify comment in background
    background_tasks.add_task(
        classify_comment,
        request.comment_id
    )
    
    return ClassificationResponse(
        comment_id=comment.comment_id,
        status="queued"
    )
