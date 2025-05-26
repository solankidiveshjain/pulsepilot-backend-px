"""
Background tasks for comment processing
"""

import asyncio
from typing import Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from models.database import Comment, Team
from services.vector_service import VectorService
from services.classification_service import ClassificationService
from utils.database import get_session
from utils.logging import get_logger
from utils.token_tracker import TokenTracker


logger = get_logger(__name__)


async def process_comment_embedding(comment_data: Dict[str, Any]):
    """Process comment embedding and classification"""
    try:
        # Create comment in database
        async with get_session() as db:
            # Find team by platform connection or create if needed
            team_id = comment_data.get("team_id")
            if not team_id:
                # This would need platform-specific logic to find team
                logger.error("No team_id provided for comment processing")
                return
            
            # Create comment
            comment = Comment(
                team_id=UUID(team_id),
                platform=comment_data["platform"],
                author=comment_data.get("author"),
                message=comment_data.get("message"),
                post_id=UUID(comment_data["post_id"]) if comment_data.get("post_id") else None,
                metadata=comment_data.get("metadata", {})
            )
            
            db.add(comment)
            await db.commit()
            await db.refresh(comment)
            
            # Process embedding and classification in parallel
            await asyncio.gather(
                generate_comment_embedding(comment.comment_id),
                classify_comment_task(comment.comment_id),
                return_exceptions=True
            )
            
    except Exception as e:
        logger.error(f"Failed to process comment: {str(e)}")


async def generate_comment_embedding(comment_id: UUID):
    """Generate embedding for a comment"""
    try:
        vector_service = VectorService()
        token_tracker = TokenTracker()
        
        async with get_session() as db:
            # Get comment
            stmt = select(Comment).where(Comment.comment_id == comment_id)
            result = await db.execute(stmt)
            comment = result.scalar_one_or_none()
            
            if not comment or not comment.message:
                return
            
            # Generate embedding
            embedding = await vector_service.generate_embedding(comment.message)
            
            # Update comment with embedding
            stmt = update(Comment).where(
                Comment.comment_id == comment_id
            ).values(embedding=embedding)
            
            await db.execute(stmt)
            await db.commit()
            
            # Track token usage (approximate)
            await token_tracker.track_usage(
                team_id=comment.team_id,
                usage_type="embedding",
                tokens_used=len(comment.message.split()),  # Rough estimate
                cost=0.0001 * len(comment.message.split())
            )
            
            logger.info(f"Generated embedding for comment {comment_id}")
            
    except Exception as e:
        logger.error(f"Failed to generate embedding for comment {comment_id}: {str(e)}")


async def classify_comment_task(comment_id: UUID):
    """Classify a comment"""
    try:
        classification_service = ClassificationService()
        
        async with get_session() as db:
            # Get comment
            stmt = select(Comment).where(Comment.comment_id == comment_id)
            result = await db.execute(stmt)
            comment = result.scalar_one_or_none()
            
            if not comment or not comment.message:
                return
            
            # Classify comment
            classification = await classification_service.classify_comment(
                comment.message,
                comment.platform
            )
            
            # Update comment metadata
            metadata = comment.metadata or {}
            metadata["classification"] = classification
            
            stmt = update(Comment).where(
                Comment.comment_id == comment_id
            ).values(metadata=metadata)
            
            await db.execute(stmt)
            await db.commit()
            
            logger.info(f"Classified comment {comment_id}")
            
    except Exception as e:
        logger.error(f"Failed to classify comment {comment_id}: {str(e)}")
