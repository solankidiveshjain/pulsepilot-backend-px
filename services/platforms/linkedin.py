"""
LinkedIn platform service implementation
"""

import hmac
import hashlib
from typing import Dict, Any, List
from uuid import UUID
from utils.http_client import get_async_client

from .base import BasePlatformService, ConnectionConfig, WebhookPayload, CommentData
from utils.config import get_config


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
