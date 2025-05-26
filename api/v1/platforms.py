"""
RESTful platform management endpoints
"""

from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Team
from utils.database import get_db
from utils.auth import get_current_team
from services.platforms.registry import get_platform_service
from services.platforms.base import OnboardingConfig, ConnectionConfig
from schemas.requests import OnboardingRequest, TokenExchangeRequest, ConnectionRequest
from schemas.responses import OnboardingResponse, ConnectionResponse
from utils.exceptions import handle_platform_error

router = APIRouter()


@router.get("/", response_model=List[str])
async def list_platforms():
    """List all supported platforms"""
    from services.platforms.registry import platform_registry
    return platform_registry.list_platforms()


@router.post("/{platform}/onboard", response_model=OnboardingResponse)
async def start_platform_onboarding(
    platform: str,
    request: OnboardingRequest,
    current_team: Team = Depends(get_current_team)
) -> OnboardingResponse:
    """Start OAuth onboarding flow for a platform"""
    
    try:
        platform_service = get_platform_service(platform)
        
        config = OnboardingConfig(
            client_id=getattr(platform_service.config, f"{platform}_client_id"),
            client_secret=getattr(platform_service.config, f"{platform}_client_secret"),
            redirect_uri=request.redirect_uri,
            scopes=request.scopes
        )
        
        response = await platform_service.get_onboarding_url(current_team.team_id, config)
        return response
        
    except Exception as e:
        raise handle_platform_error(e, platform)


@router.post("/{platform}/connect", response_model=ConnectionResponse)
async def connect_platform(
    platform: str,
    request: TokenExchangeRequest,
    current_team: Team = Depends(get_current_team)
) -> ConnectionResponse:
    """Complete platform connection using OAuth code"""
    
    try:
        platform_service = get_platform_service(platform)
        
        # Let platform service handle the entire connection process
        connection_response = await platform_service.complete_connection(
            team_id=current_team.team_id,
            auth_code=request.code,
            state=request.state
        )
        
        return connection_response
        
    except Exception as e:
        raise handle_platform_error(e, platform)


@router.get("/{platform}/connections", response_model=List[ConnectionResponse])
async def list_platform_connections(
    platform: str,
    db: AsyncSession = Depends(get_db),
    current_team: Team = Depends(get_current_team)
) -> List[ConnectionResponse]:
    """List all connections for a platform"""
    
    from sqlalchemy import select
    from models.database import SocialConnection
    
    stmt = select(SocialConnection).where(
        SocialConnection.team_id == current_team.team_id,
        SocialConnection.platform == platform
    )
    result = await db.execute(stmt)
    connections = result.scalars().all()
    
    return [
        ConnectionResponse(
            connection_id=conn.connection_id,
            platform=conn.platform,
            status=conn.status,
            created_at=conn.created_at,
            expires_at=conn.token_expires
        )
        for conn in connections
    ]


@router.delete("/{platform}/connections/{connection_id}")
async def disconnect_platform(
    platform: str,
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_team: Team = Depends(get_current_team)
):
    """Disconnect from a platform"""
    
    try:
        platform_service = get_platform_service(platform)
        
        # Find and disconnect
        from sqlalchemy import select, update
        from models.database import SocialConnection
        from datetime import datetime
        
        stmt = select(SocialConnection).where(
            SocialConnection.connection_id == connection_id,
            SocialConnection.team_id == current_team.team_id,
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
        await platform_service.disconnect(current_team.team_id, connection_id)
        
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
