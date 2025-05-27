"""
YouTube platform service implementation
"""

from typing import Dict, Any, List, Optional
from uuid import UUID
from utils.http_client import get_async_client

from .base import BasePlatformService, ConnectionConfig, WebhookPayload, CommentData
from utils.config import get_config
from utils.social_settings import get_social_media_settings
from .base import OnboardingConfig
from datetime import datetime, timedelta
import asyncio


class YouTubeService(BasePlatformService):
    """YouTube Data API v3 service implementation"""
    
    def __init__(self):
        self.base_url = "https://www.googleapis.com/youtube/v3"
        self.client = get_async_client()
        # Load configuration with fallback to None for testing
        try:
            self.config = get_config()
        except Exception:
            self.config = None
        # OAuth onboarding config
        self._oauth_config: Optional[OnboardingConfig] = None
    
    @property
    def platform_name(self) -> str:
        return "youtube"
    
    async def connect_team(self, team_id: UUID, config: ConnectionConfig) -> Dict[str, Any]:
        """Connect team to YouTube"""
        is_valid = await self.validate_token(config.access_token)
        if not is_valid:
            raise ValueError("Invalid YouTube access token")
        
        return {
            "platform": self.platform_name,
            "status": "connected",
            "access_token": config.access_token,
            "refresh_token": config.refresh_token,
            "token_expires": config.token_expires,
            "metadata": config.metadata or {}
        }
    
    async def disconnect_team(self, team_id: UUID, connection_id: UUID) -> bool:
        """Disconnect team from YouTube"""
        return True
    
    async def process_webhook(self, payload: WebhookPayload) -> List[CommentData]:
        """Process YouTube webhook and extract comments"""
        comments = []
        
        if "comment" in payload.json_data:
            comment_info = payload.json_data["comment"]
            comment = CommentData(
                external_id=comment_info.get("id", ""),
                author=comment_info.get("authorDisplayName"),
                message=comment_info.get("textDisplay"),
                post_id=comment_info.get("videoId"),
                platform_metadata={
                    "youtube_data": comment_info
                }
            )
            comments.append(comment)
        
        return comments
    
    async def validate_token(self, access_token: str) -> bool:
        """Validate YouTube access token"""
        try:
            response = await self.client.get(
                f"{self.base_url}/channels",
                params={
                    "part": "id",
                    "mine": "true",
                    "access_token": access_token
                }
            )
            return response.status_code == 200
        except Exception:
            return False
    
    async def revoke_token(self, access_token: str) -> bool:
        """Revoke YouTube access token"""
        try:
            response = await self.client.post(
                "https://oauth2.googleapis.com/revoke",
                data={"token": access_token}
            )
            return response.status_code == 200
        except Exception:
            return False
    
    async def post_reply(self, comment_id: str, message: str, access_token: str) -> Dict[str, Any]:
        """Post reply to YouTube comment"""
        response = await self.client.post(
            f"{self.base_url}/comments",
            params={"access_token": access_token},
            json={
                "snippet": {
                    "parentId": comment_id,
                    "textOriginal": message
                }
            }
        )
        response.raise_for_status()
        return response.json()

    async def verify_webhook_signature(self, body: bytes, headers: Dict[str, str]) -> bool:
        """YouTube webhook signature verification is not required (always true)"""
        return True

    # Alias validate_connection to validate_token
    validate_connection = validate_token

    async def get_onboarding_url(self, team_id: UUID, config: OnboardingConfig) -> Dict[str, Any]:
        """Generate Google OAuth2 authorization URL for YouTube"""
        self._oauth_config = config
        state = str(team_id)
        scope_str = ' '.join(config.scopes)
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={config.client_id}"
            f"&redirect_uri={config.redirect_uri}"
            f"&response_type=code"
            f"&scope={scope_str}"
            f"&access_type=offline"
            f"&state={state}"
        )
        return {'auth_url': auth_url, 'state': state, 'platform': self.platform_name}

    async def exchange_auth_code(self, auth_code: str, state: str) -> ConnectionConfig:
        """Exchange Google OAuth2 code for tokens"""
        if not self._oauth_config:
            raise RuntimeError('OAuth config missing for YouTube code exchange')
        data = {
            'code': auth_code,
            'client_id': self._oauth_config.client_id,
            'client_secret': self._oauth_config.client_secret,
            'redirect_uri': self._oauth_config.redirect_uri,
            'grant_type': 'authorization_code'
        }
        resp = await self.client.post(
            'https://oauth2.googleapis.com/token',
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        resp.raise_for_status()
        token_data = resp.json()
        access = token_data.get('access_token')
        refresh = token_data.get('refresh_token')
        expires_in = token_data.get('expires_in')
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in) if expires_in else None
        return ConnectionConfig(
            access_token=access,
            refresh_token=refresh,
            token_expires=expires_at,
            metadata=token_data
        )

    async def refresh_token(self, refresh_token: str) -> ConnectionConfig:
        """Refresh YouTube OAuth2 tokens using refresh_token grant"""
        if not self._oauth_config:
            raise RuntimeError('OAuth config missing for YouTube refresh')
        data = {
            'client_id': self._oauth_config.client_id,
            'client_secret': self._oauth_config.client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }
        resp = await self.client.post(
            'https://oauth2.googleapis.com/token',
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        resp.raise_for_status()
        token_data = resp.json()
        access = token_data.get('access_token')
        expires_in = token_data.get('expires_in')
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in) if expires_in else None
        return ConnectionConfig(
            access_token=access,
            refresh_token=token_data.get('refresh_token', refresh_token),
            token_expires=expires_at,
            metadata=token_data
        )
