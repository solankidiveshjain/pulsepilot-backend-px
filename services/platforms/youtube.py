"""
YouTube platform service implementation
"""

from typing import Dict, Any, List
from uuid import UUID
import httpx

from .base import BasePlatformService, ConnectionConfig, WebhookPayload, CommentData
from utils.config import get_config


class YouTubeService(BasePlatformService):
    """YouTube Data API v3 service implementation"""
    
    def __init__(self):
        self.base_url = "https://www.googleapis.com/youtube/v3"
        self.client = httpx.AsyncClient()
        self.config = get_config()
    
    @property
    def platform_name(self) -> str:
        return "youtube"
    
    async def connect(self, team_id: UUID, config: ConnectionConfig) -> Dict[str, Any]:
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
    
    async def disconnect(self, team_id: UUID, connection_id: UUID) -> bool:
        """Disconnect team from YouTube"""
        return True
    
    async def ingest_webhook(self, payload: WebhookPayload) -> List[CommentData]:
        """Process YouTube webhook and extract comments"""
        # YouTube uses PubSubHubbub, simplified processing
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
