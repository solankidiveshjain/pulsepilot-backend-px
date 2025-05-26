"""
Background tasks for reply submission
"""

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database import Reply, Comment, SocialConnection
from services.social_platforms import get_platform_service
from utils.database import get_session
from utils.logging import get_logger


logger = get_logger(__name__)


async def submit_reply_to_platform(reply_id: UUID, platform: str, team_id: UUID):
    """Submit reply to social media platform"""
    try:
        async with get_session() as db:
            # Get reply and comment
            stmt = select(Reply).where(Reply.reply_id == reply_id)
            result = await db.execute(stmt)
            reply = result.scalar_one_or_none()
            
            if not reply:
                logger.error(f"Reply {reply_id} not found")
                return
            
            stmt = select(Comment).where(Comment.comment_id == reply.comment_id)
            result = await db.execute(stmt)
            comment = result.scalar_one_or_none()
            
            if not comment:
                logger.error(f"Comment {reply.comment_id} not found")
                return
            
            # Get platform connection
            stmt = select(SocialConnection).where(
                SocialConnection.team_id == team_id,
                SocialConnection.platform == platform,
                SocialConnection.status == "connected"
            )
            result = await db.execute(stmt)
            connection = result.scalar_one_or_none()
            
            if not connection:
                logger.error(f"No active connection for platform {platform} and team {team_id}")
                return
            
            # Get platform service
            platform_service = get_platform_service(platform)
            if not platform_service:
                logger.error(f"Unsupported platform: {platform}")
                return
            
            # Submit reply to platform
            external_comment_id = comment.metadata.get("external_id") if comment.metadata else None
            if not external_comment_id:
                logger.error(f"No external_id found for comment {comment.comment_id}")
                return
            
            result = await platform_service.post_reply(
                comment_id=external_comment_id,
                message=reply.message,
                access_token=connection.access_token
            )
            
            logger.info(f"Successfully submitted reply {reply_id} to {platform}")
            
    except Exception as e:
        logger.error(f"Failed to submit reply {reply_id} to platform: {str(e)}")
