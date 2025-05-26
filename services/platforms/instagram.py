"""
Instagram platform service implementation
"""

import os
import hmac
import hashlib
from typing import Dict, Any, List
from uuid import UUID
import httpx

from .base import BasePlatformService, ConnectionConfig, WebhookPayload, CommentData
from utils.config import get_config


class InstagramService(BasePlatformService):
    """Instagram Graph API service implementation"""
    
    def __init__(self):
        self.base_url = "https://graph.instagram.com"
        self.client = httpx.AsyncClient()
        self.config = get_config()
    
    @property
    def platform_name(self) -> str:
        return "instagram"
    
    async def connect(self, team_id: UUID, config: ConnectionConfig) -> Dict[str, Any]:
        """Connect team to Instagram"""
        # Validate token first
        is_valid = await self.validate_token(config.access_token)
        if not is_valid:
            raise ValueError("Invalid Instagram access token")
        
        return {
            "platform": self.platform_name,
            "status": "connected",
            "access_token": config.access_token,
            "refresh_token": config.refresh_token,
            "token_expires": config.token_expires,
            "metadata": config.metadata or {}
        }
    
    async def disconnect(self, team_id: UUID, connection_id: UUID) -> bool:
        """Disconnect team from Instagram"""
        # Instagram doesn't require special disconnect logic
        return True
    
    async def ingest_webhook(self, payload: WebhookPayload) -> List[CommentData]:
        """Process Instagram webhook and extract comments"""
        # Verify signature
        if not await self._verify_signature(payload.body, payload.headers):
            raise ValueError("Invalid webhook signature")
        
        comments = []
        for entry in payload.json_data.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") == "comments":
                    value = change.get("value", {})
                    
                    comment = CommentData(
                        external_id=value.get("id", ""),
                        author=value.get("from", {}).get("username"),
                        message=value.get("text"),
                        post_id=value.get("media", {}).get("id"),
                        platform_metadata={
                            "instagram_data": value,
                            "entry_id": entry.get("id")
                        }
                    )
                    comments.append(comment)
        
        return comments
    
    async def validate_token(self, access_token: str) -> bool:
        """Validate Instagram access token"""
        try:
            response = await self.client.get(
                f"{self.base_url}/me",
                params={"access_token": access_token}
            )
            return response.status_code == 200
        except Exception:
            return False
    
    async def revoke_token(self, access_token: str) -> bool:
        """Revoke Instagram access token"""
        try:
            response = await self.client.delete(
                f"{self.base_url}/me/permissions",
                params={"access_token": access_token}
            )
            return response.status_code == 200
        except Exception:
            return False
    
    async def post_reply(self, comment_id: str, message: str, access_token: str) -> Dict[str, Any]:
        """Post reply to Instagram comment"""
        response = await self.client.post(
            f"{self.base_url}/{comment_id}/replies",
            data={
                "message": message,
                "access_token": access_token
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def _verify_signature(self, body: bytes, headers: Dict[str, str]) -> bool:
        """Verify Instagram webhook signature"""
        signature = headers.get("x-hub-signature-256", "")
        if not signature:
            return False
        
        app_secret = self.config.instagram_app_secret
        if not app_secret:
            return False
        
        expected_signature = "sha256=" + hmac.new(
            app_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
