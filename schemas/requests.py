"""
Request schemas for all API endpoints
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class ConnectionRequest(BaseModel):
    """Social platform connection request"""
    access_token: str = Field(..., description="Platform access token")
    refresh_token: Optional[str] = Field(None, description="Platform refresh token")
    token_expires: Optional[datetime] = Field(None, description="Token expiration time")


class ReplyRequest(BaseModel):
    """Single reply request"""
    message: str = Field(..., min_length=1, max_length=2000, description="Reply message")


class BulkReplyItem(BaseModel):
    """Single item in bulk reply request"""
    comment_id: UUID = Field(..., description="Comment ID to reply to")
    message: str = Field(..., min_length=1, max_length=2000, description="Reply message")


class BulkReplyRequest(BaseModel):
    """Bulk reply request"""
    replies: List[BulkReplyItem] = Field(..., min_items=1, max_items=100, description="List of replies")


class EmbeddingRequest(BaseModel):
    """Embedding generation request"""
    comment_id: UUID = Field(..., description="Comment ID to generate embedding for")


class ClassificationRequest(BaseModel):
    """Comment classification request"""
    comment_id: UUID = Field(..., description="Comment ID to classify")


class TokenTrackingRequest(BaseModel):
    """Token usage tracking request"""
    team_id: UUID = Field(..., description="Team ID")
    usage_type: str = Field(..., regex="^(embedding|classification|generation)$", description="Type of usage")
    tokens_used: int = Field(..., ge=0, description="Number of tokens used")
    cost: float = Field(..., ge=0, description="Cost of usage")


class UserCreateRequest(BaseModel):
    """User creation request"""
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$', description="User email")
    user_name: str = Field(..., min_length=1, max_length=255, description="User display name")
    roles: List[str] = Field(default=["member"], description="User roles")


class UserUpdateRequest(BaseModel):
    """User update request"""
    user_name: Optional[str] = Field(None, min_length=1, max_length=255, description="User display name")
    roles: Optional[List[str]] = Field(None, description="User roles")
