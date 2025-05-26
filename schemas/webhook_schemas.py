"""
Strict Pydantic models for webhook payloads
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime


class InstagramWebhookEntry(BaseModel):
    """Instagram webhook entry"""
    id: str = Field(..., description="Entry ID")
    time: int = Field(..., description="Timestamp")
    changes: List[Dict[str, Any]] = Field(..., description="Changes array")


class InstagramWebhookPayload(BaseModel):
    """Instagram webhook payload"""
    object: str = Field(..., description="Object type")
    entry: List[InstagramWebhookEntry] = Field(..., description="Webhook entries")
    
    @validator('object')
    def validate_object_type(cls, v):
        if v not in ['instagram', 'page']:
            raise ValueError(f"Invalid object type: {v}")
        return v


class TwitterWebhookUser(BaseModel):
    """Twitter user object"""
    id_str: str = Field(..., description="User ID")
    screen_name: str = Field(..., description="Username")
    name: str = Field(..., description="Display name")
    verified: bool = Field(False, description="Verified status")
    followers_count: int = Field(0, description="Follower count")


class TwitterWebhookTweet(BaseModel):
    """Twitter tweet object"""
    id_str: str = Field(..., description="Tweet ID")
    text: str = Field(..., description="Tweet text")
    created_at: str = Field(..., description="Creation timestamp")
    user: TwitterWebhookUser = Field(..., description="Tweet author")
    in_reply_to_status_id_str: Optional[str] = Field(None, description="Reply to tweet ID")
    retweet_count: int = Field(0, description="Retweet count")
    favorite_count: int = Field(0, description="Like count")


class TwitterWebhookPayload(BaseModel):
    """Twitter webhook payload"""
    tweet_create_events: List[TwitterWebhookTweet] = Field(default_factory=list, description="Tweet events")
    favorite_events: List[Dict[str, Any]] = Field(default_factory=list, description="Like events")
    follow_events: List[Dict[str, Any]] = Field(default_factory=list, description="Follow events")


class YouTubeWebhookSnippet(BaseModel):
    """YouTube comment snippet"""
    videoId: str = Field(..., description="Video ID")
    textDisplay: str = Field(..., description="Comment text")
    authorDisplayName: str = Field(..., description="Author name")
    authorChannelId: Optional[Dict[str, str]] = Field(None, description="Author channel")
    publishedAt: str = Field(..., description="Published timestamp")
    updatedAt: Optional[str] = Field(None, description="Updated timestamp")
    parentId: Optional[str] = Field(None, description="Parent comment ID")
    likeCount: int = Field(0, description="Like count")


class YouTubeWebhookComment(BaseModel):
    """YouTube comment object"""
    id: str = Field(..., description="Comment ID")
    snippet: YouTubeWebhookSnippet = Field(..., description="Comment snippet")


class YouTubeWebhookPayload(BaseModel):
    """YouTube webhook payload"""
    comment: YouTubeWebhookComment = Field(..., description="Comment data")


class LinkedInWebhookComment(BaseModel):
    """LinkedIn comment object"""
    id: str = Field(..., description="Comment ID")
    author: str = Field(..., description="Author URN")
    message: Dict[str, str] = Field(..., description="Comment message")
    object: str = Field(..., description="Parent object URN")
    created: Dict[str, str] = Field(..., description="Creation info")


class LinkedInWebhookEvent(BaseModel):
    """LinkedIn webhook event"""
    eventType: str = Field(..., description="Event type")
    comment: LinkedInWebhookComment = Field(..., description="Comment data")
    
    @validator('eventType')
    def validate_event_type(cls, v):
        valid_types = ['COMMENT_CREATED', 'COMMENT_UPDATED', 'COMMENT_DELETED']
        if v not in valid_types:
            raise ValueError(f"Invalid event type: {v}")
        return v


class LinkedInWebhookPayload(BaseModel):
    """LinkedIn webhook payload"""
    events: List[LinkedInWebhookEvent] = Field(..., description="Webhook events")


class BulkReplyValidatedRequest(BaseModel):
    """Validated bulk reply request"""
    replies: List[BulkReplyItem] = Field(..., min_items=1, max_items=50, description="Reply items")
    
    @validator('replies')
    def validate_unique_comments(cls, v):
        comment_ids = [item.comment_id for item in v]
        if len(comment_ids) != len(set(comment_ids)):
            raise ValueError("Duplicate comment IDs not allowed")
        return v


class BulkReplyValidatedResponse(BaseModel):
    """Validated bulk reply response"""
    total_submitted: int = Field(..., description="Total replies submitted")
    successful: List[ReplyResponse] = Field(..., description="Successful replies")
    failed: List[Dict[str, Any]] = Field(..., description="Failed replies with errors")
    job_ids: List[str] = Field(..., description="Background job IDs")
