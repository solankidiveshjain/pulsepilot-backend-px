"""
Schemas for social media data fetching (Phase 1)
"""

from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime


class PostData(BaseModel):
    """Data model for a social media post fetched on initial connect"""
    external_id: str
    platform: str
    type: Optional[str] = None
    metadata: dict = {}
    created_at: Optional[datetime] = None


class CommentData(BaseModel):
    """Data model for a social media comment fetched on initial connect"""
    external_id: str
    platform: str
    post_external_id: Optional[str] = None
    author: Optional[str] = None
    message: Optional[str] = None
    metadata: dict = {}
    created_at: Optional[datetime] = None


# Analytics schema
class MetricsData(BaseModel):
    """Aggregated engagement metrics for a given time range"""
    platform: str
    since: datetime
    until: datetime
    metrics: Dict[str, int]


class InsightsData(BaseModel):
    """Per-post detailed insights"""
    platform: str
    post_external_id: str
    metrics: Dict[str, int]


# Content management schemas
class PostCreate(BaseModel):
    """Payload for creating a new post"""
    content_type: Optional[str] = None
    text: Optional[str] = None
    media_urls: List[str] = []
    link_url: Optional[str] = None
    scheduled_at: Optional[datetime] = None


class PostUpdate(BaseModel):
    """Payload for updating an existing post"""
    content_type: Optional[str] = None
    text: Optional[str] = None
    media_urls: Optional[List[str]] = None
    link_url: Optional[str] = None
    scheduled_at: Optional[datetime] = None


class VideoUpload(BaseModel):
    """Payload for uploading a video"""
    file_path: Optional[str] = None
    file_bytes: Optional[bytes] = None
    title: str
    description: Optional[str] = None
    tags: List[str] = []
    privacy_status: Optional[str] = None
    scheduled_at: Optional[datetime] = None 