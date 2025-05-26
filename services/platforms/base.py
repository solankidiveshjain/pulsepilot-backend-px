"""
Base platform service interface for social media integrations
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from uuid import UUID


class ConnectionConfig(BaseModel):
    """Platform connection configuration"""
    access_token: str
    refresh_token: Optional[str] = None
    token_expires: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class WebhookPayload(BaseModel):
    """Webhook payload structure"""
    headers: Dict[str, str]
    body: bytes
    json_data: Dict[str, Any]


class CommentData(BaseModel):
    """Extracted comment data from webhook"""
    external_id: str
    author: Optional[str]
    message: Optional[str]
    post_id: Optional[str]
    platform_metadata: Dict[str, Any]


class BasePlatformService(ABC):
    """Base interface for all social media platform services"""
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Platform identifier"""
        pass
    
    @abstractmethod
    async def connect(self, team_id: UUID, config: ConnectionConfig) -> Dict[str, Any]:
        """Connect team to platform"""
        pass
    
    @abstractmethod
    async def disconnect(self, team_id: UUID, connection_id: UUID) -> bool:
        """Disconnect team from platform"""
        pass
    
    @abstractmethod
    async def ingest_webhook(self, payload: WebhookPayload) -> List[CommentData]:
        """Process webhook and extract comments"""
        pass
    
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
