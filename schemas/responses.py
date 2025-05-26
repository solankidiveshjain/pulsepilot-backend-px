"""
Response schemas for all API endpoints
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class OnboardingResponse(BaseModel):
    """Platform onboarding response"""
    auth_url: str = Field(..., description="OAuth authorization URL")
    state: str = Field(..., description="OAuth state parameter")
    platform: str = Field(..., description="Platform name")


class ConnectionResponse(BaseModel):
    """Social platform connection response"""
    connection_id: UUID = Field(..., description="Connection ID")
    platform: str = Field(..., description="Platform name")
    status: str = Field(..., description="Connection status")
    created_at: datetime = Field(..., description="Connection creation time")
    expires_at: Optional[datetime] = Field(None, description="Token expiration time")


class SuggestionResponse(BaseModel):
    """AI suggestion response"""
    suggestion_id: UUID = Field(..., description="Suggestion ID")
    suggested_reply: str = Field(..., description="Suggested reply text")
    score: float = Field(..., ge=0, le=1, description="Suggestion confidence score")
    confidence: str = Field(..., regex="^(high|medium|low)$", description="Confidence level")
    tone: Optional[str] = Field(None, description="Suggested tone")
    reasoning: Optional[str] = Field(None, description="Why this suggestion was generated")


class SuggestionsResponse(BaseModel):
    """Multiple AI suggestions response"""
    comment_id: UUID = Field(..., description="Comment ID")
    suggestions: List[SuggestionResponse] = Field(..., description="List of suggestions")
    context_used: Optional[str] = Field(None, description="Context information used")
    rag_contexts_count: int = Field(0, description="Number of similar contexts used")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")


class ReplyResponse(BaseModel):
    """Reply submission response"""
    reply_id: UUID = Field(..., description="Reply ID")
    message: str = Field(..., description="Reply message")
    status: str = Field(..., description="Reply status")
    submitted_at: datetime = Field(..., description="Submission timestamp")


class EmbeddingResponse(BaseModel):
    """Embedding generation response"""
    comment_id: UUID = Field(..., description="Comment ID")
    status: str = Field(..., description="Processing status")
    embedding_dimensions: int = Field(..., description="Embedding vector dimensions")
    processing_time_ms: Optional[int] = Field(None, description="Processing time in milliseconds")


class ClassificationResponse(BaseModel):
    """Comment classification response"""
    comment_id: UUID = Field(..., description="Comment ID")
    status: str = Field(..., description="Processing status")
    sentiment: Optional[str] = Field(None, description="Detected sentiment")
    emotion: Optional[str] = Field(None, description="Detected emotion")
    category: Optional[str] = Field(None, description="Comment category")
    confidence_scores: Optional[Dict[str, float]] = Field(None, description="Confidence scores for each classification")


class TokenUsageResponse(BaseModel):
    """Token usage response"""
    usage_id: int = Field(..., description="Usage record ID")
    team_id: UUID = Field(..., description="Team ID")
    tokens_used: int = Field(..., description="Number of tokens used")
    cost: float = Field(..., description="Cost of usage")
    usage_type: str = Field(..., description="Type of usage")
    created_at: datetime = Field(..., description="Usage timestamp")


class TokenQuotaResponse(BaseModel):
    """Token quota status response"""
    team_id: UUID = Field(..., description="Team ID")
    quota_limit: int = Field(..., description="Monthly token quota")
    tokens_used: int = Field(..., description="Tokens used this month")
    tokens_remaining: int = Field(..., description="Tokens remaining")
    quota_exceeded: bool = Field(..., description="Whether quota is exceeded")
    usage_breakdown: Dict[str, Dict[str, Any]] = Field(..., description="Usage breakdown by type")


class WebhookResponse(BaseModel):
    """Webhook processing response"""
    status: str = Field(..., description="Processing status")
    message: str = Field(..., description="Processing message")
    comments_processed: int = Field(0, description="Number of comments processed")
    job_id: Optional[str] = Field(None, description="Background job ID")


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
    details: Dict[str, Any] = Field(default_factory=dict, description="Error details")
    status_code: int = Field(..., description="HTTP status code")
    timestamp: str = Field(..., description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    timestamp: datetime = Field(..., description="Health check timestamp")
    dependencies: Dict[str, str] = Field(default_factory=dict, description="Dependency status")
