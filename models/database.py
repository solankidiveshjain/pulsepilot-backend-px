"""
SQLModel database models for PulsePilot
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, ARRAY, String, JSON


class Team(SQLModel, table=True):
    __tablename__ = "teams"
    
    team_id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=255)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    users: List["User"] = Relationship(back_populates="team")
    social_connections: List["SocialConnection"] = Relationship(back_populates="team")
    comments: List["Comment"] = Relationship(back_populates="team")
    posts: List["Post"] = Relationship(back_populates="team")
    token_usage: List["TokenUsage"] = Relationship(back_populates="team")
    subscriptions: List["Subscription"] = Relationship(back_populates="team")
    api_logs: List["ApiLog"] = Relationship(back_populates="team")


class User(SQLModel, table=True):
    __tablename__ = "users"
    
    user_id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="teams.team_id")
    email: str = Field(unique=True, max_length=255)
    user_name: Optional[str] = Field(default=None, max_length=255)
    avatar_url: Optional[str] = Field(default=None)
    roles: List[str] = Field(sa_column=Column(ARRAY(String)))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    team: Team = Relationship(back_populates="users")
    replies: List["Reply"] = Relationship(back_populates="user")


class SocialConnection(SQLModel, table=True):
    __tablename__ = "social_connections"
    
    connection_id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="teams.team_id")
    platform: str = Field(max_length=50)
    status: str = Field(max_length=20)  # connected, disconnected
    access_token: str
    refresh_token: Optional[str] = Field(default=None)
    token_expires: Optional[datetime] = Field(default=None)
    metadata: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    team: Team = Relationship(back_populates="social_connections")


class Comment(SQLModel, table=True):
    __tablename__ = "comments"
    
    comment_id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="teams.team_id")
    platform: str = Field(max_length=50)
    author: Optional[str] = Field(default=None)
    message: Optional[str] = Field(default=None)
    post_id: Optional[UUID] = Field(default=None, foreign_key="posts.post_id")
    archived: bool = Field(default=False)
    flagged: bool = Field(default=False)
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(768)))
    metadata: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    team: Team = Relationship(back_populates="comments")
    post: Optional["Post"] = Relationship(back_populates="comments")
    replies: List["Reply"] = Relationship(back_populates="comment")
    ai_suggestions: List["AiSuggestion"] = Relationship(back_populates="comment")


class Reply(SQLModel, table=True):
    __tablename__ = "replies"
    
    reply_id: UUID = Field(default_factory=uuid4, primary_key=True)
    comment_id: UUID = Field(foreign_key="comments.comment_id")
    user_id: UUID = Field(foreign_key="users.user_id")
    message: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    comment: Comment = Relationship(back_populates="replies")
    user: User = Relationship(back_populates="replies")


class AiSuggestion(SQLModel, table=True):
    __tablename__ = "ai_suggestions"
    
    suggestion_id: UUID = Field(default_factory=uuid4, primary_key=True)
    comment_id: UUID = Field(foreign_key="comments.comment_id")
    suggested_reply: str
    score: Optional[float] = Field(default=None)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    comment: Comment = Relationship(back_populates="ai_suggestions")


class Post(SQLModel, table=True):
    __tablename__ = "posts"
    
    post_id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="teams.team_id")
    platform: Optional[str] = Field(default=None, max_length=50)
    type: Optional[str] = Field(default=None, max_length=20)  # text, image, video, link
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    
    # Relationships
    team: Team = Relationship(back_populates="posts")
    comments: List[Comment] = Relationship(back_populates="post")


class TokenUsage(SQLModel, table=True):
    __tablename__ = "token_usage"
    
    usage_id: int = Field(primary_key=True)
    team_id: UUID = Field(foreign_key="teams.team_id")
    tokens_used: int
    usage_type: str = Field(max_length=20)  # embedding, classification, generation
    cost: Optional[float] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    team: Team = Relationship(back_populates="token_usage")


class Pricing(SQLModel, table=True):
    __tablename__ = "pricing"
    
    pricing_id: int = Field(primary_key=True)
    usage_type: str = Field(unique=True, max_length=20)  # embedding, classification, generation
    price_per_token: float
    effective_date: datetime = Field(default_factory=datetime.utcnow)


class Subscription(SQLModel, table=True):
    __tablename__ = "subscriptions"
    
    subscription_id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="teams.team_id")
    plan: Optional[str] = Field(default=None)
    monthly_token_quota: Optional[int] = Field(default=None)
    price: Optional[float] = Field(default=None)
    billing_cycle: Optional[str] = Field(default=None, max_length=20)  # monthly, annual
    start_date: datetime = Field(default_factory=datetime.utcnow)
    end_date: Optional[datetime] = Field(default=None)
    status: Optional[str] = Field(default=None, max_length=20)  # active, cancelled, expired
    
    # Relationships
    team: Team = Relationship(back_populates="subscriptions")


class ApiLog(SQLModel, table=True):
    __tablename__ = "api_logs"
    
    log_id: int = Field(primary_key=True)
    team_id: Optional[UUID] = Field(default=None, foreign_key="teams.team_id")
    endpoint: Optional[str] = Field(default=None)
    method: Optional[str] = Field(default=None, max_length=10)
    status_code: Optional[int] = Field(default=None)
    response_time_ms: Optional[int] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    team: Optional[Team] = Relationship(back_populates="api_logs")
