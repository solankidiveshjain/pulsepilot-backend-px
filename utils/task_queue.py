"""
Task queue utility for background job management
"""

from typing import Any, Dict
from uuid import UUID
from tasks.dramatiq_worker import (
    process_webhook_task,
    generate_embedding_task,
    classify_comment_task,
    submit_reply_task,
    generate_suggestions_task,
)

from utils.config import get_config
from utils.logging import get_logger

logger = get_logger(__name__)
config = get_config()


class TaskQueue:
    """Task queue for background processing"""
    
    def __init__(self):
        pass
    
    async def enqueue_webhook_processing(self, platform: str, payload_data: Dict[str, Any]) -> str:
        """Enqueue webhook processing task"""
        msg = process_webhook_task.send(platform, payload_data)
        logger.info(f"Enqueued webhook processing job {msg.message_id} for {platform}")
        return msg.message_id
    
    async def enqueue_embedding_generation(self, comment_id: UUID) -> str:
        """Enqueue embedding generation task"""
        msg = generate_embedding_task.send(str(comment_id))
        logger.info(f"Enqueued embedding generation job {msg.message_id} for comment {comment_id}")
        return msg.message_id
    
    async def enqueue_comment_classification(self, comment_id: UUID) -> str:
        """Enqueue comment classification task"""
        msg = classify_comment_task.send(str(comment_id))
        logger.info(f"Enqueued classification job {msg.message_id} for comment {comment_id}")
        return msg.message_id
    
    async def enqueue_reply_submission(self, reply_id: UUID, platform: str, team_id: UUID) -> str:
        """Enqueue reply submission task"""
        msg = submit_reply_task.send(str(reply_id), platform, str(team_id))
        logger.info(f"Enqueued reply submission job {msg.message_id}")
        return msg.message_id

    async def enqueue_suggestion_generation(self, comment_id: UUID, team_id: UUID) -> str:
        """Enqueue AI suggestion generation task"""
        msg = generate_suggestions_task.send(str(comment_id), str(team_id))
        logger.info(f"Enqueued suggestion generation job {msg.message_id} for comment {comment_id}")
        return msg.message_id


# Global task queue instance
task_queue = TaskQueue()
