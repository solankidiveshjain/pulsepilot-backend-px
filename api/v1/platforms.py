"""
RESTful platform management endpoints
"""

from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Team
from utils.database import get_db
from utils.auth import get_current_team
from services.platforms.registry import get_platform_service
from services.platforms.base import OnboardingConfig, ConnectionConfig
from schemas.requests import OnboardingRequest, TokenExchangeRequest, ConnectionRequest
from schemas.responses import OnboardingResponse, ConnectionResponse
from utils.exceptions import handle_platform_error
from services.platforms.initial_sync import initial_sync_social
from services.platforms.connectors import get_connector
from schemas.social_media import MetricsData, InsightsData, PostCreate, PostUpdate, VideoUpload, PostData as SMPostData
from models.database import SocialConnection
from utils.social_settings import get_social_media_settings

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
        # Load client credentials and default scopes from YAML config
        sm_settings = get_social_media_settings()
        plat_conf = getattr(sm_settings, platform)
        # Map platform-specific keys
        if platform == 'twitter':
            client_id = plat_conf['api_key']
            client_secret = plat_conf['api_key_secret']
        elif platform == 'tiktok':
            client_id = plat_conf['client_key']
            client_secret = plat_conf['client_secret']
        else:
            client_id = plat_conf['client_id']
            client_secret = plat_conf['client_secret']
        scopes = request.scopes or plat_conf.get('default_scopes', [])
        config = OnboardingConfig(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=request.redirect_uri,
            scopes=scopes
        )
        
        response = await platform_service.get_onboarding_url(current_team.team_id, config)
        return response
        
    except Exception as e:
        raise handle_platform_error(e, platform)


@router.post("/{platform}/connect", response_model=ConnectionResponse)
async def connect_platform(
    platform: str,
    request: TokenExchangeRequest,
    background_tasks: BackgroundTasks,
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
        # Schedule initial sync of posts/comments in background
        background_tasks.add_task(
            initial_sync_social,
            connection_response.connection_id
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
        
        # Revoke token on platform and disconnect
        # Revoke access token
        await platform_service.revoke_token(connection.access_token)
        # Perform platform-specific disconnect logic
        await platform_service.disconnect_team(current_team.team_id, connection_id)
        
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


# Analytics endpoints for social platforms
@router.get("/{platform}/connections/{connection_id}/metrics", response_model=MetricsData)
async def get_platform_metrics(
    platform: str,
    connection_id: UUID,
    since: datetime = Query(..., description="Start of time range"),
    until: datetime = Query(..., description="End of time range"),
    db: AsyncSession = Depends(get_db),
    current_team: Team = Depends(get_current_team)
) -> MetricsData:
    # Load connection
    stmt = select(SocialConnection).where(
        SocialConnection.connection_id == connection_id,
        SocialConnection.team_id == current_team.team_id,
        SocialConnection.platform == platform
    )
    result = await db.execute(stmt)
    connection = result.scalar_one_or_none()
    if not connection or connection.status != "connected":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found or not connected")
    # Auto-refresh token if expired
    from datetime import datetime
    from sqlalchemy import update
    if connection.token_expires and connection.token_expires <= datetime.utcnow():
        svc = get_platform_service(platform)
        try:
            refreshed = await svc.refresh_token(connection.refresh_token or connection.access_token)
            # Persist refreshed tokens
            upd = update(SocialConnection).where(
                SocialConnection.connection_id == connection_id
            ).values(
                access_token=refreshed.access_token,
                refresh_token=refreshed.refresh_token,
                token_expires=refreshed.token_expires,
                updated_at=datetime.utcnow()
            )
            await db.execute(upd)
            await db.commit()
            # Update in-memory
            connection.access_token = refreshed.access_token
            connection.refresh_token = refreshed.refresh_token
            connection.token_expires = refreshed.token_expires
        except NotImplementedError:
            pass
        except Exception:
            pass
    # Fetch metrics
    connector = get_connector(platform, connection)
    if not connector:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported platform")
    return await connector.fetch_metrics(since, until)

@router.get("/{platform}/connections/{connection_id}/posts/{post_id}/insights", response_model=InsightsData)
async def get_post_insights(
    platform: str,
    connection_id: UUID,
    post_id: str,
    db: AsyncSession = Depends(get_db),
    current_team: Team = Depends(get_current_team)
) -> InsightsData:
    stmt = select(SocialConnection).where(
        SocialConnection.connection_id == connection_id,
        SocialConnection.team_id == current_team.team_id,
        SocialConnection.platform == platform
    )
    result = await db.execute(stmt)
    connection = result.scalar_one_or_none()
    if not connection or connection.status != "connected":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found or not connected")
    # Auto-refresh token if expired
    from datetime import datetime
    from sqlalchemy import update
    if connection.token_expires and connection.token_expires <= datetime.utcnow():
        svc = get_platform_service(platform)
        try:
            refreshed = await svc.refresh_token(connection.refresh_token or connection.access_token)
            upd = update(SocialConnection).where(
                SocialConnection.connection_id == connection_id
            ).values(
                access_token=refreshed.access_token,
                refresh_token=refreshed.refresh_token,
                token_expires=refreshed.token_expires,
                updated_at=datetime.utcnow()
            )
            await db.execute(upd)
            await db.commit()
            connection.access_token = refreshed.access_token
            connection.refresh_token = refreshed.refresh_token
            connection.token_expires = refreshed.token_expires
        except NotImplementedError:
            pass
        except Exception:
            pass
    connector = get_connector(platform, connection)
    if not connector:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported platform")
    return await connector.fetch_insights(post_id)

@router.post("/{platform}/connections/{connection_id}/posts", response_model=SMPostData)
async def create_platform_post(
    platform: str,
    connection_id: UUID,
    payload: PostCreate,
    db: AsyncSession = Depends(get_db),
    current_team: Team = Depends(get_current_team)
) -> SMPostData:
    # Validate connection
    stmt = select(SocialConnection).where(
        SocialConnection.connection_id == connection_id,
        SocialConnection.team_id == current_team.team_id,
        SocialConnection.platform == platform
    )
    result = await db.execute(stmt)
    connection = result.scalar_one_or_none()
    if not connection or connection.status != "connected":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found or not connected")
    # Auto-refresh token if expired
    from datetime import datetime
    from sqlalchemy import update
    if connection.token_expires and connection.token_expires <= datetime.utcnow():
        svc = get_platform_service(platform)
        try:
            refreshed = await svc.refresh_token(connection.refresh_token or connection.access_token)
            upd = update(SocialConnection).where(
                SocialConnection.connection_id == connection_id
            ).values(
                access_token=refreshed.access_token,
                refresh_token=refreshed.refresh_token,
                token_expires=refreshed.token_expires,
                updated_at=datetime.utcnow()
            )
            await db.execute(upd)
            await db.commit()
            connection.access_token = refreshed.access_token
            connection.refresh_token = refreshed.refresh_token
            connection.token_expires = refreshed.token_expires
        except NotImplementedError:
            pass
        except Exception:
            pass
    connector = get_connector(platform, connection)
    if not connector:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported platform")
    return await connector.create_post(payload)

@router.patch("/{platform}/connections/{connection_id}/posts/{post_id}", response_model=SMPostData)
async def update_platform_post(
    platform: str,
    connection_id: UUID,
    post_id: str,
    payload: PostUpdate,
    db: AsyncSession = Depends(get_db),
    current_team: Team = Depends(get_current_team)
) -> SMPostData:
    stmt = select(SocialConnection).where(
        SocialConnection.connection_id == connection_id,
        SocialConnection.team_id == current_team.team_id,
        SocialConnection.platform == platform
    )
    result = await db.execute(stmt)
    connection = result.scalar_one_or_none()
    if not connection or connection.status != "connected":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found or not connected")
    # Auto-refresh token if expired
    from datetime import datetime
    from sqlalchemy import update
    if connection.token_expires and connection.token_expires <= datetime.utcnow():
        svc = get_platform_service(platform)
        try:
            refreshed = await svc.refresh_token(connection.refresh_token or connection.access_token)
            upd = update(SocialConnection).where(
                SocialConnection.connection_id == connection_id
            ).values(
                access_token=refreshed.access_token,
                refresh_token=refreshed.refresh_token,
                token_expires=refreshed.token_expires,
                updated_at=datetime.utcnow()
            )
            await db.execute(upd)
            await db.commit()
            connection.access_token = refreshed.access_token
            connection.refresh_token = refreshed.refresh_token
            connection.token_expires = refreshed.token_expires
        except NotImplementedError:
            pass
        except Exception:
            pass
    connector = get_connector(platform, connection)
    if not connector:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported platform")
    return await connector.update_post(post_id, payload)

@router.delete("/{platform}/connections/{connection_id}/posts/{post_id}")
async def delete_platform_post(
    platform: str,
    connection_id: UUID,
    post_id: str,
    db: AsyncSession = Depends(get_db),
    current_team: Team = Depends(get_current_team)
) -> dict:
    stmt = select(SocialConnection).where(
        SocialConnection.connection_id == connection_id,
        SocialConnection.team_id == current_team.team_id,
        SocialConnection.platform == platform
    )
    result = await db.execute(stmt)
    connection = result.scalar_one_or_none()
    if not connection or connection.status != "connected":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found or not connected")
    # Auto-refresh token if expired
    from datetime import datetime
    from sqlalchemy import update
    if connection.token_expires and connection.token_expires <= datetime.utcnow():
        svc = get_platform_service(platform)
        try:
            refreshed = await svc.refresh_token(connection.refresh_token or connection.access_token)
            upd = update(SocialConnection).where(
                SocialConnection.connection_id == connection_id
            ).values(
                access_token=refreshed.access_token,
                refresh_token=refreshed.refresh_token,
                token_expires=refreshed.token_expires,
                updated_at=datetime.utcnow()
            )
            await db.execute(upd)
            await db.commit()
            connection.access_token = refreshed.access_token
            connection.refresh_token = refreshed.refresh_token
            connection.token_expires = refreshed.token_expires
        except NotImplementedError:
            pass
        except Exception:
            pass
    connector = get_connector(platform, connection)
    if not connector:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported platform")
    success = await connector.delete_post(post_id)
    return {"success": success}

@router.post("/{platform}/connections/{connection_id}/videos", response_model=SMPostData)
async def upload_platform_video(
    platform: str,
    connection_id: UUID,
    payload: VideoUpload,
    db: AsyncSession = Depends(get_db),
    current_team: Team = Depends(get_current_team)
) -> SMPostData:
    stmt = select(SocialConnection).where(
        SocialConnection.connection_id == connection_id,
        SocialConnection.team_id == current_team.team_id,
        SocialConnection.platform == platform
    )
    result = await db.execute(stmt)
    connection = result.scalar_one_or_none()
    if not connection or connection.status != "connected":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found or not connected")
    # Auto-refresh token if expired
    from datetime import datetime
    from sqlalchemy import update
    if connection.token_expires and connection.token_expires <= datetime.utcnow():
        svc = get_platform_service(platform)
        try:
            refreshed = await svc.refresh_token(connection.refresh_token or connection.access_token)
            upd = update(SocialConnection).where(
                SocialConnection.connection_id == connection_id
            ).values(
                access_token=refreshed.access_token,
                refresh_token=refreshed.refresh_token,
                token_expires=refreshed.token_expires,
                updated_at=datetime.utcnow()
            )
            await db.execute(upd)
            await db.commit()
            connection.access_token = refreshed.access_token
            connection.refresh_token = refreshed.refresh_token
            connection.token_expires = refreshed.token_expires
        except NotImplementedError:
            pass
        except Exception:
            pass
    connector = get_connector(platform, connection)
    if not connector:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported platform")
    return await connector.upload_video(payload)

# Added endpoint to revoke a platform token and disconnect
@router.post("/{platform}/connections/{connection_id}/revoke")
async def revoke_platform_token(
    platform: str,
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_team: Team = Depends(get_current_team)
):
    """Revoke platform access token and disconnect"""
    from sqlalchemy import select, update
    from models.database import SocialConnection
    from datetime import datetime

    # Find connection
    stmt = select(SocialConnection).where(
        SocialConnection.connection_id == connection_id,
        SocialConnection.team_id == current_team.team_id,
        SocialConnection.platform == platform
    )
    result = await db.execute(stmt)
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    platform_service = get_platform_service(platform)
    revoked = await platform_service.revoke_token(connection.access_token)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token revocation failed")
    # Update status to disconnected
    stmt = update(SocialConnection).where(
        SocialConnection.connection_id == connection_id
    ).values(status="disconnected", updated_at=datetime.utcnow())
    await db.execute(stmt)
    await db.commit()
    return {"message": "Token revoked and disconnected successfully"}

# Added endpoint to manually update connection tokens
@router.patch("/{platform}/connections/{connection_id}/token", response_model=ConnectionResponse)
async def update_connection_token(
    platform: str,
    connection_id: UUID,
    payload: ConnectionRequest,
    db: AsyncSession = Depends(get_db),
    current_team: Team = Depends(get_current_team)
) -> ConnectionResponse:
    """Update platform access and refresh tokens"""
    from sqlalchemy import select, update
    from models.database import SocialConnection

    stmt = select(SocialConnection).where(
        SocialConnection.connection_id == connection_id,
        SocialConnection.team_id == current_team.team_id,
        SocialConnection.platform == platform
    )
    result = await db.execute(stmt)
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    # Update tokens
    stmt = update(SocialConnection).where(
        SocialConnection.connection_id == connection_id
    ).values(
        access_token=payload.access_token,
        refresh_token=payload.refresh_token,
        token_expires=payload.token_expires,
        updated_at=datetime.utcnow()
    )
    await db.execute(stmt)
    await db.commit()
    return ConnectionResponse(
        connection_id=connection.connection_id,
        platform=connection.platform,
        status=connection.status,
        created_at=connection.created_at,
        expires_at=payload.token_expires
    )
