"""
Connection management service to handle database operations for platforms
"""

from uuid import UUID
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from models.database import SocialConnection
from utils.database import get_session
from utils.logging import get_logger
from utils.exceptions import DatabaseError
from schemas.responses import ConnectionResponse

logger = get_logger(__name__)


class ConnectionManager:
    """Manages social platform connections in database"""
    
    async def store_connection(
        self,
        team_id: UUID,
        platform: str,
        connection_data: Dict[str, Any]
    ) -> ConnectionResponse:
        """Store or update platform connection"""
        
        try:
            async with get_session() as db:
                # Check for existing connection
                stmt = select(SocialConnection).where(
                    SocialConnection.team_id == team_id,
                    SocialConnection.platform == platform
                )
                result = await db.execute(stmt)
                existing_connection = result.scalar_one_or_none()
                
                if existing_connection:
                    # Update existing connection
                    stmt = update(SocialConnection).where(
                        SocialConnection.connection_id == existing_connection.connection_id
                    ).values(
                        access_token=connection_data["access_token"],
                        refresh_token=connection_data.get("refresh_token"),
                        token_expires=connection_data.get("token_expires"),
                        status=connection_data["status"],
                        metadata=connection_data.get("metadata", {}),
                        updated_at=datetime.utcnow()
                    )
                    await db.execute(stmt)
                    await db.commit()
                    
                    return ConnectionResponse(
                        connection_id=existing_connection.connection_id,
                        platform=platform,
                        status=connection_data["status"],
                        created_at=existing_connection.created_at,
                        expires_at=connection_data.get("token_expires")
                    )
                else:
                    # Create new connection
                    connection = SocialConnection(
                        team_id=team_id,
                        platform=platform,
                        status=connection_data["status"],
                        access_token=connection_data["access_token"],
                        refresh_token=connection_data.get("refresh_token"),
                        token_expires=connection_data.get("token_expires"),
                        metadata=connection_data.get("metadata", {})
                    )
                    
                    db.add(connection)
                    await db.commit()
                    await db.refresh(connection)
                    
                    return ConnectionResponse(
                        connection_id=connection.connection_id,
                        platform=platform,
                        status=connection_data["status"],
                        created_at=connection.created_at,
                        expires_at=connection.token_expires
                    )
                    
        except Exception as e:
            logger.error(f"Failed to store connection for {platform}: {str(e)}")
            raise DatabaseError(f"Connection storage failed", {"platform": platform, "error": str(e)})
    
    async def disconnect_platform(
        self,
        team_id: UUID,
        platform: str,
        connection_id: UUID
    ) -> bool:
        """Disconnect platform and update status"""
        
        try:
            async with get_session() as db:
                stmt = update(SocialConnection).where(
                    SocialConnection.connection_id == connection_id,
                    SocialConnection.team_id == team_id,
                    SocialConnection.platform == platform
                ).values(
                    status="disconnected",
                    updated_at=datetime.utcnow()
                )
                
                result = await db.execute(stmt)
                await db.commit()
                
                return result.rowcount > 0
                
        except Exception as e:
            logger.error(f"Failed to disconnect {platform}: {str(e)}")
            raise DatabaseError(f"Disconnection failed", {"platform": platform, "error": str(e)})


# Global connection manager
connection_manager = ConnectionManager()
