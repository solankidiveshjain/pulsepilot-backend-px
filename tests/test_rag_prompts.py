"""
Unit tests for RAG prompt composition
"""

import pytest
from services.rag_prompts import RAGPromptComposer, RAGContext


class TestRAGPromptComposer:
    """Test RAG prompt composition functionality"""
    
    def setup_method(self):
        self.composer = RAGPromptComposer()
        self.sample_context = RAGContext(
            similar_comments=[
                {
                    "comment_message": "Love this product!",
                    "reply_message": "Thank you so much! We're thrilled you love it!",
                    "platform": "instagram",
                    "replier_name": "Sarah",
                    "similarity_score": 0.85
                }
            ],
            persona_guidelines="Be friendly and professional",
            platform="instagram",
            comment_text="This is amazing!",
            author="user123",
            max_length=280
        )
    
    def test_compose_context_examples_with_data(self):
        """Test context example composition with data"""
        examples = self.composer.compose_context_examples(self.sample_context.similar_comments)
        
        assert "Example 1" in examples
        assert "Love this product!" in examples
        assert "Thank you so much!" in examples
        assert "Similarity: 0.85" in examples
    
    def test_compose_context_examples_empty(self):
        """Test context example composition with no data"""
        examples = self.composer.compose_context_examples([])
        assert examples == "No similar examples found."
    
    def test_create_prompt_variables(self):
        """Test prompt variable creation"""
        variables = self.composer.create_prompt_variables(self.sample_context)
        
        required_keys = [
            "comment_text", "platform", "author", "persona_guidelines",
            "context_examples", "num_suggestions", "max_length"
        ]
        
        for key in required_keys:
            assert key in variables
        
        assert variables["comment_text"] == "This is amazing!"
        assert variables["platform"] == "instagram"
        assert variables["num_suggestions"] == 3
    
    def test_validate_prompt_variables_success(self):
        """Test successful prompt variable validation"""
        variables = self.composer.create_prompt_variables(self.sample_context)
        assert self.composer.validate_prompt_variables(variables) is True
    
    def test_validate_prompt_variables_missing(self):
        """Test prompt variable validation with missing variables"""
        incomplete_variables = {"comment_text": "test"}
        
        with pytest.raises(ValueError) as exc_info:
            self.composer.validate_prompt_variables(incomplete_variables)
        
        assert "Missing required prompt variables" in str(exc_info.value)
    
    def test_get_prompt_template(self):
        """Test prompt template retrieval"""
        template = self.composer.get_prompt_template()
        assert template is not None
        assert len(template.messages) == 2  # System + Human messages
