"""
Unit tests for webhook idempotency - critical for preventing duplicate processing
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timedelta
import hashlib
import json

from services.webhook_idempotency import WebhookIdempotencyService, WebhookEvent
from models.database import Comment


class TestWebhookIdempotencyService:
    """Test webhook idempotency to prevent duplicate comment processing"""

    @pytest.fixture
    def service(self):
        return WebhookIdempotencyService()

    @pytest.fixture
    def sample_payload(self):
        return {
            "id": "comment_123",
            "text": "Test comment",
            "timestamp": "2024-01-01T00:00:00Z"
        }

    @pytest.mark.asyncio
    async def test_is_duplicate_event_returns_true_for_duplicate(self, service, sample_payload):
        """
        Business Critical: Prevents duplicate comment processing when webhooks are retried
        """
        with patch('services.webhook_idempotency.get_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db
            
            # Mock database returning count > 0 (duplicate found)
            mock_result = MagicMock()
            mock_result.scalar.return_value = 1
            mock_db.execute.return_value = mock_result
            
            is_duplicate = await service.is_duplicate_event(
                platform="instagram",
                external_id="comment_123",
                payload=sample_payload
            )
            
            assert is_duplicate is True
            mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_duplicate_event_returns_false_for_new_event(self, service, sample_payload):
        """
        Business Critical: Allows processing of new, unique webhook events
        """
        with patch('services.webhook_idempotency.get_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db
            
            # Mock database returning count = 0 (no duplicate)
            mock_result = MagicMock()
            mock_result.scalar.return_value = 0
            mock_db.execute.return_value = mock_result
            
            is_duplicate = await service.is_duplicate_event(
                platform="instagram",
                external_id="comment_123",
                payload=sample_payload
            )
            
            assert is_duplicate is False

    @pytest.mark.asyncio
    async def test_record_webhook_event_stores_event_data(self, service, sample_payload):
        """
        Business Critical: Records webhook events for idempotency tracking
        """
        team_id = uuid4()
        
        with patch('services.webhook_idempotency.get_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db
            
            await service.record_webhook_event(
                platform="instagram",
                external_id="comment_123",
                event_type="comment_created",
                payload=sample_payload,
                team_id=team_id
            )
            
            mock_db.execute.assert_called_once()
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_comment_creates_new_comment(self, service, sample_team_id):
        """
        Business Critical: Creates new comments from webhook data when they don't exist
        """
        with patch('services.webhook_idempotency.get_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db
            
            # Mock no existing comment found
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result
            
            comment = await service.upsert_comment(
                platform="instagram",
                external_id="comment_123",
                author="test_user",
                message="Test comment",
                team_id=sample_team_id,
                post_id="post_456"
            )
            
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_comment_returns_existing_comment(self, service, sample_team_id, sample_comment):
        """
        Business Critical: Returns existing comment without creating duplicate
        """
        with patch('services.webhook_idempotency.get_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db
            
            # Mock existing comment found
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = sample_comment
            mock_db.execute.return_value = mock_result
            
            comment = await service.upsert_comment(
                platform="instagram",
                external_id="comment_123",
                author="test_user",
                message="Test comment",
                team_id=sample_team_id
            )
            
            assert comment == sample_comment
            mock_db.add.assert_not_called()
            mock_db.commit.assert_not_called()

    def test_generate_payload_hash_deterministic(self, service):
        """
        Business Critical: Same payload must always generate same hash for deduplication
        """
        payload1 = {"id": "123", "text": "test", "timestamp": "2024-01-01"}
        payload2 = {"timestamp": "2024-01-01", "id": "123", "text": "test"}  # Different order
        
        hash1 = service._generate_payload_hash(payload1)
        hash2 = service._generate_payload_hash(payload2)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length

    def test_generate_payload_hash_different_for_different_payloads(self, service):
        """
        Business Critical: Different payloads must generate different hashes
        """
        payload1 = {"id": "123", "text": "test1"}
        payload2 = {"id": "123", "text": "test2"}
        
        hash1 = service._generate_payload_hash(payload1)
        hash2 = service._generate_payload_hash(payload2)
        
        assert hash1 != hash2

    @pytest.mark.asyncio
    async def test_cleanup_old_events_removes_expired_events(self, service):
        """
        Business Critical: Prevents webhook_events table from growing indefinitely
        """
        with patch('services.webhook_idempotency.get_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db
            
            # Mock deletion result
            mock_result = MagicMock()
            mock_result.rowcount = 5
            mock_db.execute.return_value = mock_result
            
            deleted_count = await service.cleanup_old_events()
            
            assert deleted_count == 5
            mock_db.execute.assert_called_once()
            mock_db.commit.assert_called_once()
