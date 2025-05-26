"""
Async task manager for isolating heavy I/O operations
"""

import asyncio
from typing import Any, Dict, List, Optional, Callable
from uuid import UUID
from arq import create_pool
from arq.connections import RedisSettings

from utils.config import get_config
from utils.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)
config = get_config()


class AsyncTaskManager:
    """Manager for async background tasks with proper isolation"""
    
    def __init__(self):
        """Initialize task manager with Redis connection pool"""
        self._pool: Optional[Any] = None
        self.redis_settings = RedisSettings.from_dsn(config.redis_url)
    
    async def get_pool(self) -> Any:
        """
        Get Redis connection pool for task queue
        
        Returns:
            Redis connection pool
        """
        if not self._pool:
            self._pool = await create_pool(self.redis_settings)
        return self._pool
    
    async def enqueue_llm_generation(
        self,
        comment_id: UUID,
        team_id: UUID,
        context_data: Dict[str, Any]
    ) -> str:
        """
        Enqueue LLM suggestion generation task
        
        Args:
            comment_id: Comment ID to generate suggestions for
            team_id: Team ID for billing tracking
            context_data: Additional context for generation
            
        Returns:
            Job ID for tracking
        """
        pool = await self.get_pool()
        job = await pool.enqueue_job(
            'generate_llm_suggestions',
            str(comment_id),
            str(team_id),
            context_data
        )
        
        logger.info("Enqueued LLM generation task", 
                   job_id=job.job_id, 
                   comment_id=str(comment_id),
                   team_id=str(team_id))
        
        return job.job_id
    
    async def enqueue_vector_embedding(
        self,
        comment_id: UUID,
        text: str,
        team_id: UUID
    ) -> str:
        """
        Enqueue vector embedding generation task
        
        Args:
            comment_id: Comment ID
            text: Text to embed
            team_id: Team ID for billing
            
        Returns:
            Job ID for tracking
        """
        pool = await self.get_pool()
        job = await pool.enqueue_job(
            'generate_vector_embedding',
            str(comment_id),
            text,
            str(team_id)
        )
        
        logger.info("Enqueued vector embedding task",
                   job_id=job.job_id,
                   comment_id=str(comment_id))
        
        return job.job_id
    
    async def enqueue_platform_reply(
        self,
        reply_id: UUID,
        platform: str,
        comment_external_id: str,
        message: str,
        access_token: str
    ) -> str:
        """
        Enqueue platform reply submission task
        
        Args:
            reply_id: Internal reply ID
            platform: Target platform
            comment_external_id: External comment ID
            message: Reply message
            access_token: Platform access token
            
        Returns:
            Job ID for tracking
        """
        pool = await self.get_pool()
        job = await pool.enqueue_job(
            'submit_platform_reply',
            str(reply_id),
            platform,
            comment_external_id,
            message,
            access_token
        )
        
        logger.info("Enqueued platform reply task",
                   job_id=job.job_id,
                   reply_id=str(reply_id),
                   platform=platform)
        
        return job.job_id
    
    async def enqueue_webhook_processing(
        self,
        platform: str,
        payload_data: Dict[str, Any],
        team_id: Optional[UUID] = None
    ) -> str:
        """
        Enqueue webhook payload processing task
        
        Args:
            platform: Source platform
            payload_data: Webhook payload
            team_id: Team ID if available
            
        Returns:
            Job ID for tracking
        """
        pool = await self.get_pool()
        job = await pool.enqueue_job(
            'process_webhook_payload',
            platform,
            payload_data,
            str(team_id) if team_id else None
        )
        
        logger.info("Enqueued webhook processing task",
                   job_id=job.job_id,
                   platform=platform,
                   team_id=str(team_id) if team_id else None)
        
        return job.job_id
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get status of background job
        
        Args:
            job_id: Job ID to check
            
        Returns:
            Job status information
        """
        pool = await self.get_pool()
        job = await pool.get_job(job_id)
        
        if not job:
            return {"status": "not_found"}
        
        return {
            "status": job.status,
            "result": job.result,
            "started_at": job.started_at,
            "finished_at": job.finished_at
        }


# Global task manager instance
task_manager = AsyncTaskManager()
