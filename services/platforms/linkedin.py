"""
LinkedIn platform service implementation
"""

import hmac
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
from utils.http_client import get_async_client
from datetime import datetime, timedelta

from .base import BasePlatformService, ConnectionConfig, WebhookPayload, CommentData, OnboardingConfig
from utils.config import get_config
import asyncio
from schemas.social_media import PostData, CommentData, MetricsData, InsightsData


class LinkedInService(BasePlatformService):
    """LinkedIn API service implementation"""
    
    def __init__(self):
        self.base_url = "https://api.linkedin.com/v2"
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
        return "linkedin"
    
    async def connect_team(self, team_id: UUID, config: ConnectionConfig) -> Dict[str, Any]:
        """Connect team to LinkedIn"""
        is_valid = await self.validate_token(config.access_token)
        if not is_valid:
            raise ValueError("Invalid LinkedIn access token")
        
        return {
            "platform": self.platform_name,
            "status": "connected",
            "access_token": config.access_token,
            "refresh_token": config.refresh_token,
            "token_expires": config.token_expires,
            "metadata": config.metadata or {}
        }
    
    async def disconnect_team(self, team_id: UUID, connection_id: UUID) -> bool:
        """Disconnect team from LinkedIn"""
        return True
    
    async def process_webhook(self, payload: WebhookPayload) -> List[CommentData]:
        """Process LinkedIn webhook and extract comments"""
        if not await self._verify_signature(payload.body, payload.headers):
            raise ValueError("Invalid webhook signature")
        
        comments = []
        for event in payload.json_data.get("events", []):
            if event.get("eventType") == "COMMENT_CREATED":
                comment_info = event.get("comment", {})
                comment = CommentData(
                    external_id=comment_info.get("id", ""),
                    author=comment_info.get("author"),
                    message=comment_info.get("message", {}).get("text"),
                    post_id=comment_info.get("object"),
                    platform_metadata={
                        "linkedin_data": event
                    }
                )
                comments.append(comment)
        
        return comments
    
    async def validate_token(self, access_token: str) -> bool:
        """Validate LinkedIn access token"""
        try:
            response = await self.client.get(
                f"{self.base_url}/people/~",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            return response.status_code == 200
        except Exception:
            return False
    
    async def revoke_token(self, access_token: str) -> bool:
        """Revoke LinkedIn access token"""
        # LinkedIn doesn't have direct revoke endpoint
        return True
    
    async def post_reply(self, comment_id: str, message: str, access_token: str) -> Dict[str, Any]:
        """Post reply to LinkedIn comment"""
        response = await self.client.post(
            f"{self.base_url}/socialActions/{comment_id}/comments",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "message": {
                    "text": message
                }
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def get_onboarding_url(self, team_id: UUID, config: OnboardingConfig) -> Dict[str, Any]:
        """Generate LinkedIn OAuth authorization URL"""
        self._oauth_config = config
        state = str(team_id)
        scope_str = ' '.join(config.scopes)
        auth_url = (
            f"https://www.linkedin.com/oauth/v2/authorization"
            f"?response_type=code"
            f"&client_id={config.client_id}"
            f"&redirect_uri={config.redirect_uri}"
            f"&scope={scope_str}"
            f"&state={state}"
        )
        return {'auth_url': auth_url, 'state': state, 'platform': self.platform_name}

    async def exchange_auth_code(self, auth_code: str, state: str) -> ConnectionConfig:
        """Exchange LinkedIn OAuth code for access token"""
        if not self._oauth_config:
            raise RuntimeError("OAuth configuration missing for LinkedIn code exchange")
        data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': self._oauth_config.redirect_uri,
            'client_id': self._oauth_config.client_id,
            'client_secret': self._oauth_config.client_secret
        }
        # LinkedIn token endpoint
        resp = await self.client.post(
            'https://www.linkedin.com/oauth/v2/accessToken',
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
            refresh_token=None,
            token_expires=expires_at,
            metadata=token_data
        )
    
    async def refresh_token(self, refresh_token: str) -> ConnectionConfig:
        """Refresh LinkedIn access token using refresh_token grant"""
        if not self._oauth_config:
            raise RuntimeError("OAuth configuration missing for LinkedIn refresh")
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self._oauth_config.client_id,
            'client_secret': self._oauth_config.client_secret
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        resp = await self.client.post(
            'https://www.linkedin.com/oauth/v2/accessToken',
            data=data,
            headers=headers
        )
        resp.raise_for_status()
        token_data = resp.json()
        access = token_data.get('access_token')
        expires_in = token_data.get('expires_in')
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in) if expires_in else None
        return ConnectionConfig(
            access_token=access,
            refresh_token=refresh_token,
            token_expires=expires_at,
            metadata=token_data
        )
    
    async def _verify_signature(self, body: bytes, headers: Dict[str, str]) -> bool:
        """Verify LinkedIn webhook signature"""
        signature = headers.get("x-linkedin-signature", "")
        if not signature:
            return False
        
        client_secret = self.config.linkedin_client_secret
        if not client_secret:
            return False
        
        expected_signature = hmac.new(
            client_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)

    # Public alias for webhook signature verification
    verify_webhook_signature = _verify_signature
    # Alias validate_connection to validate_token
    validate_connection = validate_token

    async def fetch_initial(self, access_token: str, org_id: Optional[str] = None) -> Tuple[List[PostData], List[CommentData]]:
        """Fetch recent shares and comments from LinkedIn organization page."""
        from linkedin_v2 import linkedin
        import asyncio
        if not org_id:
            return [], []
        app = linkedin.LinkedInApplication(token=access_token)
        try:
            updates = await asyncio.to_thread(
                app.get_company_updates,
                organization_id=org_id,
                params={'count': 25}
            )
        except Exception:
            return [], []
        posts: List[PostData] = []
        comments: List[CommentData] = []
        for u in updates.get('values', []):
            ts = u.get('timestamp')
            created_at = datetime.fromtimestamp(int(ts) / 1000) if ts else None
            posts.append(PostData(
                external_id=str(u.get('updateKey', '')),
                platform=self.platform_name,
                type=u.get('updateType'),
                metadata=u,
                created_at=created_at
            ))
        return posts, comments

    async def fetch_metrics(self, access_token: str, since: datetime, until: datetime, org_id: Optional[str] = None) -> MetricsData:
        """Fetch LinkedIn organization page statistics between two timestamps."""
        if not org_id:
            return MetricsData(platform=self.platform_name, since=since, until=until, metrics={})
        # Time interval in milliseconds
        start_ms = int(since.timestamp() * 1000)
        end_ms = int(until.timestamp() * 1000)
        params = {
            'q': 'organization',
            'organization': f"urn:li:organization:{org_id}",
            'timeIntervals': f"(timeRange:(start:{start_ms},end:{end_ms}),timeGranularityType:DAY)"
        }
        headers = {'Authorization': f"Bearer {access_token}"}
        base_url = self.config.linkedin_api_base_url if self.config and hasattr(self.config, 'linkedin_api_base_url') else self.base_url
        try:
            resp = await self.client.get(
                f"{base_url}/organizationPageStatistics",
                params=params,
                headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return MetricsData(platform=self.platform_name, since=since, until=until, metrics={})
        metrics: Dict[str, int] = {}
        for elem in data.get('elements', []):
            stats = elem.get('totalPageStatistics', {}) or {}
            for k, v in stats.items():
                if isinstance(v, dict):
                    metrics[k] = metrics.get(k, 0) + sum(v.values())
                else:
                    try:
                        metrics[k] = metrics.get(k, 0) + int(v)
                    except Exception:
                        pass
        return MetricsData(platform=self.platform_name, since=since, until=until, metrics=metrics)

    async def fetch_insights(self, access_token: str, post_external_id: str, org_id: Optional[str] = None) -> InsightsData:
        """Fetch LinkedIn share-level statistics for a single post."""
        if not org_id:
            return InsightsData(platform=self.platform_name, post_external_id=post_external_id, metrics={})
        params = {
            'q': 'organizationalEntity',
            'organizationalEntity': f"urn:li:organization:{org_id}",
            'shares': post_external_id
        }
        headers = {'Authorization': f"Bearer {access_token}"}
        base_url = self.config.linkedin_api_base_url if self.config and hasattr(self.config, 'linkedin_api_base_url') else self.base_url
        try:
            resp = await self.client.get(
                f"{base_url}/organizationalEntityShareStatistics",
                params=params,
                headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return InsightsData(platform=self.platform_name, post_external_id=post_external_id, metrics={})
        metrics: Dict[str, int] = {}
        for elem in data.get('elements', []):
            stats = elem.get('shareStatistics', {}) or {}
            for k, v in stats.items():
                try:
                    metrics[k] = int(v)
                except Exception:
                    pass
        return InsightsData(platform=self.platform_name, post_external_id=post_external_id, metrics=metrics)
