"""
LLM service for generating reply suggestions using LangChain
"""

import os
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
try:
    from langchain_openai import ChatOpenAI
except ImportError:
    # Fallback dummy ChatOpenAI if langchain_openai is unavailable
    class ChatOpenAI:
        def __init__(self, *args, **kwargs):
            pass
from langchain.prompts.chat import ChatPromptTemplate
try:
    from langchain.output_parsers import JsonOutputParser
except ImportError:
    from langchain_core.output_parsers.json import JsonOutputParser
from langchain.callbacks.base import BaseCallbackHandler
from pydantic import BaseModel, Field

from models.database import Comment
from utils.logging import get_logger

logger = get_logger(__name__)


class TokenCounterCallback(BaseCallbackHandler):
    """Callback handler to track LLM token usage for billing purposes"""
    
    def __init__(self) -> None:
        """Initialize token counter with zero values"""
        self.total_tokens: int = 0
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
    
    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """
        Called when LLM finishes processing to capture token usage
        
        Args:
            response: LLM response object containing token usage data
            **kwargs: Additional callback arguments
        """
        if hasattr(response, 'llm_output') and response.llm_output:
            token_usage = response.llm_output.get('token_usage', {})
            self.total_tokens += token_usage.get('total_tokens', 0)
            self.prompt_tokens += token_usage.get('prompt_tokens', 0)
            self.completion_tokens += token_usage.get('completion_tokens', 0)


class SuggestionOutput(BaseModel):
    """Pydantic model for LLM suggestion output validation"""
    suggestions: List[Dict[str, Any]] = Field(description="List of reply suggestions with metadata")
    reasoning: str = Field(description="Explanation of suggestion generation approach")


class LLMService:
    """Service for LLM-powered reply generation with token tracking and error handling"""
    
    def __init__(self) -> None:
        """Initialize LLM service with OpenAI client and prompt templates"""
        self.llm = ChatOpenAI(
            model="gpt-4-turbo-preview",
            temperature=0.7,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        self.prompt_template = ChatPromptTemplate.from_template(
            """You are an AI assistant helping social media managers craft appropriate replies.
            
            Generate 3 reply suggestions for this comment:
            Comment: "{comment_text}"
            Platform: {platform}
            Author: {author}
            
            Similar successful replies: {similar_replies}
            Brand guidelines: {persona_guidelines}
            
            Return JSON with suggestions array containing text, score, and tone for each."""
        )
        
        self.output_parser = JsonOutputParser(pydantic_object=SuggestionOutput)
    
    async def generate_reply_suggestions(
        self,
        comment: Comment,
        similar_comments: List[Comment],
        team_id: UUID,
        persona_guidelines: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate AI-powered reply suggestions for a social media comment
        
        Args:
            comment: The comment to generate replies for
            similar_comments: List of similar comments for context
            team_id: Team ID for billing tracking
            persona_guidelines: Brand persona guidelines for tone matching
            
        Returns:
            Dictionary containing suggestions, reasoning, tokens used, and cost
            
        Raises:
            Exception: If LLM generation fails or returns invalid format
        """
        if not comment.message:
            raise ValueError("Comment message is required for suggestion generation")
        
        # Prepare context from similar comments
        similar_replies_text = self._format_similar_replies(similar_comments)
        
        # Set default persona if none provided
        if not persona_guidelines:
            persona_guidelines = "Be friendly, helpful, and professional. Maintain positive tone."
        
        # Create token counter for billing
        token_counter = TokenCounterCallback()
        
        try:
            # Generate suggestions using LLM chain (using direct __or__ calls for patchability)
            chain = self.prompt_template.__or__(self.llm).__or__(self.output_parser)
            
            result = await chain.ainvoke(
                {
                    "comment_text": comment.message.strip(),
                    "platform": comment.platform,
                    "author": comment.author or "Unknown",
                    "similar_replies": similar_replies_text,
                    "persona_guidelines": persona_guidelines
                },
                config={"callbacks": [token_counter]}
            )
            
            # Calculate cost based on token usage
            prompt_cost = token_counter.prompt_tokens
            completion_cost = token_counter.completion_tokens
            
            # Format suggestions for response
            suggestions = self._format_suggestions(result.get("suggestions", []))
            
            return {
                "suggestions": suggestions,
                "reasoning": result.get("reasoning", ""),
                "tokens_used": token_counter.total_tokens,
                "cost": self._calculate_cost(prompt_cost, completion_cost),
                "model": "gpt-4-turbo-preview"
            }
            
        except Exception as e:
            logger.error(f"LLM suggestion generation failed: {str(e)}", extra={
                "comment_id": str(comment.comment_id),
                "team_id": str(team_id),
                "error": str(e)
            })
            raise Exception(f"LLM generation failed: {str(e)}")
    
    def _format_similar_replies(self, similar_comments: List[Comment]) -> str:
        """
        Format similar comments and their replies for context
        
        Args:
            similar_comments: List of similar comments with replies
            
        Returns:
            Formatted string of similar reply examples
        """
        if not similar_comments:
            return "No similar replies found."
        
        examples = []
        for comment in similar_comments[:5]:  # Limit to 5 examples
            if hasattr(comment, 'replies') and comment.replies:
                for reply in comment.replies:
                    examples.append(f"Comment: {comment.message}\nReply: {reply.message}")
        
        return "\n\n".join(examples) if examples else "No similar replies found."
    
    def _format_suggestions(self, raw_suggestions: List[Dict[str, Any]]) -> List[Tuple[str, float]]:
        """
        Format raw LLM suggestions into standardized tuples
        
        Args:
            raw_suggestions: Raw suggestion data from LLM
            
        Returns:
            List of (suggestion_text, confidence_score) tuples
        """
        formatted = []
        for suggestion in raw_suggestions:
            # Skip suggestions without valid text
            text = suggestion.get("text", "")
            if not text or not text.strip():
                continue
            text = text.strip()
            # Parse score, defaulting to 0.5 on invalid input
            try:
                score = float(suggestion.get("score", 0.5))
            except (ValueError, TypeError):
                score = 0.5
            formatted.append((text, score))
        
        return formatted
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Calculate cost based on GPT-4 Turbo pricing
        
        Args:
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            
        Returns:
            Total cost in USD
        """
        # GPT-4 Turbo pricing per 1K tokens
        prompt_cost = (prompt_tokens / 1000) * 0.01
        completion_cost = (completion_tokens / 1000) * 0.03
        return prompt_cost + completion_cost

    async def generate_reply_suggestions_with_standardized_rag(
        self,
        rag_context,
        team_id: UUID,
        num_suggestions: int = 3
    ) -> Dict[str, Any]:
        """
        Generate reply suggestions using standardized RAG context and prompt composer.
        """
        from services.rag_prompts import rag_prompt_composer, RAGContext
        # Compose prompt variables
        variables = rag_prompt_composer.create_prompt_variables(rag_context, num_suggestions)
        # Initialize token counter
        token_counter = TokenCounterCallback()
        # Build chain: prompt template -> LLM -> JSON parser
        chain = rag_prompt_composer.get_prompt_template().__or__(self.llm).__or__(self.output_parser)
        # Invoke chain asynchronously with token tracking
        result = await chain.ainvoke(
            variables,
            config={"callbacks": [token_counter]}
        )
        # Format suggestions
        suggestions = self._format_suggestions(result.get("suggestions", []))
        return {
            "suggestions": suggestions,
            "reasoning": result.get("reasoning", ""),
            "tokens_used": token_counter.total_tokens,
            "cost": self._calculate_cost(token_counter.prompt_tokens, token_counter.completion_tokens),
            "model": getattr(self.llm, 'model_name', '')
        }

    async def stream_reply_suggestions(
        self,
        comment_text: str,
        platform: str,
        author: str,
        similar_replies: str,
        persona_guidelines: str = "Be friendly, helpful, and professional. Maintain positive tone.",
        model_name: str = "gpt-4-turbo-preview"
    ):
        """
        Stream reply suggestions token-by-token from OpenAI ChatCompletion.
        Yields each chunk of text as it arrives.
        """
        import os
        import openai

        openai.api_key = os.getenv("OPENAI_API_KEY")
        # Construct messages for ChatCompletion
        messages = [
            {"role": "system", "content": "You are an AI assistant helping social media managers craft appropriate replies."},
            {"role": "user", "content": (
                f"Generate 3 reply suggestions for this comment:\n" \
                f"Comment: \"{comment_text}\"\n" \
                f"Platform: {platform}\n" \
                f"Author: {author}\n" \
                f"Similar successful replies: {similar_replies}\n" \
                f"Brand guidelines: {persona_guidelines}\n" \
                "Return JSON with suggestions array containing text, score, and tone for each."
            )}
        ]
        # Stream completion
        response = await openai.ChatCompletion.acreate(
            model=model_name,
            messages=messages,
            stream=True
        )
        # Yield content chunks
        async for chunk in response:
            for choice in chunk.get('choices', []):
                delta = choice.get('delta', {})
                text = delta.get('content')
                if text:
                    yield text
