from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from utils.http_client import get_async_client
from utils.social_settings import get_social_media_settings
from .base import BasePlatformService, PlatformConnectionData, OnboardingConfig, PlatformWebhookData
from facebook import GraphAPI, GraphAPIError
import hmac
import hashlib
import asyncio


class FacebookService(BasePlatformService):
    """Facebook Graph API service implementation"""

    def __init__(self):
        self.client = get_async_client()
        settings = get_social_media_settings().facebook
        self.api_base = settings.get('api_base_url')
        # Placeholder for OAuth onboarding config
        self._oauth_config: Optional[OnboardingConfig] = None

    @property
    def platform_name(self) -> str:
        return 'facebook'

    async def get_onboarding_url(self, team_id: UUID, config: OnboardingConfig) -> Dict[str, Any]:
        """Generate Facebook OAuth authorization URL"""
        self._oauth_config = config
        state = str(team_id)
        scope_str = ','.join(config.scopes)
        auth_url = (
            f"https://www.facebook.com/v12.0/dialog/oauth"
            f"?client_id={config.client_id}"
            f"&redirect_uri={config.redirect_uri}"
            f"&scope={scope_str}"
            f"&state={state}"
        )
        return {'auth_url': auth_url, 'state': state, 'platform': self.platform_name}

    async def exchange_auth_code(self, auth_code: str, state: str) -> PlatformConnectionData:
        """Exchange code for Facebook access token (short and long lived)"""
        if not self._oauth_config:
            raise RuntimeError('OAuth configuration missing')
        # Step 1: short-lived token
        params = {
            'client_id': self._oauth_config.client_id,
            'redirect_uri': self._oauth_config.redirect_uri,
            'client_secret': self._oauth_config.client_secret,
            'code': auth_code
        }
        resp = await self.client.get(f"{self.api_base}/oauth/access_token", params=params)
        resp.raise_for_status()
        data = resp.json()
        short_token = data.get('access_token')
        # Step 2: exchange for long-lived token
        params2 = {
            'grant_type': 'fb_exchange_token',
            'client_id': self._oauth_config.client_id,
            'client_secret': self._oauth_config.client_secret,
            'fb_exchange_token': short_token
        }
        resp2 = await self.client.get(f"{self.api_base}/oauth/access_token", params=params2)
        resp2.raise_for_status()
        long_data = resp2.json()
        access_token = long_data.get('access_token')
        expires_in = long_data.get('expires_in')
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in) if expires_in else None
        metadata = {**data, **long_data}
        return PlatformConnectionData(
            access_token=access_token,
            refresh_token=None,
            token_expires=expires_at,
            metadata=metadata
        )

    async def refresh_token(self, refresh_token: str) -> PlatformConnectionData:
        """Refresh Facebook long-lived token using fb_exchange_token grant"""
        if not self._oauth_config:
            raise RuntimeError('OAuth configuration missing')
        # Use existing token as fb_exchange_token
        params = {
            'grant_type': 'fb_exchange_token',
            'client_id': self._oauth_config.client_id,
            'client_secret': self._oauth_config.client_secret,
            'fb_exchange_token': refresh_token
        }
        resp = await self.client.get(f"{self.api_base}/oauth/access_token", params=params)
        resp.raise_for_status()
        data = resp.json()
        access_token = data.get('access_token')
        expires_in = data.get('expires_in')
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in) if expires_in else None
        return PlatformConnectionData(
            access_token=access_token,
            refresh_token=None,
            token_expires=expires_at,
            metadata=data
        )

    async def validate_connection(self, access_token: str) -> bool:
        """Validate Facebook access token by fetching the profile."""
        graph = GraphAPI(access_token=access_token, version='12.0')
        try:
            # Use a thread for sync SDK call
            await asyncio.to_thread(graph.get_object, 'me', fields='id')
            return True
        except GraphAPIError:
            return False

    async def connect_team(self, team_id: UUID, connection_data: PlatformConnectionData) -> Dict[str, Any]:
        """Finalize connection: validate token and fetch profile data."""
        is_valid = await self.validate_connection(connection_data.access_token)
        if not is_valid:
            raise ValueError('Invalid Facebook access token')
        graph = GraphAPI(access_token=connection_data.access_token, version='12.0')
        try:
            profile = await asyncio.to_thread(graph.get_object, 'me', fields='id,name')
        except GraphAPIError:
            profile = {}
        return {
            'platform': self.platform_name,
            'status': 'connected',
            'access_token': connection_data.access_token,
            'refresh_token': connection_data.refresh_token,
            'token_expires': connection_data.token_expires,
            'metadata': profile
        }

    async def disconnect_team(self, team_id: UUID, connection_id: UUID) -> bool:
        """Disconnect by simply revoking local status (Facebook token revocation is not supported)."""
        return True

    async def process_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> List[PlatformWebhookData]:
        """Parse Facebook page webhook events into standardized comment data."""
        comments: List[PlatformWebhookData] = []
        for entry in payload.get('entry', []):
            for change in entry.get('changes', []):
                if change.get('field') == 'feed':
                    val = change.get('value', {})
                    if val.get('item') == 'comment':
                        comments.append(PlatformWebhookData(
                            external_id=val.get('comment_id', ''),
                            author=val.get('sender_name'),
                            message=val.get('message', ''),
                            post_id=val.get('post_id'),
                            platform_metadata={'facebook_data': val}
                        ))
        return comments

    async def verify_webhook_signature(self, body: bytes, headers: Dict[str, str]) -> bool:
        """Verify Facebook webhook signature using app secret."""
        signature = headers.get('x-hub-signature-256', '')
        if not signature or not self._oauth_config:
            return False
        secret = self._oauth_config.client_secret
        expected = 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)

    async def post_reply(self, comment_id: str, message: str, access_token: str) -> Dict[str, Any]:
        """Post a reply to a Facebook comment."""
        graph = GraphAPI(access_token=access_token, version='16.0')
        result = await asyncio.to_thread(graph.put_object, comment_id, 'comments', message=message)
        return result

    async def fetch_initial(self) -> Any:
        raise NotImplementedError('FacebookService.fetch_initial not implemented')

    async def fetch_metrics(self, since: datetime, until: datetime) -> Any:
        raise NotImplementedError('FacebookService.fetch_metrics not implemented')

    async def fetch_insights(self, post_external_id: str) -> Any:
        raise NotImplementedError('FacebookService.fetch_insights not implemented')

    async def create_post(self, payload: Any) -> Any:
        raise NotImplementedError('FacebookService.create_post not implemented')

    async def update_post(self, post_external_id: str, payload: Any) -> Any:
        raise NotImplementedError('FacebookService.update_post not implemented')

    async def delete_post(self, post_external_id: str) -> bool:
        raise NotImplementedError('FacebookService.delete_post not implemented')

    async def upload_video(self, payload: Any) -> Any:
        raise NotImplementedError('FacebookService.upload_video not implemented') 