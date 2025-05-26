"""
Strict Pydantic models for all API endpoints
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from uuid import UUID
from pydantic import BaseModel, Field, validator
from enum import Enum


class PlatformType(str, Enum):
    """Supported platforms"""
    INSTAGRAM = "instagram"
    TWITTER = "twitter"
    YOUTUBE = "youtube"
    LINKEDIN = "linkedin"


# Connection Models
class ConnectionRequest(BaseModel):
    """Platform connection request"""
    access_token: str = Field(..., min_length=1, description="Platform access token")
    refresh_token: Optional[str] = Field(None, description="Platform refresh token")
    token_expires: Optional[datetime] = Field(None, description="Token expiration time")
    
    @validator('access_token')
    def validate_access_token(cls, v):
        if not v.strip():
            raise ValueError("Access token cannot be empty")
        return v.strip()


class ConnectionResponse(BaseModel):
    """Platform connection response"""
    connection_id: UUID = Field(..., description="Connection ID")
    platform: PlatformType = Field(..., description="Platform name")
    status: str = Field(..., description="Connection status")
    created_at: datetime = Field(..., description="Connection creation time")
    expires_at: Optional[datetime] = Field(None, description="Token expiration time")


# Webhook Models
class WebhookRequest(BaseModel):
    """Webhook payload validation"""
    platform: PlatformType = Field(..., description="Source platform")
    payload: Dict[str, Any] = Field(..., description="Webhook payload")
    
    @validator('payload')
    def validate_payload(cls, v):
        if not v:
            raise ValueError("Webhook payload cannot be empty")
        return v


class WebhookResponse(BaseModel):
    """Webhook processing response"""
    status: str = Field(..., description="Processing status")
    message: str = Field(..., description="Processing message")
    comments_processed: int = Field(0, description="Number of comments processed")
    job_id: Optional[str] = Field(None, description="Background job ID")


# Reply Models
class ReplyRequest(BaseModel):
    """Reply submission request"""
    message: str = Field(..., min_length=1, max_length=2000, description="Reply message")
    
    @validator('message')
    def validate_message(cls, v):
        if not v.strip():
            raise ValueError("Reply message cannot be empty")
        return v.strip()


class BulkReplyItem(BaseModel):
    """Single item in bulk reply request"""
    comment_id: UUID = Field(..., description="Comment ID")
    message: str = Field(..., min_length=1, max_length=2000, description="Reply message")
    
    @validator('message')
    def validate_message(cls, v):
        if not v.strip():
            raise ValueError("Reply message cannot be empty")
        return v.strip()


class BulkReplyRequest(BaseModel):
    """Bulk reply request"""
    replies: List[BulkReplyItem] = Field(..., min_items=1, max_items=50, description="Reply items")
    
    @validator('replies')
    def validate_unique_comments(cls, v):
        comment_ids = [item.comment_id for item in v]
        if len(comment_ids) != len(set(comment_ids)):
            raise ValueError("Duplicate comment IDs not allowed")
        return v


class ReplyResponse(BaseModel):
    """Reply submission response"""
    reply_id: UUID = Field(..., description="Reply ID")
    message: str = Field(..., description="Reply message")
    status: str = Field(..., description="Reply status")
    submitted_at: datetime = Field(..., description="Submission timestamp")


# Suggestion Models
class SuggestionRequest(BaseModel):
    """AI suggestion request"""
    comment_id: UUID = Field(..., description="Comment ID")
    max_suggestions: int = Field(3, ge=1, le=10, description="Maximum suggestions")
    include_context: bool = Field(True, description="Include similar contexts")


class SuggestionItem(BaseModel):
    """Individual suggestion"""
    text: str = Field(..., description="Suggested reply text")
    score: float = Field(..., ge=0, le=1, description="Confidence score")
    tone: str = Field(..., description="Suggested tone")
    reasoning: Optional[str] = Field(None, description="Generation reasoning")


class SuggestionsResponse(BaseModel):
    """AI suggestions response"""
    comment_id: UUID = Field(..., description="Comment ID")
    suggestions: List[SuggestionItem] = Field(..., description="Generated suggestions")
    context_used: str = Field(..., description="Context information")
    processing_time_ms: int = Field(..., description="Processing time")
    job_id: Optional[str] = Field(None, description="Background job ID")


# Analytics Models
class TokenUsageResponse(BaseModel):
    """Token usage analytics"""
    team_id: UUID = Field(..., description="Team ID")
    quota_limit: int = Field(..., description="Monthly quota")
    tokens_used: int = Field(..., description="Tokens used")
    tokens_remaining: int = Field(..., description="Tokens remaining")
    quota_exceeded: bool = Field(..., description="Quota exceeded flag")
    usage_breakdown: Dict[str, Dict[str, Any]] = Field(..., description="Usage by type")


# Error Models
class ErrorDetail(BaseModel):
    """Error detail structure"""
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional details")


class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = Field(False, description="Success flag")
    error: ErrorDetail = Field(..., description="Error information")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
