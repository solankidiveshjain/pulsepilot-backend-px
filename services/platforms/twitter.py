"""
Twitter/X platform service implementation
"""

import os
import hmac
import hashlib
import secrets
import base64
from typing import Dict, Any, List, Optional
from uuid import UUID
from utils.http_client import get_async_client

from .base import BasePlatformService, ConnectionConfig, OnboardingConfig, WebhookPayload, CommentData
from utils.config import get_config


class TwitterService(BasePlatformService):
    """Twitter/X API v2 service implementation"""
    
    def __init__(self):
        self.base_url = "https://api.twitter.com/2"
        self.client = get_async_client()
        # Load configuration with fallback to None for testing
        try:
            self.config = get_config()
        except Exception:
            self.config = None
        # Placeholders for OAuth
        self._oauth_config: Optional[ConnectionConfig] = None
        self._code_verifier: Optional[str] = None
    
    @property
    def platform_name(self) -> str:
        return "twitter"
    
    async def connect_team(self, team_id: UUID, config: ConnectionConfig) -> Dict[str, Any]:
        """Connect team to Twitter"""
        is_valid = await self.validate_token(config.access_token)
        if not is_valid:
            raise ValueError("Invalid Twitter access token")
        
        return {
            "platform": self.platform_name,
            "status": "connected",
            "access_token": config.access_token,
            "refresh_token": config.refresh_token,
            "token_expires": config.token_expires,
            "metadata": config.metadata or {}
        }
    
    async def disconnect_team(self, team_id: UUID, connection_id: UUID) -> bool:
        """Disconnect team from Twitter"""
        return True
    
    async def process_webhook(self, payload: WebhookPayload) -> List[CommentData]:
        """Process Twitter webhook and extract comments"""
        if not await self._verify_signature(payload.body, payload.headers):
            raise ValueError("Invalid webhook signature")
        
        comments = []
        for tweet in payload.json_data.get("tweet_create_events", []):
            if tweet.get("in_reply_to_status_id"):
                comment = CommentData(
                    external_id=tweet.get("id_str", ""),
                    author=tweet.get("user", {}).get("screen_name"),
                    message=tweet.get("text"),
                    post_id=tweet.get("in_reply_to_status_id"),
                    platform_metadata={
                        "twitter_data": tweet
                    }
                )
                comments.append(comment)
        
        return comments
    
    async def validate_token(self, access_token: str) -> bool:
        """Validate Twitter access token"""
        try:
            response = await self.client.get(
                f"{self.base_url}/users/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            return response.status_code == 200
        except Exception:
            return False
    
    async def revoke_token(self, access_token: str) -> bool:
        """Revoke Twitter access token"""
        try:
            response = await self.client.post(
                "https://api.twitter.com/oauth/revoke",
                data={"token": access_token}
            )
            return response.status_code == 200
        except Exception:
            return False
    
    async def post_reply(self, comment_id: str, message: str, access_token: str) -> Dict[str, Any]:
        """Post reply to Twitter tweet"""
        response = await self.client.post(
            f"{self.base_url}/tweets",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "text": message,
                "reply": {"in_reply_to_tweet_id": comment_id}
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def _verify_signature(self, body: bytes, headers: Dict[str, str]) -> bool:
        """Verify Twitter webhook signature"""
        signature = headers.get("x-twitter-webhooks-signature", "")
        if not signature:
            return False
        
        consumer_secret = self.config.twitter_consumer_secret
        if not consumer_secret:
            return False
        
        expected_signature = "sha256=" + hmac.new(
            consumer_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)

    # Public alias for webhook signature verification
    verify_webhook_signature = _verify_signature
    # Public alias for connection validation
    validate_connection = validate_token

    async def get_onboarding_url(self, team_id: UUID, config: OnboardingConfig) -> Dict[str, Any]:
        """Generate Twitter OAuth2 PKCE authorization URL"""
        self._oauth_config = config
        # Generate code verifier and challenge
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).rstrip(b"=").decode()
        self._code_verifier = code_verifier
        state = str(team_id)
        scope_str = " ".join(config.scopes)
        auth_url = (
            f"https://twitter.com/i/oauth2/authorize"
            f"?response_type=code"
            f"&client_id={config.client_id}"
            f"&redirect_uri={config.redirect_uri}"
            f"&scope={scope_str}"
            f"&state={state}"
            f"&code_challenge={code_challenge}"
            f"&code_challenge_method=S256"
        )
        return {"auth_url": auth_url, "state": state, "platform": self.platform_name}

    async def exchange_auth_code(self, auth_code: str, state: str) -> ConnectionConfig:
        """Exchange authorization code for access token using PKCE"""
        if not self._oauth_config or not self._code_verifier:
            raise RuntimeError("OAuth configuration missing for Twitter code exchange")
        data = {
            'grant_type': 'authorization_code',
            'client_id': self._oauth_config.client_id,
            'code': auth_code,
            'redirect_uri': self._oauth_config.redirect_uri,
            'code_verifier': self._code_verifier
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        resp = await self.client.post(
            'https://api.twitter.com/2/oauth2/token',
            data=data,
            headers=headers
        )
        resp.raise_for_status()
        token_data = resp.json()
        return ConnectionConfig(
            access_token=token_data.get('access_token'),
            refresh_token=token_data.get('refresh_token'),
            token_expires=None,
            metadata=token_data
        )

    async def refresh_token(self, refresh_token: str) -> ConnectionConfig:
        """Refresh Twitter access token using OAuth2 refresh_token grant"""
        if not self._oauth_config:
            raise RuntimeError("OAuth configuration missing for Twitter refresh")
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self._oauth_config.client_id
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        resp = await self.client.post(
            'https://api.twitter.com/2/oauth2/token',
            data=data,
            headers=headers
        )
        resp.raise_for_status()
        token_data = resp.json()
        return ConnectionConfig(
            access_token=token_data.get('access_token'),
            refresh_token=token_data.get('refresh_token'),
            token_expires=None,
            metadata=token_data
        )
