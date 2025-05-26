"""
ARQ worker configuration for background tasks
"""

import asyncio
from arq import create_pool
from arq.connections import RedisSettings
from typing import Dict, Any
from uuid import UUID

from utils.config import get_config
from utils.logging import get_logger
from tasks.webhook_tasks import process_webhook_comments
from tasks.embedding_tasks import generate_comment_embedding
from tasks.classification_tasks import classify_comment
from tasks.reply_tasks import submit_reply_to_platform

logger = get_logger(__name__)
config = get_config()


async def startup(ctx):
    """Worker startup"""
    logger.info("ARQ worker starting up")


async def shutdown(ctx):
    """Worker shutdown"""
    logger.info("ARQ worker shutting down")


async def process_webhook_task(ctx, platform: str, payload_data: Dict[str, Any]) -> List[str]:
    """Process webhook in background"""
    try:
        comment_ids = await process_webhook_comments(platform, payload_data)
        logger.info(f"Processed webhook for {platform}, created {len(comment_ids)} comments")
        return [str(cid) for cid in comment_ids]
    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}")
        raise


async def generate_embedding_task(ctx, comment_id: str) -> bool:
    """Generate embedding in background"""
    try:
        result = await generate_comment_embedding(UUID(comment_id))
        logger.info(f"Generated embedding for comment {comment_id}")
        return result
    except Exception as e:
        logger.error(f"Embedding generation failed: {str(e)}")
        raise


async def classify_comment_task(ctx, comment_id: str) -> bool:
    """Classify comment in background"""
    try:
        result = await classify_comment(UUID(comment_id))
        logger.info(f"Classified comment {comment_id}")
        return result
    except Exception as e:
        logger.error(f"Comment classification failed: {str(e)}")
        raise


async def submit_reply_task(ctx, reply_id: str, platform: str, team_id: str) -> bool:
    """Submit reply in background"""
    try:
        result = await submit_reply_to_platform(UUID(reply_id), platform, UUID(team_id))
        logger.info(f"Submitted reply {reply_id} to {platform}")
        return result
    except Exception as e:
        logger.error(f"Reply submission failed: {str(e)}")
        raise


async def generate_suggestions_task(ctx, comment_id: str, team_id: str) -> Dict[str, Any]:
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
            result = await db.execute(stmt)
            comment = result.scalar_one_or_none()
            
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
        logger.error(f"Suggestion generation failed: {str(e)}")
        raise


class WorkerSettings:
    """ARQ worker settings"""
    functions = [
        process_webhook_task,
        generate_embedding_task,
        classify_comment_task,
        submit_reply_task,
        generate_suggestions_task,
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(config.redis_url)
    job_timeout = 300
    keep_result = 3600


# Create ARQ pool for enqueueing jobs
async def get_arq_pool():
    """Get ARQ Redis pool"""
    return await create_pool(WorkerSettings.redis_settings)
