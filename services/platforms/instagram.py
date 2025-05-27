"""
Instagram platform service implementation
"""

import hmac
import hashlib
from typing import Dict, Any, List
from uuid import UUID
from utils.http_client import get_async_client

from .base import BasePlatformService, PlatformConnectionData, PlatformWebhookData
from utils.config import get_config


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
