"""
Response schemas for all API endpoints
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class ConnectionResponse(BaseModel):
    """Social platform connection response"""
    connection_id: UUID = Field(..., description="Connection ID")
    platform: str = Field(..., description="Platform name")
    status: str = Field(..., description="Connection status")
    created_at: datetime = Field(..., description="Connection creation time")


class SuggestionResponse(BaseModel):
    """AI suggestion response"""
    suggestion_id: UUID = Field(..., description="Suggestion ID")
    suggested_reply: str = Field(..., description="Suggested reply text")
    score: float = Field(..., ge=0, le=1, description="Suggestion confidence score")
    confidence: str = Field(..., regex="^(high|medium|low)$", description="Confidence level")


class ReplyResponse(BaseModel):
    """Reply submission response"""
    reply_id: UUID = Field(..., description="Reply ID")
    message: str = Field(..., description="Reply message")
    status: str = Field(..., description="Reply status")


class EmbeddingResponse(BaseModel):
    """Embedding generation response"""
    comment_id: UUID = Field(..., description="Comment ID")
    status: str = Field(..., description="Processing status")
    embedding_dimensions: int = Field(..., description="Embedding vector dimensions")


class ClassificationResponse(BaseModel):
    """Comment classification response"""
    comment_id: UUID = Field(..., description="Comment ID")
    status: str = Field(..., description="Processing status")
    sentiment: Optional[str] = Field(None, description="Detected sentiment")
    emotion: Optional[str] = Field(None, description="Detected emotion")
    category: Optional[str] = Field(None, description="Comment category")


class TokenTrackingResponse(BaseModel):
    """Token usage tracking response"""
    usage_id: int = Field(..., description="Usage record ID")
    team_id: UUID = Field(..., description="Team ID")
    tokens_used: int = Field(..., description="Number of tokens used")
    cost: float = Field(..., description="Cost of usage")
    status: str = Field(..., description="Tracking status")


class WebhookResponse(BaseModel):
    """Webhook processing response"""
    status: str = Field(..., description="Processing status")
    message: str = Field(..., description="Processing message")


class UserResponse(BaseModel):
    """User response"""
    user_id: UUID = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    user_name: Optional[str] = Field(None, description="User display name")
    roles: List[str] = Field(..., description="User roles")
    team_id: UUID = Field(..., description="Team ID")
    created_at: str = Field(..., description="User creation time")


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str = Field(..., description="Error message")
    details: dict = Field(default_factory=dict, description="Error details")
    status_code: int = Field(..., description="HTTP status code")
