"""
Social media platform connection endpoints
"""

from uuid import UUID
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel

from models.database import SocialConnection, Team
from utils.database import get_db
from utils.auth import get_current_team
from services.social_platforms import get_platform_service


router = APIRouter()


class ConnectionRequest(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_expires: Optional[datetime] = None


class ConnectionResponse(BaseModel):
    connection_id: UUID
    platform: str
    status: str
    created_at: datetime


@router.post("/{team_id}/platforms/{platform}/connections")
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
    
    # Validate platform
    platform_service = get_platform_service(platform)
    if not platform_service:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported platform: {platform}"
        )
    
    # Validate token with platform
    try:
        is_valid = await platform_service.validate_token(request.access_token)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid access token"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Token validation failed: {str(e)}"
        )
    
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
            access_token=request.access_token,
            refresh_token=request.refresh_token,
            token_expires=request.token_expires,
            status="connected",
            updated_at=datetime.utcnow()
        )
        await db.execute(stmt)
        await db.commit()
        
        return ConnectionResponse(
            connection_id=existing_connection.connection_id,
            platform=platform,
            status="connected",
            created_at=existing_connection.created_at
        )
    else:
        # Create new connection
        connection = SocialConnection(
            team_id=team_id,
            platform=platform,
            status="connected",
            access_token=request.access_token,
            refresh_token=request.refresh_token,
            token_expires=request.token_expires
        )
        
        db.add(connection)
        await db.commit()
        await db.refresh(connection)
        
        return ConnectionResponse(
            connection_id=connection.connection_id,
            platform=platform,
            status="connected",
            created_at=connection.created_at
        )


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
    
    # Get platform service and revoke token if possible
    platform_service = get_platform_service(platform)
    if platform_service:
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
