"""
Embedding generation endpoints
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel

from models.database import Comment
from utils.database import get_db
from services.vector_service import VectorService
from tasks.embedding_tasks import generate_comment_embedding


router = APIRouter()


class EmbeddingRequest(BaseModel):
    comment_id: UUID


class EmbeddingResponse(BaseModel):
    comment_id: UUID
    status: str
    embedding_dimensions: int


@router.post("/generate")
async def generate_embedding(
    request: EmbeddingRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    vector_service: VectorService = Depends()
) -> EmbeddingResponse:
    """Generate embeddings for a comment"""
    
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
            detail="Comment has no message to embed"
        )
    
    # Check if embedding already exists
    if comment.embedding:
        return EmbeddingResponse(
            comment_id=comment.comment_id,
            status="already_exists",
            embedding_dimensions=len(comment.embedding)
        )
    
    # Generate embedding in background
    background_tasks.add_task(
        generate_comment_embedding,
        request.comment_id
    )
    
    return EmbeddingResponse(
        comment_id=comment.comment_id,
        status="queued",
        embedding_dimensions=768  # all-MiniLM-L6-v2 dimensions
    )
