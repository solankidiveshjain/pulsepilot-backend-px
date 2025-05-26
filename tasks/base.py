"""
Base task definitions and async task handling
"""

import asyncio
from typing import Any, Dict, List
from uuid import UUID
from abc import ABC, abstractmethod

from utils.logging import get_logger

logger = get_logger(__name__)


class BaseTask(ABC):
    """Base class for all background tasks"""
    
    @property
    @abstractmethod
    def task_name(self) -> str:
        """Task identifier"""
        pass
    
    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        """Execute the task"""
        pass
    
    async def run_with_error_handling(self, *args, **kwargs) -> Any:
        """Execute task with error handling and logging"""
        try:
            logger.info(f"Starting task: {self.task_name}")
            result = await self.execute(*args, **kwargs)
            logger.info(f"Completed task: {self.task_name}")
            return result
        except Exception as e:
            logger.error(f"Task {self.task_name} failed: {str(e)}")
            raise


class TaskQueue:
    """Simple async task queue for background processing"""
    
    def __init__(self):
        self._tasks: List[asyncio.Task] = []
    
    def add_task(self, coro):
        """Add coroutine to task queue"""
        task = asyncio.create_task(coro)
        self._tasks.append(task)
        return task
    
    async def wait_for_completion(self):
        """Wait for all tasks to complete"""
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()


# Global task queue
task_queue = TaskQueue()
