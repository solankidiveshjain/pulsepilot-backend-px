"""
Request schemas for all API endpoints
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, validator


class OnboardingRequest(BaseModel):
    """Platform onboarding request"""
    redirect_uri: str = Field(..., description="OAuth redirect URI")
    scopes: List[str] = Field(default=[], description="Requested OAuth scopes")


class TokenExchangeRequest(BaseModel):
    """OAuth token exchange request"""
    code: str = Field(..., description="Authorization code")
    state: str = Field(..., description="OAuth state parameter")


class ConnectionRequest(BaseModel):
    """Social platform connection request"""
    access_token: str = Field(..., description="Platform access token")
    refresh_token: Optional[str] = Field(None, description="Platform refresh token")
    token_expires: Optional[datetime] = Field(None, description="Token expiration time")


class ReplyRequest(BaseModel):
    """Single reply request"""
    message: str = Field(..., min_length=1, max_length=2000, description="Reply message")
    
    @validator('message')
    def validate_message(cls, v):
        if not v.strip():
            raise ValueError("Message cannot be empty or whitespace only")
        return v.strip()


class BulkReplyItem(BaseModel):
    """Single item in bulk reply request"""
    comment_id: UUID = Field(..., description="Comment ID to reply to")
    message: str = Field(..., min_length=1, max_length=2000, description="Reply message")
    
    @validator('message')
    def validate_message(cls, v):
        if not v.strip():
            raise ValueError("Message cannot be empty or whitespace only")
        return v.strip()


class BulkReplyRequest(BaseModel):
    """Bulk reply request"""
    replies: List[BulkReplyItem] = Field(..., min_items=1, max_items=100, description="List of replies")


class SuggestionRequest(BaseModel):
    """AI suggestion generation request"""
    comment_id: UUID = Field(..., description="Comment ID to generate suggestions for")
    max_suggestions: int = Field(3, ge=1, le=10, description="Maximum number of suggestions")
    include_context: bool = Field(True, description="Include similar reply contexts")


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
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class UserCreateRequest(BaseModel):
    """User creation request"""
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$', description="User email")
    user_name: str = Field(..., min_length=1, max_length=255, description="User display name")
    roles: List[str] = Field(default=["member"], description="User roles")
    
    @validator('roles')
    def validate_roles(cls, v):
        valid_roles = ["admin", "member", "viewer"]
        for role in v:
            if role not in valid_roles:
                raise ValueError(f"Invalid role: {role}. Must be one of {valid_roles}")
        return v


class UserUpdateRequest(BaseModel):
    """User update request"""
    user_name: Optional[str] = Field(None, min_length=1, max_length=255, description="User display name")
    roles: Optional[List[str]] = Field(None, description="User roles")
    
    @validator('roles')
    def validate_roles(cls, v):
        if v is not None:
            valid_roles = ["admin", "member", "viewer"]
            for role in v:
                if role not in valid_roles:
                    raise ValueError(f"Invalid role: {role}. Must be one of {valid_roles}")
        return v


class WebhookVerificationRequest(BaseModel):
    """Webhook verification request"""
    hub_mode: str = Field(..., description="Webhook verification mode")
    hub_challenge: str = Field(..., description="Webhook challenge")
    hub_verify_token: str = Field(..., description="Webhook verification token")
