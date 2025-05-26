"""
Canonical schemas for normalizing social media data
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field, validator
from enum import Enum


class PlatformType(str, Enum):
    """Supported social media platforms"""
    INSTAGRAM = "instagram"
    TWITTER = "twitter"
    YOUTUBE = "youtube"
    LINKEDIN = "linkedin"


class ContentType(str, Enum):
    """Types of social media content"""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    LINK = "link"
    STORY = "story"


class SentimentType(str, Enum):
    """Sentiment classifications"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class EmotionType(str, Enum):
    """Emotion classifications"""
    JOY = "joy"
    ANGER = "anger"
    SADNESS = "sadness"
    FEAR = "fear"
    SURPRISE = "surprise"
    DISGUST = "disgust"
    NEUTRAL = "neutral"


class CategoryType(str, Enum):
    """Comment categories"""
    QUESTION = "question"
    COMPLAINT = "complaint"
    COMPLIMENT = "compliment"
    SUGGESTION = "suggestion"
    GENERAL = "general"


class CanonicalAuthor(BaseModel):
    """Normalized author information"""
    external_id: str = Field(..., description="Platform-specific user ID")
    username: Optional[str] = Field(None, description="Username or handle")
    display_name: Optional[str] = Field(None, description="Display name")
    avatar_url: Optional[str] = Field(None, description="Profile picture URL")
    verified: bool = Field(False, description="Whether account is verified")
    follower_count: Optional[int] = Field(None, description="Number of followers")


class CanonicalPost(BaseModel):
    """Normalized post information"""
    external_id: str = Field(..., description="Platform-specific post ID")
    content_type: ContentType = Field(..., description="Type of content")
    text: Optional[str] = Field(None, description="Post text content")
    media_urls: List[str] = Field(default_factory=list, description="Media URLs")
    url: Optional[str] = Field(None, description="Post URL")
    created_at: Optional[datetime] = Field(None, description="Post creation time")
    engagement_metrics: Dict[str, int] = Field(default_factory=dict, description="Likes, shares, etc.")


class CanonicalComment(BaseModel):
    """Normalized comment data"""
    external_id: str = Field(..., description="Platform-specific comment ID")
    platform: PlatformType = Field(..., description="Source platform")
    author: CanonicalAuthor = Field(..., description="Comment author")
    post: CanonicalPost = Field(..., description="Parent post")
    message: str = Field(..., description="Comment text")
    created_at: datetime = Field(..., description="Comment creation time")
    updated_at: Optional[datetime] = Field(None, description="Last update time")
    parent_comment_id: Optional[str] = Field(None, description="Parent comment ID for replies")
    engagement_metrics: Dict[str, int] = Field(default_factory=dict, description="Likes, replies, etc.")
    language: Optional[str] = Field(None, description="Detected language code")
    is_spam: bool = Field(False, description="Whether comment is spam")
    is_offensive: bool = Field(False, description="Whether comment is offensive")
    platform_metadata: Dict[str, Any] = Field(default_factory=dict, description="Platform-specific data")
    
    @validator('message')
    def validate_message(cls, v):
        if not v or not v.strip():
            raise ValueError("Comment message cannot be empty")
        return v.strip()


class CanonicalClassification(BaseModel):
    """Normalized classification results"""
    sentiment: SentimentType = Field(..., description="Sentiment classification")
    emotion: EmotionType = Field(..., description="Emotion classification")
    category: CategoryType = Field(..., description="Category classification")
    confidence_scores: Dict[str, float] = Field(..., description="Confidence scores for each classification")
    language: Optional[str] = Field(None, description="Detected language")
    topics: List[str] = Field(default_factory=list, description="Extracted topics/keywords")
    intent: Optional[str] = Field(None, description="User intent")


class CanonicalReply(BaseModel):
    """Normalized reply data"""
    external_id: Optional[str] = Field(None, description="Platform-specific reply ID")
    comment_external_id: str = Field(..., description="Parent comment external ID")
    platform: PlatformType = Field(..., description="Target platform")
    message: str = Field(..., description="Reply text")
    author_id: UUID = Field(..., description="Internal user ID who created reply")
    created_at: datetime = Field(..., description="Reply creation time")
    submitted_at: Optional[datetime] = Field(None, description="When reply was submitted to platform")
    status: str = Field("pending", description="Reply status: pending, submitted, failed")
    error_message: Optional[str] = Field(None, description="Error message if submission failed")
    platform_metadata: Dict[str, Any] = Field(default_factory=dict, description="Platform-specific data")
    
    @validator('message')
    def validate_message(cls, v):
        if not v or not v.strip():
            raise ValueError("Reply message cannot be empty")
        return v.strip()


class CommentNormalizer:
    """Utility class for normalizing platform-specific data to canonical format"""
    
    @staticmethod
    def normalize_instagram_comment(raw_data: Dict[str, Any]) -> CanonicalComment:
        """Normalize Instagram comment data"""
        author_data = raw_data.get("from", {})
        media_data = raw_data.get("media", {})
        
        author = CanonicalAuthor(
            external_id=author_data.get("id", ""),
            username=author_data.get("username"),
            display_name=author_data.get("username")  # Instagram uses username as display name
        )
        
        post = CanonicalPost(
            external_id=media_data.get("id", ""),
            content_type=ContentType.IMAGE,  # Instagram is primarily images
            url=media_data.get("permalink")
        )
        
        return CanonicalComment(
            external_id=raw_data.get("id", ""),
            platform=PlatformType.INSTAGRAM,
            author=author,
            post=post,
            message=raw_data.get("text", ""),
            created_at=datetime.fromisoformat(raw_data.get("timestamp", datetime.utcnow().isoformat())),
            platform_metadata=raw_data
        )
    
    @staticmethod
    def normalize_twitter_comment(raw_data: Dict[str, Any]) -> CanonicalComment:
        """Normalize Twitter comment data"""
        user_data = raw_data.get("user", {})
        
        author = CanonicalAuthor(
            external_id=user_data.get("id_str", ""),
            username=user_data.get("screen_name"),
            display_name=user_data.get("name"),
            avatar_url=user_data.get("profile_image_url_https"),
            verified=user_data.get("verified", False),
            follower_count=user_data.get("followers_count")
        )
        
        post = CanonicalPost(
            external_id=raw_data.get("in_reply_to_status_id_str", ""),
            content_type=ContentType.TEXT,
            text=raw_data.get("text", ""),
            created_at=datetime.strptime(raw_data.get("created_at", ""), "%a %b %d %H:%M:%S %z %Y") if raw_data.get("created_at") else None
        )
        
        return CanonicalComment(
            external_id=raw_data.get("id_str", ""),
            platform=PlatformType.TWITTER,
            author=author,
            post=post,
            message=raw_data.get("text", ""),
            created_at=datetime.strptime(raw_data.get("created_at", ""), "%a %b %d %H:%M:%S %z %Y") if raw_data.get("created_at") else datetime.utcnow(),
            parent_comment_id=raw_data.get("in_reply_to_status_id_str"),
            engagement_metrics={
                "retweets": raw_data.get("retweet_count", 0),
                "likes": raw_data.get("favorite_count", 0)
            },
            platform_metadata=raw_data
        )
    
    @staticmethod
    def normalize_youtube_comment(raw_data: Dict[str, Any]) -> CanonicalComment:
        """Normalize YouTube comment data"""
        snippet = raw_data.get("snippet", {})
        
        author = CanonicalAuthor(
            external_id=snippet.get("authorChannelId", {}).get("value", ""),
            username=snippet.get("authorDisplayName"),
            display_name=snippet.get("authorDisplayName"),
            avatar_url=snippet.get("authorProfileImageUrl")
        )
        
        post = CanonicalPost(
            external_id=snippet.get("videoId", ""),
            content_type=ContentType.VIDEO,
            url=f"https://youtube.com/watch?v={snippet.get('videoId', '')}" if snippet.get("videoId") else None
        )
        
        return CanonicalComment(
            external_id=raw_data.get("id", ""),
            platform=PlatformType.YOUTUBE,
            author=author,
            post=post,
            message=snippet.get("textDisplay", ""),
            created_at=datetime.fromisoformat(snippet.get("publishedAt", datetime.utcnow().isoformat()).replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(snippet.get("updatedAt", datetime.utcnow().isoformat()).replace("Z", "+00:00")) if snippet.get("updatedAt") else None,
            parent_comment_id=snippet.get("parentId"),
            engagement_metrics={
                "likes": snippet.get("likeCount", 0)
            },
            platform_metadata=raw_data
        )
    
    @staticmethod
    def normalize_linkedin_comment(raw_data: Dict[str, Any]) -> CanonicalComment:
        """Normalize LinkedIn comment data"""
        comment_data = raw_data.get("comment", {})
        
        author = CanonicalAuthor(
            external_id=comment_data.get("author", ""),
            username=comment_data.get("author"),  # LinkedIn uses URNs
            display_name=comment_data.get("authorName")
        )
        
        post = CanonicalPost(
            external_id=comment_data.get("object", ""),
            content_type=ContentType.TEXT
        )
        
        return CanonicalComment(
            external_id=comment_data.get("id", ""),
            platform=PlatformType.LINKEDIN,
            author=author,
            post=post,
            message=comment_data.get("message", {}).get("text", ""),
            created_at=datetime.fromisoformat(comment_data.get("created", {}).get("time", datetime.utcnow().isoformat())),
            platform_metadata=raw_data
        )
