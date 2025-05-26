"""
LLM service for generating reply suggestions using LangChain
"""

import os
from typing import List, Dict, Any
from uuid import UUID
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.callbacks import BaseCallbackHandler
from pydantic import BaseModel, Field

from models.database import Comment


class TokenCounterCallback(BaseCallbackHandler):
    """Callback to track token usage"""
    
    def __init__(self):
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
    
    def on_llm_end(self, response, **kwargs):
        if hasattr(response, 'llm_output') and response.llm_output:
            token_usage = response.llm_output.get('token_usage', {})
            self.total_tokens += token_usage.get('total_tokens', 0)
            self.prompt_tokens += token_usage.get('prompt_tokens', 0)
            self.completion_tokens += token_usage.get('completion_tokens', 0)


class SuggestionOutput(BaseModel):
    """Output schema for reply suggestions"""
    suggestions: List[Dict[str, Any]] = Field(description="List of reply suggestions with text and score")
    reasoning: str = Field(description="Explanation of the suggestions")


class LLMService:
    """Service for LLM-powered reply generation"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4-turbo-preview",
            temperature=0.7,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Create prompt template
        self.prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(
                """You are an AI assistant helping social media managers craft appropriate replies to comments.
                
                Your task is to generate 3 different reply suggestions for the given comment, considering:
                1. The tone and context of the original comment
                2. The brand's persona and voice
                3. Similar successful replies from the past
                4. Platform-specific best practices
                
                Guidelines:
                - Keep replies concise and engaging
                - Match the tone of the original comment (professional, casual, etc.)
                - Be helpful and add value
                - Avoid controversial topics
                - Include a call-to-action when appropriate
                
                Return your response as JSON with this structure:
                {{
                    "suggestions": [
                        {{"text": "reply text", "score": 0.9, "tone": "friendly"}},
                        {{"text": "reply text", "score": 0.8, "tone": "professional"}},
                        {{"text": "reply text", "score": 0.7, "tone": "casual"}}
                    ],
                    "reasoning": "Brief explanation of the approach"
                }}
                """
            ),
            HumanMessagePromptTemplate.from_template(
                """Original Comment: "{comment_text}"
                Platform: {platform}
                Author: {author}
                
                Similar successful replies from the past:
                {similar_replies}
                
                Brand persona guidelines:
                {persona_guidelines}
                
                Generate 3 reply suggestions:"""
            )
        ])
        
        self.output_parser = JsonOutputParser(pydantic_object=SuggestionOutput)
    
    async def generate_reply_suggestions(
        self,
        comment: Comment,
        similar_comments: List[Comment],
        team_id: UUID,
        persona_guidelines: str = None
    ) -> Dict[str, Any]:
        """Generate reply suggestions for a comment"""
        
        # Prepare similar replies context
        similar_replies = []
        for similar_comment in similar_comments:
            if hasattr(similar_comment, 'replies') and similar_comment.replies:
                for reply in similar_comment.replies:
                    similar_replies.append({
                        "original_comment": similar_comment.message,
                        "reply": reply.message,
                        "platform": similar_comment.platform
                    })
        
        similar_replies_text = "\n".join([
            f"Comment: {r['original_comment']}\nReply: {r['reply']}\n"
            for r in similar_replies[:5]  # Limit to 5 examples
        ]) if similar_replies else "No similar replies found."
        
        # Default persona guidelines if none provided
        if not persona_guidelines:
            persona_guidelines = "Be friendly, helpful, and professional. Maintain a positive tone."
        
        # Create token counter
        token_counter = TokenCounterCallback()
        
        # Generate suggestions
        chain = self.prompt_template | self.llm | self.output_parser
        
        try:
            result = await chain.ainvoke(
                {
                    "comment_text": comment.message,
                    "platform": comment.platform,
                    "author": comment.author or "Unknown",
                    "similar_replies": similar_replies_text,
                    "persona_guidelines": persona_guidelines
                },
                config={"callbacks": [token_counter]}
            )
            
            # Calculate cost (approximate pricing for GPT-4 Turbo)
            cost = (token_counter.prompt_tokens * 0.00001) + (token_counter.completion_tokens * 0.00003)
            
            # Format suggestions
            suggestions = []
            for suggestion in result.get("suggestions", []):
                suggestions.append((
                    suggestion.get("text", ""),
                    suggestion.get("score", 0.5)
                ))
            
            return {
                "suggestions": suggestions,
                "reasoning": result.get("reasoning", ""),
                "tokens_used": token_counter.total_tokens,
                "cost": cost
            }
            
        except Exception as e:
            raise Exception(f"LLM generation failed: {str(e)}")
