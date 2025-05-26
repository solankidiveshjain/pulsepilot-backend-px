"""
Background tasks for comment classification
"""

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from models.database import Comment
from services.classification_service import ClassificationService
from utils.database import get_session
from utils.logging import get_logger
from utils.token_tracker import TokenTracker


logger = get_logger(__name__)


async def classify_comment(comment_id: UUID):
    """Classify a comment (standalone task)"""
    try:
        classification_service = ClassificationService()
        token_tracker = TokenTracker()
        
        async with get_session() as db:
            # Get comment
            stmt = select(Comment).where(Comment.comment_id == comment_id)
            result = await db.execute(stmt)
            comment = result.scalar_one_or_none()
            
            if not comment:
                logger.error(f"Comment {comment_id} not found")
                return
            
            if not comment.message:
                logger.error(f"Comment {comment_id} has no message to classify")
                return
            
            # Check if already classified
            if comment.metadata and "classification" in comment.metadata:
                logger.info(f"Comment {comment_id} already classified")
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
            
            # Track token usage (approximate)
            await token_tracker.track_usage(
                team_id=comment.team_id,
                usage_type="classification",
                tokens_used=len(comment.message.split()),
                cost=0.0002 * len(comment.message.split())
            )
            
            logger.info(f"Classified comment {comment_id}")
            
    except Exception as e:
        logger.error(f"Failed to classify comment {comment_id}: {str(e)}")


async def batch_classify_comments(team_id: UUID, limit: int = 100):
    """Classify comments without classification"""
    try:
        async with get_session() as db:
            # Get comments without classification
            stmt = select(Comment).where(
                Comment.team_id == team_id,
                Comment.message.isnot(None)
            ).limit(limit)
            
            result = await db.execute(stmt)
            comments = result.scalars().all()
            
            # Filter comments that don't have classification
            unclassified_comments = []
            for comment in comments:
                if not comment.metadata or "classification" not in comment.metadata:
                    unclassified_comments.append(comment)
            
            logger.info(f"Processing {len(unclassified_comments)} comments for classification")
            
            for comment in unclassified_comments:
                await classify_comment(comment.comment_id)
            
    except Exception as e:
        logger.error(f"Failed to batch classify comments: {str(e)}")
