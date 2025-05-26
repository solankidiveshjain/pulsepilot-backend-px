"""
Task queue utility for background job management
"""

from typing import Any, Dict
from uuid import UUID
from arq import create_pool
from arq.connections import RedisSettings

from utils.config import get_config
from utils.logging import get_logger

logger = get_logger(__name__)
config = get_config()


class TaskQueue:
    """Task queue for background processing"""
    
    def __init__(self):
        self._pool = None
    
    async def get_pool(self):
        """Get Redis pool for ARQ"""
        if not self._pool:
            self._pool = await create_pool(RedisSettings.from_dsn(config.redis_url))
        return self._pool
    
    async def enqueue_webhook_processing(self, platform: str, payload_data: Dict[str, Any]) -> str:
        """Enqueue webhook processing task"""
        pool = await self.get_pool()
        job = await pool.enqueue_job('process_webhook_task', platform, payload_data)
        logger.info(f"Enqueued webhook processing job {job.job_id} for {platform}")
        return job.job_id
    
    async def enqueue_embedding_generation(self, comment_id: UUID) -> str:
        """Enqueue embedding generation task"""
        pool = await self.get_pool()
        job = await pool.enqueue_job('generate_embedding_task', str(comment_id))
        logger.info(f"Enqueued embedding generation job {job.job_id} for comment {comment_id}")
        return job.job_id
    
    async def enqueue_comment_classification(self, comment_id: UUID) -> str:
        """Enqueue comment classification task"""
        pool = await self.get_pool()
        job = await pool.enqueue_job('classify_comment_task', str(comment_id))
        logger.info(f"Enqueued classification job {job.job_id} for comment {comment_id}")
        return job.job_id
    
    async def enqueue_reply_submission(self, reply_id: UUID, platform: str, team_id: UUID) -> str:
        """Enqueue reply submission task"""
        pool = await self.get_pool()
        job = await pool.enqueue_job('submit_reply_task', str(reply_id), platform, str(team_id))
        logger.info(f"Enqueued reply submission job {job.job_id}")
        return job.job_id

    async def enqueue_suggestion_generation(self, comment_id: UUID, team_id: UUID) -> str:
        """Enqueue AI suggestion generation task"""
        pool = await self.get_pool()
        job = await pool.enqueue_job('generate_suggestions_task', str(comment_id), str(team_id))
        logger.info(f"Enqueued suggestion generation job {job.job_id} for comment {comment_id}")
        return job.job_id


# Global task queue instance
task_queue = TaskQueue()
