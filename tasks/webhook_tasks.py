"""
Webhook processing background tasks
"""

from typing import Dict, Any, List
from uuid import UUID

from .base import BaseTask, task_queue
from services.platforms.registry import get_platform_service
from services.platforms.base import WebhookPayload, CommentData
from models.database import Comment, Reply
from utils.database import get_session
from utils.logging import get_logger
from utils.exceptions import PlatformError, DatabaseError

logger = get_logger(__name__)


class WebhookProcessingTask(BaseTask):
    """Process webhook and extract comments"""
    
    @property
    def task_name(self) -> str:
        return "webhook_processing"
    
    async def execute(self, platform: str, payload_data: Dict[str, Any]) -> List[UUID]:
        """Process webhook payload and create comments"""
        try:
            # Get platform service
            platform_service = get_platform_service(platform)
            
            # Create webhook payload
            payload = WebhookPayload(
                headers=payload_data["headers"],
                body=payload_data["body"],
                json_data=payload_data["json_data"]
            )
            
            # Extract comments from webhook
            comments_data = await platform_service.ingest_webhook(payload)
            
            # Store comments in database
            comment_ids = []
            async with get_session() as db:
                for comment_data in comments_data:
                    comment = Comment(
                        team_id=payload_data.get("team_id"),  # This should be determined from webhook
                        platform=platform,
                        author=comment_data.author,
                        message=comment_data.message,
                        metadata={
                            "external_id": comment_data.external_id,
                            "post_id": comment_data.post_id,
                            **comment_data.platform_metadata
                        }
                    )
                    
                    db.add(comment)
                    await db.commit()
                    await db.refresh(comment)
                    comment_ids.append(comment.comment_id)
                    
                    # Queue embedding and classification tasks
                    task_queue.add_task(
                        EmbeddingGenerationTask().run_with_error_handling(comment.comment_id)
                    )
                    task_queue.add_task(
                        CommentClassificationTask().run_with_error_handling(comment.comment_id)
                    )
            
            return comment_ids
            
        except Exception as e:
            raise PlatformError(f"Webhook processing failed for {platform}", {"error": str(e)})


class EmbeddingGenerationTask(BaseTask):
    """Generate embeddings for comments"""
    
    @property
    def task_name(self) -> str:
        return "embedding_generation"
    
    async def execute(self, comment_id: UUID) -> bool:
        """Generate embedding for a comment"""
        try:
            from services.vector_service import VectorService
            from utils.token_tracker import TokenTracker
            from sqlalchemy import select, update
            
            vector_service = VectorService()
            token_tracker = TokenTracker()
            
            async with get_session() as db:
                # Get comment
                stmt = select(Comment).where(Comment.comment_id == comment_id)
                result = await db.execute(stmt)
                comment = result.scalar_one_or_none()
                
                if not comment or not comment.message:
                    return False
                
                if comment.embedding:
                    logger.info(f"Comment {comment_id} already has embedding")
                    return True
                
                # Combine comment and any replies for embedding
                stmt_r = select(Reply).where(Reply.comment_id == comment_id)
                res_r = await db.execute(stmt_r)
                reply_objs = res_r.scalars().all()
                texts = [comment.message] + [r.message for r in reply_objs if r.message]
                text_to_embed = " ".join(texts)
                # Generate embedding on combined text
                embedding = await vector_service.generate_embedding(text_to_embed)
                
                # Update comment
                stmt = update(Comment).where(
                    Comment.comment_id == comment_id
                ).values(embedding=embedding)
                
                await db.execute(stmt)
                await db.commit()
                
                # Track token usage
                await token_tracker.track_usage(
                    team_id=comment.team_id,
                    usage_type="embedding",
                    tokens_used=len(text_to_embed.split()),
                    cost=0.0001 * len(text_to_embed.split())
                )
                
                return True
                
        except Exception as e:
            raise DatabaseError(f"Embedding generation failed for comment {comment_id}", {"error": str(e)})


class CommentClassificationTask(BaseTask):
    """Classify comments for sentiment/emotion/category"""
    
    @property
    def task_name(self) -> str:
        return "comment_classification"
    
    async def execute(self, comment_id: UUID) -> bool:
        """Classify a comment"""
        try:
            from sqlalchemy import select, update
            
            async with get_session() as db:
                # Get comment
                stmt = select(Comment).where(Comment.comment_id == comment_id)
                result = await db.execute(stmt)
                comment = result.scalar_one_or_none()
                
                if not comment or not comment.message:
                    return False
                
                # Check if already classified
                if comment.metadata and "classification" in comment.metadata:
                    logger.info(f"Comment {comment_id} already classified")
                    return True
                
                # Instantiate services after skip
                from services.classification_service import ClassificationService
                from utils.token_tracker import TokenTracker
                classification_service = ClassificationService()
                token_tracker = TokenTracker()
                
                # Combine comment and replies for classification
                stmt_r = select(Reply).where(Reply.comment_id == comment_id)
                res_r = await db.execute(stmt_r)
                reply_objs = res_r.scalars().all()
                texts = [comment.message] + [r.message for r in reply_objs if r.message]
                text_to_classify = " ".join(texts)
                # Classify comment context
                classification = await classification_service.classify_comment(
                    text_to_classify,
                    comment.platform
                )
                
                # Update metadata
                metadata = comment.metadata or {}
                metadata["classification"] = classification
                
                stmt = update(Comment).where(
                    Comment.comment_id == comment_id
                ).values(metadata_json=metadata)
                
                await db.execute(stmt)
                await db.commit()
                
                # Track token usage
                await token_tracker.track_usage(
                    team_id=comment.team_id,
                    usage_type="classification",
                    tokens_used=len(text_to_classify.split()),
                    cost=0.0002 * len(text_to_classify.split())
                )
                
                return True
                
        except Exception as e:
            error_info = {"error": str(e)}
            raise DatabaseError("Classification failed for comment {}".format(comment_id), error_info)


class ReplySubmissionTask(BaseTask):
    """Submit replies to social platforms"""
    
    @property
    def task_name(self) -> str:
        return "reply_submission"
    
    async def execute(self, reply_id: UUID, platform: str, team_id: UUID) -> bool:
        """Submit reply to platform"""
        try:
            from models.database import Reply, SocialConnection
            from sqlalchemy import select
            
            platform_service = get_platform_service(platform)
            
            async with get_session() as db:
                # Get reply and comment
                stmt = select(Reply).where(Reply.reply_id == reply_id)
                result = await db.execute(stmt)
                reply = result.scalar_one_or_none()
                
                if not reply:
                    return False
                
                stmt = select(Comment).where(Comment.comment_id == reply.comment_id)
                result = await db.execute(stmt)
                comment = result.scalar_one_or_none()
                
                if not comment:
                    return False
                
                # Get platform connection
                stmt = select(SocialConnection).where(
                    SocialConnection.team_id == team_id,
                    SocialConnection.platform == platform,
                    SocialConnection.status == "connected"
                )
                result = await db.execute(stmt)
                connection = result.scalar_one_or_none()
                
                if not connection:
                    raise PlatformError(f"No active connection for {platform}")
                
                # Get external comment ID
                external_comment_id = comment.metadata.get("external_id")
                if not external_comment_id:
                    raise PlatformError("No external comment ID found")
                
                # Submit reply
                await platform_service.post_reply(
                    comment_id=external_comment_id,
                    message=reply.message,
                    access_token=connection.access_token
                )
                
                return True
                
        except Exception as e:
            raise PlatformError(f"Reply submission failed for {platform}", {"error": str(e)})


# Task instances
webhook_processing_task = WebhookProcessingTask()
embedding_generation_task = EmbeddingGenerationTask()
comment_classification_task = CommentClassificationTask()
reply_submission_task = ReplySubmissionTask()
