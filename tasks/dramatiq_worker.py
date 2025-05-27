"""
Dramatiq worker configuration for background tasks
"""

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from typing import List, Dict, Any
from uuid import UUID

from utils.config import get_config
from utils.logging import get_logger
from tasks.webhook_tasks import process_webhook_comments
from tasks.embedding_tasks import generate_comment_embedding
from tasks.classification_tasks import classify_comment
from tasks.reply_tasks import submit_reply_to_platform

config = get_config()
logger = get_logger(__name__)

# Setup Redis broker for Dramatiq
broker = RedisBroker(url=config.redis_url)
dramatiq.set_broker(broker)

@dramatiq.actor(max_retries=3)
async def process_webhook_task(platform: str, payload_data: Dict[str, Any]) -> List[str]:
    """Process webhook in background"""
    try:
        comment_ids = await process_webhook_comments(platform, payload_data)
        logger.info(f"Processed webhook for {platform}, created {len(comment_ids)} comments")
        return [str(cid) for cid in comment_ids]
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        raise

@dramatiq.actor(max_retries=3)
async def generate_embedding_task(comment_id: str) -> bool:
    """Generate embedding in background"""
    try:
        result = await generate_comment_embedding(UUID(comment_id))
        logger.info(f"Generated embedding for comment {comment_id}")
        return result
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        raise

@dramatiq.actor(max_retries=3)
async def classify_comment_task(comment_id: str) -> bool:
    """Classify comment in background"""
    try:
        result = await classify_comment(UUID(comment_id))
        logger.info(f"Classified comment {comment_id}")
        return result
    except Exception as e:
        logger.error(f"Comment classification failed: {e}")
        raise

@dramatiq.actor(max_retries=3)
async def submit_reply_task(reply_id: str, platform: str, team_id: str) -> bool:
    """Submit reply in background"""
    try:
        result = await submit_reply_to_platform(UUID(reply_id), platform, UUID(team_id))
        logger.info(f"Submitted reply {reply_id} to {platform}")
        return result
    except Exception as e:
        logger.error(f"Reply submission failed: {e}")
        raise

@dramatiq.actor(max_retries=3)
async def generate_suggestions_task(comment_id: str, team_id: str) -> Dict[str, Any]:
    """Generate AI suggestions in background"""
    try:
        from services.rag_service import RAGService
        from models.database import Comment, AiSuggestion
        from utils.database import get_session
        from utils.token_tracker import TokenTracker
        from sqlalchemy import select

        rag_service = RAGService()
        token_tracker = TokenTracker()

        async with get_session() as db:
            # Get comment
            stmt = select(Comment).where(Comment.comment_id == UUID(comment_id))
            res = await db.execute(stmt)
            comment = res.scalar_one_or_none()
            if not comment:
                raise ValueError(f"Comment {comment_id} not found")

            # Generate suggestions using RAG
            suggestions_data = await rag_service.generate_contextual_suggestions(
                comment=comment,
                team_id=UUID(team_id)
            )

            # Track token usage
            await token_tracker.track_llm_usage(
                team_id=UUID(team_id),
                model_name="gpt-4-turbo-preview",
                prompt_tokens=suggestions_data.get("tokens_used", 0) // 2,
                completion_tokens=suggestions_data.get("tokens_used", 0) // 2,
                total_tokens=suggestions_data.get("tokens_used", 0),
                operation="suggestion_generation"
            )

            # Save suggestions to database
            for suggestion_text, score in suggestions_data["suggestions"]:
                suggestion = AiSuggestion(
                    comment_id=UUID(comment_id),
                    suggested_reply=suggestion_text,
                    score=score
                )
                db.add(suggestion)

            await db.commit()
            logger.info(f"Generated {len(suggestions_data['suggestions'])} suggestions for comment {comment_id}")
            return suggestions_data
    except Exception as e:
        logger.error(f"Suggestion generation failed: {e}")
        raise 