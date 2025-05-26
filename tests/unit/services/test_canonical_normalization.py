"""
Unit tests for canonical data normalization - critical for consistent data processing
"""

import pytest
from datetime import datetime
from hypothesis import given, strategies as st
from pydantic import ValidationError

from schemas.canonical import (
    CommentNormalizer, CanonicalComment, CanonicalAuthor, CanonicalPost,
    PlatformType, ContentType, SentimentType, EmotionType, CategoryType
)


class TestCommentNormalizer:
    """Test platform-specific data normalization to canonical format"""

    def test_normalize_instagram_comment_complete_data(self):
        """
        Business Critical: Instagram comments must be normalized correctly for consistent processing
        """
        raw_data = {
            "id": "comment_123",
            "text": "Love this post!",
            "timestamp": "2024-01-01T12:00:00Z",
            "from": {
                "id": "user_456",
                "username": "test_user"
            },
            "media": {
                "id": "media_789",
                "permalink": "https://instagram.com/p/abc123"
            }
        }
        
        canonical = CommentNormalizer.normalize_instagram_comment(raw_data)
        
        assert canonical.external_id == "comment_123"
        assert canonical.platform == PlatformType.INSTAGRAM
        assert canonical.message == "Love this post!"
        assert canonical.author.external_id == "user_456"
        assert canonical.author.username == "test_user"
        assert canonical.post.external_id == "media_789"
        assert canonical.post.content_type == ContentType.IMAGE
        assert canonical.platform_metadata == raw_data

    def test_normalize_instagram_comment_missing_optional_fields(self):
        """
        Business Critical: Missing optional fields should not break normalization
        """
        raw_data = {
            "id": "comment_123",
            "text": "Test comment",
            "timestamp": "2024-01-01T12:00:00Z",
            "from": {},  # Missing user data
            "media": {}  # Missing media data
        }
        
        canonical = CommentNormalizer.normalize_instagram_comment(raw_data)
        
        assert canonical.external_id == "comment_123"
        assert canonical.message == "Test comment"
        assert canonical.author.external_id == ""
        assert canonical.author.username is None
        assert canonical.post.external_id == ""

    def test_normalize_twitter_comment_complete_data(self):
        """
        Business Critical: Twitter comments must be normalized with proper engagement metrics
        """
        raw_data = {
            "id_str": "tweet_123",
            "text": "@brand Great service!",
            "created_at": "Wed Oct 10 20:19:24 +0000 2018",
            "in_reply_to_status_id_str": "original_tweet_456",
            "user": {
                "id_str": "user_789",
                "screen_name": "test_user",
                "name": "Test User",
                "profile_image_url_https": "https://pbs.twimg.com/profile_images/test.jpg",
                "verified": True,
                "followers_count": 1000
            },
            "retweet_count": 5,
            "favorite_count": 10
        }
        
        canonical = CommentNormalizer.normalize_twitter_comment(raw_data)
        
        assert canonical.external_id == "tweet_123"
        assert canonical.platform == PlatformType.TWITTER
        assert canonical.message == "@brand Great service!"
        assert canonical.author.external_id == "user_789"
        assert canonical.author.username == "test_user"
        assert canonical.author.display_name == "Test User"
        assert canonical.author.verified is True
        assert canonical.author.follower_count == 1000
        assert canonical.parent_comment_id == "original_tweet_456"
        assert canonical.engagement_metrics["retweets"] == 5
        assert canonical.engagement_metrics["likes"] == 10

    def test_normalize_youtube_comment_with_parent(self):
        """
        Business Critical: YouTube comment replies must preserve parent relationship
        """
        raw_data = {
            "id": "comment_123",
            "snippet": {
                "videoId": "video_456",
                "textDisplay": "Great video!",
                "authorDisplayName": "Test User",
                "authorChannelId": {"value": "channel_789"},
                "authorProfileImageUrl": "https://yt3.ggpht.com/test.jpg",
                "publishedAt": "2024-01-01T12:00:00Z",
                "updatedAt": "2024-01-01T12:30:00Z",
                "parentId": "parent_comment_456",
                "likeCount": 3
            }
        }
        
        canonical = CommentNormalizer.normalize_youtube_comment(raw_data)
        
        assert canonical.external_id == "comment_123"
        assert canonical.platform == PlatformType.YOUTUBE
        assert canonical.message == "Great video!"
        assert canonical.author.external_id == "channel_789"
        assert canonical.author.username == "Test User"
        assert canonical.post.external_id == "video_456"
        assert canonical.post.content_type == ContentType.VIDEO
        assert canonical.parent_comment_id == "parent_comment_456"
        assert canonical.engagement_metrics["likes"] == 3

    def test_normalize_linkedin_comment_business_context(self):
        """
        Business Critical: LinkedIn comments must be normalized for professional context
        """
        raw_data = {
            "comment": {
                "id": "comment_123",
                "author": "urn:li:person:123456",
                "authorName": "John Doe",
                "object": "urn:li:activity:789012",
                "message": {"text": "Excellent insights!"},
                "created": {"time": "2024-01-01T12:00:00Z"}
            }
        }
        
        canonical = CommentNormalizer.normalize_linkedin_comment(raw_data)
        
        assert canonical.external_id == "comment_123"
        assert canonical.platform == PlatformType.LINKEDIN
        assert canonical.message == "Excellent insights!"
        assert canonical.author.external_id == "urn:li:person:123456"
        assert canonical.author.display_name == "John Doe"
        assert canonical.post.external_id == "urn:li:activity:789012"
        assert canonical.post.content_type == ContentType.TEXT

    @given(st.text(min_size=1, max_size=1000))
    def test_canonical_comment_message_validation_hypothesis(self, message_text):
        """
        Business Critical: Comment message validation must handle all possible text inputs
        """
        # Test that any non-empty string is accepted
        comment = CanonicalComment(
            external_id="test_123",
            platform=PlatformType.INSTAGRAM,
            author=CanonicalAuthor(external_id="user_123"),
            post=CanonicalPost(external_id="post_123", content_type=ContentType.TEXT),
            message=message_text,
            created_at=datetime.utcnow()
        )
        
        assert comment.message == message_text.strip()

    def test_canonical_comment_empty_message_raises_error(self):
        """
        Business Critical: Empty messages must be rejected to prevent invalid data
        """
        with pytest.raises(ValidationError, match="Comment message cannot be empty"):
            CanonicalComment(
                external_id="test_123",
                platform=PlatformType.INSTAGRAM,
                author=CanonicalAuthor(external_id="user_123"),
                post=CanonicalPost(external_id="post_123", content_type=ContentType.TEXT),
                message="",  # Empty message
                created_at=datetime.utcnow()
            )

    def test_canonical_comment_whitespace_only_message_raises_error(self):
        """
        Business Critical: Whitespace-only messages must be rejected
        """
        with pytest.raises(ValidationError, match="Comment message cannot be empty"):
            CanonicalComment(
                external_id="test_123",
                platform=PlatformType.INSTAGRAM,
                author=CanonicalAuthor(external_id="user_123"),
                post=CanonicalPost(external_id="post_123", content_type=ContentType.TEXT),
                message="   \n\t   ",  # Whitespace only
                created_at=datetime.utcnow()
            )

    @given(
        st.one_of(
            st.just(PlatformType.INSTAGRAM),
            st.just(PlatformType.TWITTER),
            st.just(PlatformType.YOUTUBE),
            st.just(PlatformType.LINKEDIN)
        ),
        st.text(min_size=1, max_size=500),
        st.text(min_size=1, max_size=100)
    )
    def test_canonical_comment_platform_consistency_hypothesis(self, platform, message, external_id):
        """
        Business Critical: All platform types must work consistently with canonical format
        """
        comment = CanonicalComment(
            external_id=external_id,
            platform=platform,
            author=CanonicalAuthor(external_id="user_123"),
            post=CanonicalPost(external_id="post_123", content_type=ContentType.TEXT),
            message=message,
            created_at=datetime.utcnow()
        )
        
        assert comment.platform == platform
        assert comment.external_id == external_id
        assert comment.message == message.strip()


class TestCanonicalClassification:
    """Test canonical classification data structures"""

    def test_canonical_classification_all_fields_valid(self):
        """
        Business Critical: Classification results must validate correctly for ML pipeline
        """
        from schemas.canonical import CanonicalClassification
        
        classification = CanonicalClassification(
            sentiment=SentimentType.POSITIVE,
            emotion=EmotionType.JOY,
            category=CategoryType.COMPLIMENT,
            confidence_scores={
                "sentiment": 0.95,
                "emotion": 0.87,
                "category": 0.92
            },
            language="en",
            topics=["product", "quality"],
            intent="praise"
        )
        
        assert classification.sentiment == SentimentType.POSITIVE
        assert classification.emotion == EmotionType.JOY
        assert classification.category == CategoryType.COMPLIMENT
        assert classification.confidence_scores["sentiment"] == 0.95
        assert "product" in classification.topics

    @given(
        st.floats(min_value=0.0, max_value=1.0),
        st.floats(min_value=0.0, max_value=1.0),
        st.floats(min_value=0.0, max_value=1.0)
    )
    def test_canonical_classification_confidence_scores_hypothesis(self, sent_conf, emo_conf, cat_conf):
        """
        Business Critical: Confidence scores must be valid probabilities for ML accuracy
        """
        from schemas.canonical import CanonicalClassification
        
        classification = CanonicalClassification(
            sentiment=SentimentType.NEUTRAL,
            emotion=EmotionType.NEUTRAL,
            category=CategoryType.GENERAL,
            confidence_scores={
                "sentiment": sent_conf,
                "emotion": emo_conf,
                "category": cat_conf
            }
        )
        
        assert 0.0 <= classification.confidence_scores["sentiment"] <= 1.0
        assert 0.0 <= classification.confidence_scores["emotion"] <= 1.0
        assert 0.0 <= classification.confidence_scores["category"] <= 1.0


class TestCanonicalReply:
    """Test canonical reply data structures"""

    def test_canonical_reply_valid_data(self):
        """
        Business Critical: Reply data must validate correctly for posting to platforms
        """
        from schemas.canonical import CanonicalReply
        
        reply = CanonicalReply(
            comment_external_id="comment_123",
            platform=PlatformType.INSTAGRAM,
            message="Thank you for your feedback!",
            author_id=uuid4(),
            created_at=datetime.utcnow()
        )
        
        assert reply.comment_external_id == "comment_123"
        assert reply.platform == PlatformType.INSTAGRAM
        assert reply.message == "Thank you for your feedback!"
        assert reply.status == "pending"

    def test_canonical_reply_empty_message_raises_error(self):
        """
        Business Critical: Empty reply messages must be rejected
        """
        from schemas.canonical import CanonicalReply
        
        with pytest.raises(ValidationError, match="Reply message cannot be empty"):
            CanonicalReply(
                comment_external_id="comment_123",
                platform=PlatformType.INSTAGRAM,
                message="",  # Empty message
                author_id=uuid4(),
                created_at=datetime.utcnow()
            )

    def test_canonical_reply_message_trimmed(self):
        """
        Business Critical: Reply messages must be trimmed of whitespace
        """
        from schemas.canonical import CanonicalReply
        
        reply = CanonicalReply(
            comment_external_id="comment_123",
            platform=PlatformType.INSTAGRAM,
            message="  Thank you!  \n",  # Whitespace around message
            author_id=uuid4(),
            created_at=datetime.utcnow()
        )
        
        assert reply.message == "Thank you!"
