"""
Twitter/X platform service implementation
"""

import os
import hmac
import hashlib
from typing import Dict, Any, List
from uuid import UUID
import httpx

from .base import BasePlatformService, ConnectionConfig, WebhookPayload, CommentData
from utils.config import get_config


class TwitterService(BasePlatformService):
    """Twitter/X API v2 service implementation"""
    
    def __init__(self):
        self.base_url = "https://api.twitter.com/2"
        self.client = httpx.AsyncClient()
        self.config = get_config()
    
    @property
    def platform_name(self) -> str:
        return "twitter"
    
    async def connect(self, team_id: UUID, config: ConnectionConfig) -> Dict[str, Any]:
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
    
    async def disconnect(self, team_id: UUID, connection_id: UUID) -> bool:
        """Disconnect team from Twitter"""
        return True
    
    async def ingest_webhook(self, payload: WebhookPayload) -> List[CommentData]:
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
