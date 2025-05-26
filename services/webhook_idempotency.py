"""
Webhook idempotency service for safe retry handling
"""

import hashlib
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from pydantic import BaseModel

from models.database import Comment
from utils.database import get_session
from utils.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)


class WebhookEvent(BaseModel):
    """Webhook event data model"""
    platform: str
    external_id: str
    event_type: str
    payload_hash: str
    team_id: Optional[UUID] = None


class WebhookIdempotencyService:
    """Service for ensuring webhook processing idempotency"""
    
    def __init__(self):
        """Initialize idempotency service"""
        self.deduplication_window = timedelta(hours=24)
    
    async def is_duplicate_event(
        self,
        platform: str,
        external_id: str,
        payload: Dict[str, Any]
    ) -> bool:
        """
        Check if webhook event is a duplicate within deduplication window
        
        Args:
            platform: Source platform
            external_id: External event/comment ID
            payload: Webhook payload
            
        Returns:
            True if event is duplicate
        """
        payload_hash = self._generate_payload_hash(payload)
        cutoff_time = datetime.utcnow() - self.deduplication_window
        
        async with get_session() as db:
            # Check for existing event with same external_id and payload hash
            stmt = text("""
                SELECT COUNT(*) 
                FROM webhook_events 
                WHERE platform = :platform 
                  AND external_id = :external_id 
                  AND payload_hash = :payload_hash
                  AND created_at > :cutoff_time
            """)
            
            result = await db.execute(stmt, {
                "platform": platform,
                "external_id": external_id,
                "payload_hash": payload_hash,
                "cutoff_time": cutoff_time
            })
            
            count = result.scalar()
            return count > 0
    
    async def record_webhook_event(
        self,
        platform: str,
        external_id: str,
        event_type: str,
        payload: Dict[str, Any],
        team_id: Optional[UUID] = None
    ) -> None:
        """
        Record webhook event for idempotency tracking
        
        Args:
            platform: Source platform
            external_id: External event/comment ID
            event_type: Type of webhook event
            payload: Webhook payload
            team_id: Team ID if available
        """
        payload_hash = self._generate_payload_hash(payload)
        
        async with get_session() as db:
            # Insert webhook event record
            stmt = text("""
                INSERT INTO webhook_events 
                (platform, external_id, event_type, payload_hash, team_id, created_at)
                VALUES (:platform, :external_id, :event_type, :payload_hash, :team_id, :created_at)
                ON CONFLICT (platform, external_id, payload_hash) DO NOTHING
            """)
            
            await db.execute(stmt, {
                "platform": platform,
                "external_id": external_id,
                "event_type": event_type,
                "payload_hash": payload_hash,
                "team_id": str(team_id) if team_id else None,
                "created_at": datetime.utcnow()
            })
            
            await db.commit()
    
    async def upsert_comment(
        self,
        platform: str,
        external_id: str,
        author: Optional[str],
        message: str,
        team_id: UUID,
        post_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Comment:
        """
        Upsert comment with idempotency protection
        
        Args:
            platform: Source platform
            external_id: External comment ID
            author: Comment author
            message: Comment message
            team_id: Team ID
            post_id: External post ID
            metadata: Additional metadata
            
        Returns:
            Comment object (new or existing)
        """
        async with get_session() as db:
            # Try to find existing comment by external_id and platform
            stmt = select(Comment).where(
                Comment.metadata_json['external_id'] == external_id,
                Comment.platform == platform,
                Comment.team_id == team_id
            )
            
            result = await db.execute(stmt)
            existing_comment = result.scalar_one_or_none()
            
            if existing_comment:
                logger.info("Found existing comment, skipping duplicate",
                           comment_id=str(existing_comment.comment_id),
                           external_id=external_id,
                           platform=platform)
                return existing_comment
            
            # Create new comment
            comment_metadata = metadata or {}
            comment_metadata['external_id'] = external_id
            if post_id:
                comment_metadata['post_id'] = post_id
            
            new_comment = Comment(
                team_id=team_id,
                platform=platform,
                author=author,
                message=message,
                metadata=comment_metadata
            )
            
            db.add(new_comment)
            await db.commit()
            await db.refresh(new_comment)
            
            logger.info("Created new comment from webhook",
                       comment_id=str(new_comment.comment_id),
                       external_id=external_id,
                       platform=platform)
            
            return new_comment
    
    async def cleanup_old_events(self) -> int:
        """
        Clean up old webhook events beyond deduplication window
        
        Returns:
            Number of events cleaned up
        """
        cutoff_time = datetime.utcnow() - self.deduplication_window
        
        async with get_session() as db:
            stmt = text("""
                DELETE FROM webhook_events 
                WHERE created_at < :cutoff_time
            """)
            
            result = await db.execute(stmt, {"cutoff_time": cutoff_time})
            await db.commit()
            
            deleted_count = result.rowcount
            logger.info("Cleaned up old webhook events", count=deleted_count)
            
            return deleted_count
    
    def _generate_payload_hash(self, payload: Dict[str, Any]) -> str:
        """
        Generate deterministic hash of webhook payload
        
        Args:
            payload: Webhook payload
            
        Returns:
            SHA-256 hash of payload
        """
        import json
        
        # Sort keys for deterministic hashing
        payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(payload_str.encode()).hexdigest()


# Global idempotency service
webhook_idempotency = WebhookIdempotencyService()
