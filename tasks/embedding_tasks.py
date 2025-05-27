"""
Background tasks for embedding generation
"""

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database import Comment
from services.vector_service import VectorService
from utils.database import get_session
from utils.logging import get_logger
from utils.token_tracker import TokenTracker
from utils.db_utils import upsert


logger = get_logger(__name__)


async def generate_comment_embedding(comment_id: UUID):
    """Generate embedding for a comment (standalone task)"""
    try:
        vector_service = VectorService()
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
                logger.error(f"Comment {comment_id} has no message to embed")
                return
            
            if comment.embedding:
                logger.info(f"Comment {comment_id} already has embedding")
                return
            
            # Generate embedding
            embedding = await vector_service.generate_embedding(comment.message)
            
            # Upsert comment embedding
            await upsert(
                session=db,
                model=Comment,
                values={
                    "comment_id": comment_id,
                    "embedding": embedding
                },
                pk_field="comment_id"
            )
            
            # Track token usage
            await token_tracker.track_usage(
                team_id=comment.team_id,
                usage_type="embedding",
                tokens_used=len(comment.message.split()),
                cost=0.0001 * len(comment.message.split())
            )
            
            logger.info(f"Generated embedding for comment {comment_id}")
            
    except Exception as e:
        logger.error(f"Failed to generate embedding for comment {comment_id}: {str(e)}")


async def batch_generate_embeddings(team_id: UUID, limit: int = 100):
    """Generate embeddings for comments without embeddings"""
    try:
        vector_service = VectorService()
        
        async with get_session() as db:
            # Get comments without embeddings
            stmt = select(Comment).where(
                Comment.team_id == team_id,
                Comment.embedding.is_(None),
                Comment.message.isnot(None)
            ).limit(limit)
            
            result = await db.execute(stmt)
            comments = result.scalars().all()
            
            logger.info(f"Processing {len(comments)} comments for embedding generation")
            
            for comment in comments:
                await generate_comment_embedding(comment.comment_id)
            
    except Exception as e:
        logger.error(f"Failed to batch generate embeddings: {str(e)}")
