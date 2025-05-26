"""
Workflow orchestrator for comment processing pipeline
"""

import asyncio
from typing import Dict, Any, List
from uuid import UUID
from datetime import datetime, timedelta

from tasks.comment_tasks import process_comment_embedding
from tasks.embedding_tasks import batch_generate_embeddings
from tasks.classification_tasks import batch_classify_comments
from utils.logging import get_logger


logger = get_logger(__name__)


class CommentProcessingWorkflow:
    """Orchestrates the comment processing pipeline"""
    
    def __init__(self):
        self.batch_size = 50
        self.processing_interval = 300  # 5 minutes
    
    async def process_webhook_comments(self, comments: List[Dict[str, Any]]):
        """Process comments from webhook"""
        try:
            # Process comments in parallel batches
            tasks = []
            for comment_data in comments:
                task = asyncio.create_task(process_comment_embedding(comment_data))
                tasks.append(task)
            
            # Wait for all tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)
            
            logger.info(f"Processed {len(comments)} webhook comments")
            
        except Exception as e:
            logger.error(f"Failed to process webhook comments: {str(e)}")
    
    async def run_batch_processing(self, team_id: UUID):
        """Run batch processing for a team"""
        try:
            # Run embedding and classification in parallel
            await asyncio.gather(
                batch_generate_embeddings(team_id, self.batch_size),
                batch_classify_comments(team_id, self.batch_size),
                return_exceptions=True
            )
            
            logger.info(f"Completed batch processing for team {team_id}")
            
        except Exception as e:
            logger.error(f"Failed to run batch processing for team {team_id}: {str(e)}")
    
    async def run_periodic_processing(self):
        """Run periodic processing for all teams"""
        try:
            from utils.database import get_session
            from models.database import Team
            from sqlalchemy import select
            
            async with get_session() as db:
                # Get all teams
                stmt = select(Team)
                result = await db.execute(stmt)
                teams = result.scalars().all()
                
                # Process each team
                tasks = []
                for team in teams:
                    task = asyncio.create_task(self.run_batch_processing(team.team_id))
                    tasks.append(task)
                
                await asyncio.gather(*tasks, return_exceptions=True)
                
                logger.info(f"Completed periodic processing for {len(teams)} teams")
                
        except Exception as e:
            logger.error(f"Failed to run periodic processing: {str(e)}")


# Global workflow instance
comment_workflow = CommentProcessingWorkflow()
