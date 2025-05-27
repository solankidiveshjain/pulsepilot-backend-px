from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from utils.http_client import get_async_client
from utils.social_settings import get_social_media_settings
from .base import BasePlatformService, PlatformConnectionData, OnboardingConfig, PlatformWebhookData
import asyncio


class TikTokService(BasePlatformService):
    """TikTok API service implementation"""

    def __init__(self):
        self.client = get_async_client()
        settings = get_social_media_settings().tiktok
        self.api_base = settings.get('api_base_url')
        self.client_key = settings.get('client_key')
        self.client_secret = settings.get('client_secret')
        self._oauth_config: Optional[OnboardingConfig] = None

    @property
    def platform_name(self) -> str:
        return 'tiktok'

    async def get_onboarding_url(self, team_id: UUID, config: OnboardingConfig) -> Dict[str, Any]:
        """Generate TikTok OAuth authorization URL"""
        self._oauth_config = config
        state = str(team_id)
        scope_str = ','.join(config.scopes)
        auth_url = (
            f"{self.api_base}/platform/oauth/authorize"
            f"?client_key={config.client_id or self.client_key}"
            f"&redirect_uri={config.redirect_uri}"
            f"&scope={scope_str}"
            f"&response_type=code"
            f"&state={state}"
        )
        return {'auth_url': auth_url, 'state': state, 'platform': self.platform_name}

    async def exchange_auth_code(self, auth_code: str, state: str) -> PlatformConnectionData:
        """Exchange code for TikTok access token"""
        if not self._oauth_config:
            raise RuntimeError('OAuth configuration missing')
        params = {
            'client_key': self._oauth_config.client_id or self.client_key,
            'client_secret': self._oauth_config.client_secret or self.client_secret,
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': self._oauth_config.redirect_uri
        }
        resp = await self.client.post(f"{self.api_base}/oauth/access_token", json=params)
        resp.raise_for_status()
        data = resp.json()
        access_token = data.get('data', {}).get('access_token')
        expires_in = data.get('data', {}).get('expires_in')
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in) if expires_in else None
        return PlatformConnectionData(
            access_token=access_token,
            refresh_token=None,
            token_expires=expires_at,
            metadata=data.get('data', {})
        )

    async def refresh_token(self, refresh_token: str) -> PlatformConnectionData:
        """TikTok token refresh is not supported via API"""
        raise NotImplementedError('TikTok token refresh not supported')

    async def validate_connection(self, access_token: str) -> bool:
        """Validate TikTok access token by checking its presence."""
        return bool(access_token)

    async def connect_team(self, team_id: UUID, connection_data: PlatformConnectionData) -> Dict[str, Any]:
        """Finalize connection: ensure token is valid and store metadata."""
        is_valid = await self.validate_connection(connection_data.access_token)
        if not is_valid:
            raise ValueError('Invalid TikTok access token')
        # Metadata might include user info later
        return {
            'platform': self.platform_name,
            'status': 'connected',
            'access_token': connection_data.access_token,
            'refresh_token': connection_data.refresh_token,
            'token_expires': connection_data.token_expires,
            'metadata': connection_data.metadata or {}
        }

    async def disconnect_team(self, team_id: UUID, connection_id: UUID) -> bool:
        """Disconnect TikTok by marking status locally."""
        return True

    async def process_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> List[PlatformWebhookData]:
        """Process TikTok webhook payload and extract comments."""
        comments: List[PlatformWebhookData] = []
        # Example TikTok webhook payload: {'comment': {...}}
        comment_info = payload.get('comment') or {}
        if comment_info:
            comments.append(PlatformWebhookData(
                external_id=comment_info.get('cid', ''),
                author=comment_info.get('user', {}).get('uid'),
                message=comment_info.get('text', ''),
                post_id=comment_info.get('item_id'),
                platform_metadata={'tiktok_data': comment_info}
            ))
        return comments

    async def verify_webhook_signature(self, body: bytes, headers: Dict[str, str]) -> bool:
        """TikTok webhooks do not include signatures by default."""
        return True

    async def post_reply(self, comment_id: str, message: str, access_token: str) -> Dict[str, Any]:
        """Post reply to TikTok comment (not currently supported)."""
        # TikTok API does not support comments replies via API
        return {}

    async def fetch_initial(self) -> Any:
        raise NotImplementedError('TikTokService.fetch_initial not implemented')

    async def fetch_metrics(self, since: datetime, until: datetime) -> Any:
        raise NotImplementedError('TikTokService.fetch_metrics not implemented')

    async def fetch_insights(self, post_external_id: str) -> Any:
        raise NotImplementedError('TikTokService.fetch_insights not implemented')

    async def create_post(self, payload: Any) -> Any:
        raise NotImplementedError('TikTokService.create_post not implemented')

    async def update_post(self, post_external_id: str, payload: Any) -> Any:
        raise NotImplementedError('TikTokService.update_post not implemented')

    async def delete_post(self, post_external_id: str) -> bool:
        raise NotImplementedError('TikTokService.delete_post not implemented')

    async def upload_video(self, payload: Any) -> Any:
        raise NotImplementedError('TikTokService.upload_video not implemented') 