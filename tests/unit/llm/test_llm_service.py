"""
Unit tests for LLM service - critical for AI reply generation accuracy and cost control
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from services.llm_service import LLMService, TokenCounterCallback, SuggestionOutput
from models.database import Comment


class TestTokenCounterCallback:
    """Test token counting for accurate billing"""

    def test_token_counter_initialization(self):
        """
        Business Critical: Token counter must start with zero values for accurate billing
        """
        callback = TokenCounterCallback()
        
        assert callback.total_tokens == 0
        assert callback.prompt_tokens == 0
        assert callback.completion_tokens == 0

    def test_token_counter_on_llm_end_updates_counts(self):
        """
        Business Critical: Token usage must be accurately tracked for billing
        """
        callback = TokenCounterCallback()
        
        # Mock LLM response with token usage
        mock_response = MagicMock()
        mock_response.llm_output = {
            "token_usage": {
                "total_tokens": 100,
                "prompt_tokens": 60,
                "completion_tokens": 40
            }
        }
        
        callback.on_llm_end(mock_response)
        
        assert callback.total_tokens == 100
        assert callback.prompt_tokens == 60
        assert callback.completion_tokens == 40

    def test_token_counter_accumulates_multiple_calls(self):
        """
        Business Critical: Multiple LLM calls must accumulate token usage correctly
        """
        callback = TokenCounterCallback()
        
        # First call
        mock_response1 = MagicMock()
        mock_response1.llm_output = {"token_usage": {"total_tokens": 50, "prompt_tokens": 30, "completion_tokens": 20}}
        callback.on_llm_end(mock_response1)
        
        # Second call
        mock_response2 = MagicMock()
        mock_response2.llm_output = {"token_usage": {"total_tokens": 75, "prompt_tokens": 45, "completion_tokens": 30}}
        callback.on_llm_end(mock_response2)
        
        assert callback.total_tokens == 125
        assert callback.prompt_tokens == 75
        assert callback.completion_tokens == 50

    def test_token_counter_handles_missing_token_usage(self):
        """
        Business Critical: Missing token usage data should not crash billing
        """
        callback = TokenCounterCallback()
        
        # Mock response without token usage
        mock_response = MagicMock()
        mock_response.llm_output = {}
        
        callback.on_llm_end(mock_response)
        
        assert callback.total_tokens == 0
        assert callback.prompt_tokens == 0
        assert callback.completion_tokens == 0


class TestLLMService:
    """Test LLM service for reply generation"""

    @pytest.fixture
    def llm_service(self):
        with patch('services.llm_service.ChatOpenAI'), \
             patch('services.llm_service.os.getenv', return_value="sk-test-key"):
            return LLMService()

    @pytest.fixture
    def sample_comment(self):
        return Comment(
            comment_id=uuid4(),
            team_id=uuid4(),
            platform="instagram",
            author="test_user",
            message="This product is amazing!"
        )

    @pytest.mark.asyncio
    async def test_generate_reply_suggestions_success(self, llm_service, sample_comment, mock_openai_response):
        """
        Business Critical: LLM must generate valid reply suggestions for customer engagement
        """
        with patch.object(llm_service.prompt_template, '__or__') as mock_chain:
            # Mock the chain execution
            mock_chain_result = AsyncMock()
            mock_chain_result.ainvoke.return_value = mock_openai_response
            mock_chain.return_value.__or__.return_value = mock_chain_result
            
            result = await llm_service.generate_reply_suggestions(
                comment=sample_comment,
                similar_comments=[],
                team_id=uuid4(),
                persona_guidelines="Be friendly and professional"
            )
            
            assert "suggestions" in result
            assert "reasoning" in result
            assert "tokens_used" in result
            assert "cost" in result
            assert len(result["suggestions"]) == 3

    @pytest.mark.asyncio
    async def test_generate_reply_suggestions_empty_message_raises_error(self, llm_service):
        """
        Business Critical: Empty comments should not be processed to avoid wasted LLM costs
        """
        comment = Comment(
            comment_id=uuid4(),
            team_id=uuid4(),
            platform="instagram",
            author="test_user",
            message=""  # Empty message
        )
        
        with pytest.raises(ValueError, match="Comment message is required"):
            await llm_service.generate_reply_suggestions(
                comment=comment,
                similar_comments=[],
                team_id=uuid4()
            )

    @pytest.mark.asyncio
    async def test_generate_reply_suggestions_none_message_raises_error(self, llm_service):
        """
        Business Critical: None messages should not be processed
        """
        comment = Comment(
            comment_id=uuid4(),
            team_id=uuid4(),
            platform="instagram",
            author="test_user",
            message=None  # None message
        )
        
        with pytest.raises(ValueError, match="Comment message is required"):
            await llm_service.generate_reply_suggestions(
                comment=comment,
                similar_comments=[],
                team_id=uuid4()
            )

    @pytest.mark.asyncio
    async def test_generate_reply_suggestions_llm_failure_raises_exception(self, llm_service, sample_comment):
        """
        Business Critical: LLM failures must be handled gracefully with clear error messages
        """
        with patch.object(llm_service.prompt_template, '__or__') as mock_chain:
            # Mock chain to raise exception
            mock_chain_result = AsyncMock()
            mock_chain_result.ainvoke.side_effect = Exception("OpenAI API error")
            mock_chain.return_value.__or__.return_value = mock_chain_result
            
            with pytest.raises(Exception, match="LLM generation failed: OpenAI API error"):
                await llm_service.generate_reply_suggestions(
                    comment=sample_comment,
                    similar_comments=[],
                    team_id=uuid4()
                )

    def test_format_similar_replies_with_replies(self, llm_service):
        """
        Business Critical: Similar replies must be formatted correctly for LLM context
        """
        # Mock comments with replies
        comment1 = MagicMock()
        comment1.message = "Great product!"
        reply1 = MagicMock()
        reply1.message = "Thank you for your feedback!"
        comment1.replies = [reply1]
        
        comment2 = MagicMock()
        comment2.message = "Love this!"
        reply2 = MagicMock()
        reply2.message = "We're glad you love it!"
        comment2.replies = [reply2]
        
        similar_comments = [comment1, comment2]
        
        result = llm_service._format_similar_replies(similar_comments)
        
        assert "Great product!" in result
        assert "Thank you for your feedback!" in result
        assert "Love this!" in result
        assert "We're glad you love it!" in result

    def test_format_similar_replies_no_replies(self, llm_service):
        """
        Business Critical: Comments without replies should return appropriate message
        """
        comment = MagicMock()
        comment.message = "Test comment"
        comment.replies = []
        
        result = llm_service._format_similar_replies([comment])
        
        assert result == "No similar replies found."

    def test_format_similar_replies_empty_list(self, llm_service):
        """
        Business Critical: Empty similar comments should return appropriate message
        """
        result = llm_service._format_similar_replies([])
        
        assert result == "No similar replies found."

    def test_format_suggestions_valid_data(self, llm_service):
        """
        Business Critical: LLM suggestions must be formatted correctly for API response
        """
        raw_suggestions = [
            {"text": "Thank you!", "score": 0.9},
            {"text": "We appreciate it!", "score": 0.8},
            {"text": "Thanks for sharing!", "score": 0.7}
        ]
        
        result = llm_service._format_suggestions(raw_suggestions)
        
        assert len(result) == 3
        assert result[0] == ("Thank you!", 0.9)
        assert result[1] == ("We appreciate it!", 0.8)
        assert result[2] == ("Thanks for sharing!", 0.7)

    def test_format_suggestions_missing_fields(self, llm_service):
        """
        Business Critical: Malformed LLM responses should be handled gracefully
        """
        raw_suggestions = [
            {"text": "Valid suggestion", "score": 0.9},
            {"score": 0.8},  # Missing text
            {"text": "", "score": 0.7},  # Empty text
            {"text": "Another valid", "score": "invalid"}  # Invalid score
        ]
        
        result = llm_service._format_suggestions(raw_suggestions)
        
        # Should only include valid suggestions
        assert len(result) == 2
        assert result[0] == ("Valid suggestion", 0.9)
        assert result[1] == ("Another valid", 0.5)  # Default score for invalid

    def test_calculate_cost_gpt4_turbo_pricing(self, llm_service):
        """
        Business Critical: Cost calculation must be accurate for billing
        """
        prompt_tokens = 1000
        completion_tokens = 500
        
        cost = llm_service._calculate_cost(prompt_tokens, completion_tokens)
        
        # GPT-4 Turbo: $0.01 per 1K prompt tokens, $0.03 per 1K completion tokens
        expected_cost = (1000 / 1000) * 0.01 + (500 / 1000) * 0.03
        assert cost == expected_cost
        assert cost == 0.025

    def test_calculate_cost_zero_tokens(self, llm_service):
        """
        Business Critical: Zero token usage should result in zero cost
        """
        cost = llm_service._calculate_cost(0, 0)
        
        assert cost == 0.0

    def test_calculate_cost_fractional_tokens(self, llm_service):
        """
        Business Critical: Fractional token costs should be calculated correctly
        """
        prompt_tokens = 500  # 0.5K tokens
        completion_tokens = 250  # 0.25K tokens
        
        cost = llm_service._calculate_cost(prompt_tokens, completion_tokens)
        
        expected_cost = (500 / 1000) * 0.01 + (250 / 1000) * 0.03
        assert cost == expected_cost
        assert cost == 0.0125
