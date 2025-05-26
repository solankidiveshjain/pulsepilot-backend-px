"""
Unit tests for RAG service - critical for context-aware AI reply generation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from services.rag_service import RAGService
from models.database import Comment, Team


class TestRAGService:
    """Test RAG service for contextual reply generation"""

    @pytest.fixture
    def rag_service(self):
        with patch('services.rag_service.VectorService'), \
             patch('services.rag_service.LLMService'):
            return RAGService()

    @pytest.fixture
    def sample_comment_with_embedding(self, sample_team_id):
        comment = Comment(
            comment_id=uuid4(),
            team_id=sample_team_id,
            platform="instagram",
            author="test_user",
            message="This product is amazing!",
            embedding=[0.1, 0.2, 0.3] * 128  # 384-dim embedding
        )
        return comment

    @pytest.mark.asyncio
    async def test_generate_contextual_suggestions_with_existing_embedding(self, rag_service, sample_comment_with_embedding, sample_team_id):
        """
        Business Critical: Comments with existing embeddings should use them for similarity search
        """
        mock_similar_contexts = [
            {
                "comment_message": "Great product!",
                "reply_message": "Thank you for your feedback!",
                "similarity_score": 0.85,
                "platform": "instagram"
            }
        ]
        
        with patch.object(rag_service, '_find_similar_reply_contexts', return_value=mock_similar_contexts), \
             patch.object(rag_service, '_get_team_persona', return_value="Be friendly and professional"), \
             patch('services.rag_service.rag_prompt_composer') as mock_composer, \
             patch.object(rag_service.llm_service, 'generate_reply_suggestions_with_standardized_rag') as mock_llm:
            
            mock_llm.return_value = {
                "suggestions": [("Thank you!", 0.9)],
                "reasoning": "Generated friendly response"
            }
            
            result = await rag_service.generate_contextual_suggestions(
                comment=sample_comment_with_embedding,
                team_id=sample_team_id,
                limit_similar=5
            )
            
            # Should not generate new embedding
            rag_service.vector_service.generate_embedding.assert_not_called()
            
            # Should find similar contexts
            rag_service._find_similar_reply_contexts.assert_called_once_with(
                sample_comment_with_embedding.embedding,
                sample_team_id,
                5
            )
            
            assert "suggestions" in result

    @pytest.mark.asyncio
    async def test_generate_contextual_suggestions_without_embedding(self, rag_service, sample_team_id):
        """
        Business Critical: Comments without embeddings should generate them first
        """
        comment = Comment(
            comment_id=uuid4(),
            team_id=sample_team_id,
            platform="instagram",
            author="test_user",
            message="This product is amazing!",
            embedding=None  # No existing embedding
        )
        
        mock_embedding = [0.1, 0.2, 0.3] * 128
        
        with patch.object(rag_service.vector_service, 'generate_embedding', return_value=mock_embedding), \
             patch.object(rag_service, '_find_similar_reply_contexts', return_value=[]), \
             patch.object(rag_service, '_get_team_persona', return_value="Be professional"), \
             patch.object(rag_service.llm_service, 'generate_reply_suggestions_with_standardized_rag') as mock_llm:
            
            mock_llm.return_value = {"suggestions": [("Thank you!", 0.9)]}
            
            result = await rag_service.generate_contextual_suggestions(
                comment=comment,
                team_id=sample_team_id
            )
            
            # Should generate embedding
            rag_service.vector_service.generate_embedding.assert_called_once_with("This product is amazing!")
            
            # Comment should have embedding set
            assert comment.embedding == mock_embedding

    @pytest.mark.asyncio
    async def test_find_similar_reply_contexts_returns_relevant_data(self, rag_service, sample_team_id):
        """
        Business Critical: Similar context search must return properly formatted data for RAG
        """
        query_embedding = [0.1, 0.2, 0.3] * 128
        
        with patch('services.rag_service.get_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db
            
            # Mock database results
            mock_row1 = MagicMock()
            mock_row1.comment_id = uuid4()
            mock_row1.comment_message = "Great product!"
            mock_row1.platform = "instagram"
            mock_row1.author = "user1"
            mock_row1.reply_message = "Thank you for your feedback!"
            mock_row1.replier_name = "support_agent"
            mock_row1.similarity_distance = 0.15  # High similarity
            mock_row1.metadata = {"external_id": "comment_123"}
            
            mock_result = MagicMock()
            mock_result.fetchall.return_value = [mock_row1]
            mock_db.execute.return_value = mock_result
            
            contexts = await rag_service._find_similar_reply_contexts(
                query_embedding=query_embedding,
                team_id=sample_team_id,
                limit=5
            )
            
            assert len(contexts) == 1
            assert contexts[0]["comment_message"] == "Great product!"
            assert contexts[0]["reply_message"] == "Thank you for your feedback!"
            assert contexts[0]["similarity_score"] == 0.85  # 1 - 0.15
            assert contexts[0]["platform"] == "instagram"

    @pytest.mark.asyncio
    async def test_find_similar_reply_contexts_filters_by_similarity(self, rag_service, sample_team_id):
        """
        Business Critical: Only sufficiently similar contexts should be returned for quality RAG
        """
        query_embedding = [0.1, 0.2, 0.3] * 128
        
        with patch('services.rag_service.get_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db
            
            # Mock SQL query execution
            mock_result = MagicMock()
            mock_result.fetchall.return_value = []  # No similar results
            mock_db.execute.return_value = mock_result
            
            contexts = await rag_service._find_similar_reply_contexts(
                query_embedding=query_embedding,
                team_id=sample_team_id,
                limit=5
            )
            
            # Should call database with similarity threshold
            mock_db.execute.assert_called_once()
            call_args = mock_db.execute.call_args
            sql_query = call_args[0][0].text
            
            # Should filter by similarity distance < 0.3
            assert "< 0.3" in sql_query
            assert len(contexts) == 0

    @pytest.mark.asyncio
    async def test_get_team_persona_with_custom_persona(self, rag_service, sample_team_id):
        """
        Business Critical: Custom team personas must be used for brand-consistent replies
        """
        with patch('services.rag_service.get_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db
            
            # Mock team with custom persona
            mock_team = MagicMock()
            mock_team.metadata = {
                "persona": {
                    "voice": "Casual and fun",
                    "tone": "Enthusiastic",
                    "guidelines": "Use emojis and be energetic",
                    "avoid": "Being too formal"
                }
            }
            
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_team
            mock_db.execute.return_value = mock_result
            
            persona = await rag_service._get_team_persona(sample_team_id)
            
            assert "Casual and fun" in persona
            assert "Enthusiastic" in persona
            assert "Use emojis and be energetic" in persona
            assert "Being too formal" in persona

    @pytest.mark.asyncio
    async def test_get_team_persona_default_fallback(self, rag_service, sample_team_id):
        """
        Business Critical: Default persona must be used when team has no custom persona
        """
        with patch('services.rag_service.get_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db
            
            # Mock team without persona or no team found
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result
            
            persona = await rag_service._get_team_persona(sample_team_id)
            
            # Should return default persona
            assert "Professional and friendly" in persona
            assert "Helpful and engaging" in persona
            assert "Be responsive" in persona

    @pytest.mark.asyncio
    async def test_get_team_persona_team_without_persona_metadata(self, rag_service, sample_team_id):
        """
        Business Critical: Teams without persona metadata should get default persona
        """
        with patch('services.rag_service.get_session') as mock_get_session:
            mock_db = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_db
            
            # Mock team without persona metadata
            mock_team = MagicMock()
            mock_team.metadata = {}  # No persona key
            
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_team
            mock_db.execute.return_value = mock_result
            
            persona = await rag_service._get_team_persona(sample_team_id)
            
            # Should return default persona
            assert "Professional and friendly" in persona
            assert "Helpful and engaging" in persona
