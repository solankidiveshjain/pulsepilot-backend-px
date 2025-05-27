"""
Social media platform integration services
"""

import os
import hmac
import hashlib
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from utils.http_client import get_async_client


class BasePlatformService(ABC):
    """Base class for social media platform services"""
    
    @abstractmethod
    async def validate_token(self, access_token: str) -> bool:
        """Validate access token with platform"""
        pass
    
    @abstractmethod
    async def revoke_token(self, access_token: str) -> bool:
        """Revoke access token"""
        pass
    
    @abstractmethod
    async def post_reply(self, comment_id: str, message: str, access_token: str) -> Dict[str, Any]:
        """Post reply to comment"""
        pass


class InstagramService(BasePlatformService):
    """Instagram Graph API service"""
    
    def __init__(self):
        self.base_url = "https://graph.instagram.com"
        self.client = get_async_client()
    
    async def validate_token(self, access_token: str) -> bool:
        """Validate Instagram access token"""
        try:
            response = await self.client.get(
                f"{self.base_url}/me",
                params={"access_token": access_token},
                timeout=5.0
            )
            return response.status_code == 200
        except Exception:
            return False
    
    async def revoke_token(self, access_token: str) -> bool:
        """Revoke Instagram access token"""
        try:
            response = await self.client.delete(
                f"{self.base_url}/me/permissions",
                params={"access_token": access_token},
                timeout=5.0
            )
            return response.status_code == 200
        except Exception:
            return False
    
    async def post_reply(self, comment_id: str, message: str, access_token: str) -> Dict[str, Any]:
        """Post reply to Instagram comment"""
        try:
            response = await self.client.post(
                f"{self.base_url}/{comment_id}/replies",
                data={
                    "message": message,
                    "access_token": access_token
                },
                timeout=10.0
            )
            return response.json()
        except Exception as e:
            raise Exception(f"Failed to post Instagram reply: {str(e)}")


class TwitterService(BasePlatformService):
    """Twitter/X API v2 service"""
    
    def __init__(self):
        self.base_url = "https://api.twitter.com/2"
        self.client = get_async_client()
    
    async def validate_token(self, access_token: str) -> bool:
        """Validate Twitter access token"""
        try:
            response = await self.client.get(
                f"{self.base_url}/users/me",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=5.0
            )
            return response.status_code == 200
        except Exception:
            return False
    
    async def revoke_token(self, access_token: str) -> bool:
        """Revoke Twitter access token"""
        try:
            response = await self.client.post(
                "https://api.twitter.com/oauth/revoke",
                data={"token": access_token},
                timeout=5.0
            )
            return response.status_code == 200
        except Exception:
            return False
    
    async def post_reply(self, comment_id: str, message: str, access_token: str) -> Dict[str, Any]:
        """Post reply to Twitter tweet"""
        try:
            response = await self.client.post(
                f"{self.base_url}/tweets",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "text": message,
                    "reply": {"in_reply_to_tweet_id": comment_id}
                },
                timeout=10.0
            )
            return response.json()
        except Exception as e:
            raise Exception(f"Failed to post Twitter reply: {str(e)}")


class YouTubeService(BasePlatformService):
    """YouTube Data API v3 service"""
    
    def __init__(self):
        self.base_url = "https://www.googleapis.com/youtube/v3"
        self.client = get_async_client()
    
    async def validate_token(self, access_token: str) -> bool:
        """Validate YouTube access token"""
        try:
            response = await self.client.get(
                f"{self.base_url}/channels",
                params={
                    "part": "id",
                    "mine": "true",
                    "access_token": access_token
                },
                timeout=5.0
            )
            return response.status_code == 200
        except Exception:
            return False
    
    async def revoke_token(self, access_token: str) -> bool:
        """Revoke YouTube access token"""
        try:
            response = await self.client.post(
                "https://oauth2.googleapis.com/revoke",
                data={"token": access_token},
                timeout=5.0
            )
            return response.status_code == 200
        except Exception:
            return False
    
    async def post_reply(self, comment_id: str, message: str, access_token: str) -> Dict[str, Any]:
        """Post reply to YouTube comment"""
        try:
            response = await self.client.post(
                f"{self.base_url}/comments",
                params={"access_token": access_token},
                json={
                    "snippet": {
                        "parentId": comment_id,
                        "textOriginal": message
                    }
                },
                timeout=10.0
            )
            return response.json()
        except Exception as e:
            raise Exception(f"Failed to post YouTube reply: {str(e)}")


class LinkedInService(BasePlatformService):
    """LinkedIn API service"""
    
    def __init__(self):
        self.base_url = "https://api.linkedin.com/v2"
        self.client = get_async_client()
    
    async def validate_token(self, access_token: str) -> bool:
        """Validate LinkedIn access token"""
        try:
            response = await self.client.get(
                f"{self.base_url}/people/~",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=5.0
            )
            return response.status_code == 200
        except Exception:
            return False
    
    async def revoke_token(self, access_token: str) -> bool:
        """Revoke LinkedIn access token"""
        # LinkedIn doesn't have a direct revoke endpoint
        return True
    
    async def post_reply(self, comment_id: str, message: str, access_token: str) -> Dict[str, Any]:
        """Post reply to LinkedIn comment"""
        try:
            response = await self.client.post(
                f"{self.base_url}/socialActions/{comment_id}/comments",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "message": {
                        "text": message
                    }
                },
                timeout=10.0
            )
            return response.json()
        except Exception as e:
            raise Exception(f"Failed to post LinkedIn reply: {str(e)}")


# Platform service registry
PLATFORM_SERVICES = {
    "instagram": InstagramService,
    "twitter": TwitterService,
    "youtube": YouTubeService,
    "linkedin": LinkedInService
}


def get_platform_service(platform: str) -> Optional[BasePlatformService]:
    """Get platform service instance"""
    service_class = PLATFORM_SERVICES.get(platform.lower())
    if service_class:
        return service_class()
    return None
