"""
Base platform service interface with strict abstraction
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class PlatformConnectionData(BaseModel):
    """Standardized platform connection data"""
    access_token: str
    refresh_token: Optional[str] = None
    token_expires: Optional[datetime] = None
    metadata: Dict[str, Any] = {}


class PlatformWebhookData(BaseModel):
    """Standardized webhook data"""
    external_id: str
    author: Optional[str] = None
    message: str
    post_id: Optional[str] = None
    platform_metadata: Dict[str, Any] = {}


# Aliases for legacy names
ConnectionConfig = PlatformConnectionData
CommentData = PlatformWebhookData

class WebhookPayload(BaseModel):
    """Raw webhook payload data for ingestion"""
    headers: Dict[str, str]
    body: bytes
    json_data: Dict[str, Any]


class BasePlatformService(ABC):
    """Abstract base class for all social platform services"""
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Platform identifier"""
        pass
    
    @abstractmethod
    async def validate_connection(self, access_token: str) -> bool:
        """Validate platform access token"""
        pass
    
    @abstractmethod
    async def connect_team(self, team_id: UUID, connection_data: PlatformConnectionData) -> Dict[str, Any]:
        """Connect team to platform"""
        pass
    
    @abstractmethod
    async def disconnect_team(self, team_id: UUID, connection_id: UUID) -> bool:
        """Disconnect team from platform"""
        pass
    
    @abstractmethod
    async def process_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> List[PlatformWebhookData]:
        """Process webhook payload and extract comments"""
        pass
    
    @abstractmethod
    async def verify_webhook_signature(self, body: bytes, headers: Dict[str, str]) -> bool:
        """Verify webhook signature"""
        pass
    
    @abstractmethod
    async def post_reply(self, comment_id: str, message: str, access_token: str) -> Dict[str, Any]:
        """Post reply to platform"""
        pass
