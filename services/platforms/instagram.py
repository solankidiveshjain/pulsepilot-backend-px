"""
Instagram platform service implementation
"""

import hmac
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
from utils.http_client import get_async_client
from utils.config import get_config
from datetime import datetime, timedelta
from schemas.social_media import PostData, CommentData, MetricsData, InsightsData
import httpx

from .base import BasePlatformService, PlatformConnectionData, PlatformWebhookData, OnboardingConfig


class InstagramService(BasePlatformService):
    """Instagram Graph API service implementation"""
    
    def __init__(self):
        self.base_url = "https://graph.instagram.com"
        self.client = get_async_client()
        # Load configuration with fallback to None for testing
        try:
            self.config = get_config()
        except Exception:
            self.config = None
        # Placeholder for OAuth onboarding configuration
        self._oauth_config: Optional[OnboardingConfig] = None
    
    @property
    def platform_name(self) -> str:
        return "instagram"
    
    async def validate_connection(self, access_token: str) -> bool:
        """Validate Instagram access token"""
        try:
            response = await self.client.get(
                f"{self.base_url}/me",
                params={"access_token": access_token}
            )
            return response.status_code == 200
        except Exception:
            return False
    
    async def connect_team(self, team_id: UUID, connection_data: PlatformConnectionData) -> Dict[str, Any]:
        """Connect team to Instagram"""
        is_valid = await self.validate_connection(connection_data.access_token)
        if not is_valid:
            raise ValueError("Invalid Instagram access token")
        
        return {
            "platform": self.platform_name,
            "status": "connected",
            "access_token": connection_data.access_token,
            "refresh_token": connection_data.refresh_token,
            "token_expires": connection_data.token_expires,
            "metadata": connection_data.metadata
        }
    
    async def disconnect_team(self, team_id: UUID, connection_id: UUID) -> bool:
        """Disconnect team from Instagram"""
        return True
    
    async def process_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> List[PlatformWebhookData]:
        """Process Instagram webhook and extract comments"""
        comments = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") == "comments":
                    value = change.get("value", {})
                    comment = PlatformWebhookData(
                        external_id=value.get("id", ""),
                        author=value.get("from", {}).get("username"),
                        message=value.get("text", ""),
                        post_id=value.get("media", {}).get("id"),
                        platform_metadata={"instagram_data": value}
                    )
                    comments.append(comment)
        return comments
    
    async def verify_webhook_signature(self, body: bytes, headers: Dict[str, str]) -> bool:
        """Verify Instagram webhook signature"""
        signature = headers.get("x-hub-signature-256", "")
        if not signature:
            return False
        
        expected_signature = "sha256=" + hmac.new(
            self.config.instagram_app_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    async def post_reply(self, comment_id: str, message: str, access_token: str) -> Dict[str, Any]:
        """Post reply to Instagram comment"""
        response = await self.client.post(
            f"{self.base_url}/{comment_id}/replies",
            data={"message": message, "access_token": access_token}
        )
        response.raise_for_status()
        return response.json()
    
    async def get_onboarding_url(self, team_id: UUID, config: OnboardingConfig) -> Dict[str, Any]:
        """Stub OAuth URL generation until full flow is implemented"""
        # Save onboarding config for code exchange
        self._oauth_config = config
        state = str(team_id)
        # Construct Instagram Basic Display OAuth authorization URL
        scope_str = ",".join(config.scopes)
        auth_url = (
            f"https://api.instagram.com/oauth/authorize"
            f"?client_id={config.client_id}"
            f"&redirect_uri={config.redirect_uri}"
            f"&scope={scope_str}"
            f"&response_type=code"
            f"&state={state}"
        )
        return {"auth_url": auth_url, "state": state, "platform": self.platform_name}
    
    async def exchange_auth_code(self, auth_code: str, state: str) -> PlatformConnectionData:
        """Perform full OAuth code exchange for Instagram Basic Display API"""
        if not self._oauth_config:
            raise RuntimeError("OAuth configuration missing for Instagram code exchange")
        # Step 1: exchange code for short-lived token
        data = {
            "client_id": self._oauth_config.client_id,
            "client_secret": self._oauth_config.client_secret,
            "grant_type": "authorization_code",
            "redirect_uri": self._oauth_config.redirect_uri,
            "code": auth_code,
        }
        resp1 = await self.client.post(
            "https://api.instagram.com/oauth/access_token",
            data=data
        )
        resp1.raise_for_status()
        token_data = resp1.json()
        short_token = token_data.get("access_token")
        user_id = token_data.get("user_id")

        # Step 2: exchange short-lived token for long-lived token
        exchange_params = {
            "grant_type": "ig_exchange_token",
            "client_secret": self._oauth_config.client_secret,
            "access_token": short_token
        }
        resp2 = await self.client.get(
            f"{self.base_url}/access_token",
            params=exchange_params
        )
        resp2.raise_for_status()
        long_data = resp2.json()
        long_token = long_data.get("access_token")
        expires_in = long_data.get("expires_in")
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in) if expires_in else None

        # Combine metadata
        metadata = {"user_id": user_id, **long_data}
        return PlatformConnectionData(
            access_token=long_token,
            refresh_token=None,
            token_expires=expires_at,
            metadata=metadata
        )
    
    async def refresh_token(self, refresh_token: str) -> PlatformConnectionData:
        """Refresh Instagram long-lived token"""
        # Instagram uses current access_token in place of refresh_token
        params = {
            'grant_type': 'ig_refresh_token',
            'access_token': refresh_token
        }
        resp = await self.client.get(
            f"{self.base_url}/refresh_access_token",
            params=params
        )
        resp.raise_for_status()
        data = resp.json()
        new_token = data.get('access_token')
        expires_in = data.get('expires_in')
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in) if expires_in else None
        return PlatformConnectionData(
            access_token=new_token,
            refresh_token=None,
            token_expires=expires_at,
            metadata=data
        )

    async def fetch_initial(self, access_token: str) -> Tuple[List[PostData], List[CommentData]]:
        """Fetch recent media entries and nested comments via Instagram Graph API v16.0"""
        fields = (
            'media.limit(25){id,caption,media_type,permalink,timestamp,'
            'comments.limit(25){id,text,timestamp,username}}'
        )
        try:
            resp = await self.client.get(
                f"{self.base_url}/me/media",
                params={"fields": fields, "access_token": access_token}
            )
            resp.raise_for_status()
            items = resp.json().get('data', [])
        except httpx.HTTPError:
            return [], []
        posts: List[PostData] = []
        comments: List[CommentData] = []
        for item in items:
            ts = item.get('timestamp') or item.get('created_time')
            created_at = datetime.fromisoformat(ts.replace('Z', '+00:00')) if ts else None
            posts.append(PostData(
                external_id=item.get('id', ''),
                platform=self.platform_name,
                type=item.get('media_type'),
                metadata=item,
                created_at=created_at
            ))
            for c in item.get('comments', {}).get('data', []):
                cts = c.get('timestamp') or c.get('created_time')
                c_at = datetime.fromisoformat(cts.replace('Z', '+00:00')) if cts else None
                comments.append(CommentData(
                    external_id=c.get('id', ''),
                    platform=self.platform_name,
                    post_external_id=item.get('id', ''),
                    author=c.get('username') or c.get('from', {}).get('username'),
                    message=c.get('text'),
                    metadata=c,
                    created_at=c_at
                ))
        return posts, comments

    async def fetch_metrics(self, access_token: str, since: datetime, until: datetime) -> MetricsData:
        """Fetch Instagram profile-level metrics between two timestamps"""
        metric_names = ['impressions', 'reach', 'profile_views']
        try:
            resp = await self.client.get(
                f"{self.base_url}/me/insights",
                params={
                    'metric': ','.join(metric_names),
                    'period': 'day',
                    'since': int(since.timestamp()),
                    'until': int(until.timestamp()),
                    'access_token': access_token
                }
            )
            resp.raise_for_status()
            data = resp.json().get('data', [])
        except httpx.HTTPError:
            return MetricsData(platform=self.platform_name, since=since, until=until, metrics={})
        metrics: Dict[str, int] = {}
        for entry in data:
            name = entry.get('name')
            total = 0
            for v in entry.get('values', []):
                val = v.get('value', 0)
                total += sum(val.values()) if isinstance(val, dict) else val
            if name:
                metrics[name] = total
        return MetricsData(platform=self.platform_name, since=since, until=until, metrics=metrics)

    async def fetch_insights(self, access_token: str, post_external_id: str) -> InsightsData:
        """Fetch media-level detailed insights via Graph API"""
        metric_names = ['impressions', 'reach', 'engagement']
        try:
            resp = await self.client.get(
                f"{self.base_url}/{post_external_id}/insights",
                params={
                    'metric': ','.join(metric_names),
                    'period': 'lifetime',
                    'access_token': access_token
                }
            )
            resp.raise_for_status()
            data = resp.json().get('data', [])
        except httpx.HTTPError:
            return InsightsData(platform=self.platform_name, post_external_id=post_external_id, metrics={})
        metrics: Dict[str, int] = {}
        for entry in data:
            name = entry.get('name')
            total = 0
            for v in entry.get('values', []):
                val = v.get('value', 0)
                total += sum(val.values()) if isinstance(val, dict) else val
            if name:
                metrics[name] = total
        return InsightsData(platform=self.platform_name, post_external_id=post_external_id, metrics=metrics)
