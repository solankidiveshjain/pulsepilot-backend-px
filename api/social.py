"""
Social media platform connection endpoints - Refactored
"""

from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from models.database import SocialConnection, Team
from utils.database import get_db
from utils.auth import get_current_team
from services.platforms.registry import get_platform_service
from services.platforms.base import ConnectionConfig
from schemas.requests import ConnectionRequest
from schemas.responses import ConnectionResponse
from utils.exceptions import handle_platform_error, PlatformError

router = APIRouter()


@router.post("/{team_id}/platforms/{platform}/connections", response_model=ConnectionResponse)
async def connect_platform(
    team_id: UUID,
    platform: str,
    request: ConnectionRequest,
    db: AsyncSession = Depends(get_db),
    current_team: Team = Depends(get_current_team)
) -> ConnectionResponse:
    """Connect to a social media platform"""
    
    # Verify team access
    if current_team.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to team"
        )
    
    try:
        # Get platform service
        platform_service = get_platform_service(platform)
        
        # Create connection config
        config = ConnectionConfig(
            access_token=request.access_token,
            refresh_token=request.refresh_token,
            token_expires=request.token_expires.isoformat() if request.token_expires else None
        )
        
        # Connect to platform
        connection_data = await platform_service.connect(team_id, config)
        
        # Check if connection already exists
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
                token_expires=datetime.fromisoformat(connection_data["token_expires"]) if connection_data.get("token_expires") else None,
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
                created_at=existing_connection.created_at
            )
        else:
            # Create new connection
            connection = SocialConnection(
                team_id=team_id,
                platform=platform,
                status=connection_data["status"],
                access_token=connection_data["access_token"],
                refresh_token=connection_data.get("refresh_token"),
                token_expires=datetime.fromisoformat(connection_data["token_expires"]) if connection_data.get("token_expires") else None,
                metadata=connection_data.get("metadata", {})
            )
            
            db.add(connection)
            await db.commit()
            await db.refresh(connection)
            
            return ConnectionResponse(
                connection_id=connection.connection_id,
                platform=platform,
                status=connection_data["status"],
                created_at=connection.created_at
            )
            
    except Exception as e:
        raise handle_platform_error(e, platform)


@router.delete("/{team_id}/platforms/{platform}/connections/{connection_id}")
async def disconnect_platform(
    team_id: UUID,
    platform: str,
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_team: Team = Depends(get_current_team)
):
    """Disconnect a social media platform"""
    
    # Verify team access
    if current_team.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to team"
        )
    
    try:
        # Get platform service
        platform_service = get_platform_service(platform)
        
        # Find connection
        stmt = select(SocialConnection).where(
            SocialConnection.connection_id == connection_id,
            SocialConnection.team_id == team_id,
            SocialConnection.platform == platform
        )
        result = await db.execute(stmt)
        connection = result.scalar_one_or_none()
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found"
            )
        
        # Disconnect from platform
        await platform_service.disconnect(team_id, connection_id)
        
        # Revoke token if possible
        try:
            await platform_service.revoke_token(connection.access_token)
        except Exception:
            # Continue even if revocation fails
            pass
        
        # Update connection status
        stmt = update(SocialConnection).where(
            SocialConnection.connection_id == connection_id
        ).values(
            status="disconnected",
            updated_at=datetime.utcnow()
        )
        await db.execute(stmt)
        await db.commit()
        
        return {"message": "Platform disconnected successfully"}
        
    except Exception as e:
        raise handle_platform_error(e, platform)
