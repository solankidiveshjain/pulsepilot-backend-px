"""
Pytest configuration and shared fixtures for PulsePilot backend tests
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from typing import Dict, Any, List

from models.database import Comment, Team, Reply, TokenUsage
from utils.config import Config


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_config():
    """Mock configuration with all required secrets"""
    config = MagicMock(spec=Config)
    config.postgres_url = "postgresql://test:test@localhost/test"
    config.supabase_url = "https://test.supabase.co"
    config.supabase_jwt_secret = "test-jwt-secret-32-chars-long-123"
    config.supabase_service_role_key = "test-service-role-key"
    config.openai_api_key = "sk-test-openai-key"
    config.webhook_secret_key = "test-webhook-secret-32-chars-long"
    config.jwt_secret_key = "test-jwt-secret-32-chars-long-456"
    config.instagram_app_secret = "test-instagram-secret"
    config.twitter_consumer_secret = "test-twitter-secret"
    config.youtube_client_secret = "test-youtube-secret"
    config.linkedin_client_secret = "test-linkedin-secret"
    config.redis_url = "redis://localhost:6379"
    config.environment = "test"
    config.log_level = "DEBUG"
    return config


@pytest.fixture
def sample_team_id():
    """Sample team UUID for testing"""
    return uuid4()


@pytest.fixture
def sample_comment(sample_team_id):
    """Sample comment for testing"""
    return Comment(
        comment_id=uuid4(),
        team_id=sample_team_id,
        platform="instagram",
        author="test_user",
        message="This is a test comment",
        metadata={"external_id": "test_123", "post_id": "post_456"}
    )


@pytest.fixture
def sample_team(sample_team_id):
    """Sample team for testing"""
    return Team(
        team_id=sample_team_id,
        team_name="Test Team",
        metadata={
            "persona": {
                "voice": "Professional and friendly",
                "tone": "Helpful and engaging",
                "guidelines": "Be responsive and maintain brand consistency"
            }
        }
    )


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response"""
    return {
        "suggestions": [
            {"text": "Thank you for your feedback!", "score": 0.9, "tone": "friendly"},
            {"text": "We appreciate your comment.", "score": 0.8, "tone": "professional"},
            {"text": "Thanks for reaching out!", "score": 0.7, "tone": "casual"}
        ],
        "reasoning": "Generated friendly responses based on positive sentiment"
    }


@pytest.fixture
def instagram_webhook_payload():
    """Sample Instagram webhook payload"""
    return {
        "entry": [
            {
                "id": "page_123",
                "changes": [
                    {
                        "field": "comments",
                        "value": {
                            "id": "comment_456",
                            "text": "Great post!",
                            "from": {"username": "test_user", "id": "user_789"},
                            "media": {"id": "media_123"}
                        }
                    }
                ]
            }
        ]
    }


@pytest.fixture
def twitter_webhook_payload():
    """Sample Twitter webhook payload"""
    return {
        "tweet_create_events": [
            {
                "id_str": "tweet_123",
                "text": "@brand This is awesome!",
                "in_reply_to_status_id_str": "original_tweet_456",
                "user": {
                    "id_str": "user_789",
                    "screen_name": "test_user",
                    "name": "Test User"
                },
                "created_at": "Wed Oct 10 20:19:24 +0000 2018"
            }
        ]
    }
