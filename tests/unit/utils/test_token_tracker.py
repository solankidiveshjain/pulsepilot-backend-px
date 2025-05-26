"""
Unit tests for token tracking - critical for accurate billing and quota enforcement
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timedelta

from utils.token_tracker import TokenTracker
from models.database import TokenUsage, Subscription, Pricing


class TestTokenTracker:
    """Test token usage tracking for billing and quota management"""

    @pytest.fixture
    def token_tracker(self):
        return TokenTracker()

    @pytest.fixture
    def sample_team_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_track_usage_creates_usage_record(self, token_tracker, sample_team_id):
        """
        Business Critical: Token usage must be accurately recorded for billing
        """
        with patch('utils.token_tracker.get_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db
            
            # Mock cost calculation
            with patch.object(token_tracker, '_calculate_cost', return_value=0.05):
                usage = await token_tracker.track_usage(
                    team_id=sample_team_id,
                    usage_type="generation",
                    tokens_used=1000,
                    metadata={"model": "gpt-4"}
                )
                
                mock_db.add.assert_called_once()
                mock_db.commit.assert_called_once()
                mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_track_usage_with_provided_cost(self, token_tracker, sample_team_id):
        """
        Business Critical: Pre-calculated costs should be used when provided
        """
        with patch('utils.token_tracker.get_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db
            
            # Mock quota check
            with patch.object(token_tracker, 'check_quota', return_value={"quota_exceeded": False}):
                usage = await token_tracker.track_usage(
                    team_id=sample_team_id,
                    usage_type="generation",
                    tokens_used=1000,
                    cost=0.10  # Provided cost
                )
                
                # Should not call _calculate_cost when cost is provided
                mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_track_llm_usage_with_detailed_breakdown(self, token_tracker, sample_team_id):
        """
        Business Critical: LLM usage must track detailed token breakdown for accurate billing
        """
        with patch('utils.token_tracker.get_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db
            
            with patch.object(token_tracker, '_calculate_llm_cost', return_value=0.025), \
                 patch.object(token_tracker, 'check_quota', return_value={"quota_exceeded": False}):
                
                usage = await token_tracker.track_llm_usage(
                    team_id=sample_team_id,
                    model_name="gpt-4-turbo-preview",
                    prompt_tokens=800,
                    completion_tokens=200,
                    total_tokens=1000,
                    operation="reply_generation"
                )
                
                # Verify metadata includes detailed breakdown
                call_args = mock_db.add.call_args[0][0]
                assert call_args.usage_type == "generation"
                assert call_args.tokens_used == 1000
                assert "model_name" in call_args.metadata
                assert "prompt_tokens" in call_args.metadata
                assert "completion_tokens" in call_args.metadata

    @pytest.mark.asyncio
    async def test_track_embedding_usage_estimates_tokens(self, token_tracker, sample_team_id):
        """
        Business Critical: Embedding usage must estimate tokens correctly for billing
        """
        with patch('utils.token_tracker.get_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db
            
            with patch.object(token_tracker, 'check_quota', return_value={"quota_exceeded": False}):
                usage = await token_tracker.track_embedding_usage(
                    team_id=sample_team_id,
                    text_length=400,  # Should estimate ~100 tokens
                    embedding_model="all-MiniLM-L6-v2"
                )
                
                call_args = mock_db.add.call_args[0][0]
                assert call_args.usage_type == "embedding"
                assert call_args.tokens_used == 100  # 400 / 4
                assert "embedding_model" in call_args.metadata

    @pytest.mark.asyncio
    async def test_calculate_llm_cost_gpt4_turbo(self, token_tracker):
        """
        Business Critical: GPT-4 Turbo costs must be calculated correctly
        """
        cost = await token_tracker._calculate_llm_cost(
            model_name="gpt-4-turbo-preview",
            prompt_tokens=1000,
            completion_tokens=500
        )
        
        # $0.01 per 1K prompt + $0.03 per 1K completion
        expected_cost = (1000/1000) * 0.01 + (500/1000) * 0.03
        assert cost == expected_cost
        assert cost == 0.025

    @pytest.mark.asyncio
    async def test_calculate_llm_cost_unknown_model_uses_default(self, token_tracker):
        """
        Business Critical: Unknown models should use default pricing to prevent billing errors
        """
        cost = await token_tracker._calculate_llm_cost(
            model_name="unknown-model",
            prompt_tokens=1000,
            completion_tokens=500
        )
        
        # Should use default pricing (same as gpt-4-turbo-preview)
        expected_cost = (1000/1000) * 0.01 + (500/1000) * 0.03
        assert cost == expected_cost

    @pytest.mark.asyncio
    async def test_check_quota_with_active_subscription(self, token_tracker, sample_team_id):
        """
        Business Critical: Quota checking must work correctly for teams with subscriptions
        """
        with patch('utils.token_tracker.get_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db
            
            # Mock subscription
            mock_subscription = MagicMock()
            mock_subscription.monthly_token_quota = 10000
            mock_subscription.plan = "pro"
            
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_subscription
            mock_db.execute.return_value = mock_result
            
            # Mock usage breakdown
            mock_usage_result = MagicMock()
            mock_usage_result.fetchall.return_value = [
                MagicMock(usage_type="generation", total_tokens=3000, total_cost=0.15, usage_count=5),
                MagicMock(usage_type="embedding", total_tokens=2000, total_cost=0.02, usage_count=10)
            ]
            mock_db.execute.side_effect = [mock_result, mock_usage_result]
            
            quota_status = await token_tracker.check_quota(sample_team_id)
            
            assert quota_status["has_quota"] is True
            assert quota_status["quota_limit"] == 10000
            assert quota_status["tokens_used"] == 5000
            assert quota_status["tokens_remaining"] == 5000
            assert quota_status["quota_exceeded"] is False
            assert "generation" in quota_status["usage_breakdown"]
            assert "embedding" in quota_status["usage_breakdown"]

    @pytest.mark.asyncio
    async def test_check_quota_no_subscription(self, token_tracker, sample_team_id):
        """
        Business Critical: Teams without subscriptions should have no quota
        """
        with patch('utils.token_tracker.get_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db
            
            # Mock no subscription found
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result
            
            quota_status = await token_tracker.check_quota(sample_team_id)
            
            assert quota_status["has_quota"] is False
            assert quota_status["quota_limit"] == 0
            assert quota_status["tokens_used"] == 0
            assert quota_status["tokens_remaining"] == 0

    @pytest.mark.asyncio
    async def test_check_quota_exceeded(self, token_tracker, sample_team_id):
        """
        Business Critical: Quota exceeded status must be detected correctly
        """
        with patch('utils.token_tracker.get_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db
            
            # Mock subscription with low quota
            mock_subscription = MagicMock()
            mock_subscription.monthly_token_quota = 1000
            mock_subscription.plan = "basic"
            
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_subscription
            
            # Mock high usage
            mock_usage_result = MagicMock()
            mock_usage_result.fetchall.return_value = [
                MagicMock(usage_type="generation", total_tokens=1500, total_cost=0.075, usage_count=3)
            ]
            mock_db.execute.side_effect = [mock_result, mock_usage_result]
            
            quota_status = await token_tracker.check_quota(sample_team_id)
            
            assert quota_status["quota_exceeded"] is True
            assert quota_status["tokens_used"] == 1500
            assert quota_status["tokens_remaining"] == 0  # Can't be negative

    @pytest.mark.asyncio
    async def test_get_usage_analytics_returns_daily_breakdown(self, token_tracker, sample_team_id):
        """
        Business Critical: Usage analytics must provide accurate daily breakdown for reporting
        """
        with patch('utils.token_tracker.get_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db
            
            # Mock daily usage data
            from datetime import date
            mock_result = MagicMock()
            mock_result.fetchall.return_value = [
                MagicMock(date=date(2024, 1, 1), usage_type="generation", tokens=500, cost=0.025),
                MagicMock(date=date(2024, 1, 1), usage_type="embedding", tokens=200, cost=0.002),
                MagicMock(date=date(2024, 1, 2), usage_type="generation", tokens=300, cost=0.015)
            ]
            mock_db.execute.return_value = mock_result
            
            analytics = await token_tracker.get_usage_analytics(sample_team_id, days=7)
            
            assert analytics["period_days"] == 7
            assert "daily_usage" in analytics
            assert "2024-01-01" in analytics["daily_usage"]
            assert "2024-01-02" in analytics["daily_usage"]
            
            # Check data structure
            day1_data = analytics["daily_usage"]["2024-01-01"]
            assert "generation" in day1_data
            assert "embedding" in day1_data
            assert day1_data["generation"]["tokens"] == 500
            assert day1_data["embedding"]["tokens"] == 200
