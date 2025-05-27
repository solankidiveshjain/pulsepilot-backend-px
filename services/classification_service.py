"""
Comment classification service for sentiment, emotion, and category analysis
"""

import os
from typing import Dict, Any
try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None
try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
except ImportError:
    ChatPromptTemplate = None
    JsonOutputParser = None
from pydantic import BaseModel, Field


class ClassificationOutput(BaseModel):
    """Output schema for comment classification"""
    sentiment: str = Field(description="Sentiment: positive, negative, or neutral")
    emotion: str = Field(description="Primary emotion: joy, anger, sadness, fear, surprise, disgust, or neutral")
    category: str = Field(description="Comment category: question, complaint, compliment, suggestion, or general")
    confidence: float = Field(description="Confidence score between 0 and 1")


class ClassificationService:
    """Service for classifying comments"""
    
    def __init__(self):
        if ChatOpenAI is None or ChatPromptTemplate is None or JsonOutputParser is None:
            raise RuntimeError("Required langchain packages are not installed")
        self.llm = ChatOpenAI(
            model="gpt-4-turbo-preview",
            temperature=0.1,  # Low temperature for consistent classification
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        self.prompt_template = ChatPromptTemplate.from_template(
            """Analyze the following social media comment and classify it across three dimensions:

1. Sentiment: positive, negative, or neutral
2. Emotion: joy, anger, sadness, fear, surprise, disgust, or neutral
3. Category: question, complaint, compliment, suggestion, or general

Comment: "{comment_text}"
Platform: {platform}

Provide your analysis as JSON with the following structure:
{{
    "sentiment": "positive|negative|neutral",
    "emotion": "joy|anger|sadness|fear|surprise|disgust|neutral",
    "category": "question|complaint|compliment|suggestion|general",
    "confidence": 0.95
}}

Consider the context and nuances of social media communication. Be precise and consistent in your classifications."""
        )
        
        self.output_parser = JsonOutputParser(pydantic_object=ClassificationOutput)
    
    async def classify_comment(self, comment_text: str, platform: str) -> Dict[str, Any]:
        """Classify a comment's sentiment, emotion, and category"""
        
        if not comment_text or not comment_text.strip():
            return {
                "sentiment": "neutral",
                "emotion": "neutral",
                "category": "general",
                "confidence": 0.0
            }
        
        try:
            chain = self.prompt_template | self.llm | self.output_parser
            
            result = await chain.ainvoke({
                "comment_text": comment_text.strip(),
                "platform": platform
            })
            
            return {
                "sentiment": result.get("sentiment", "neutral"),
                "emotion": result.get("emotion", "neutral"),
                "category": result.get("category", "general"),
                "confidence": result.get("confidence", 0.5)
            }
            
        except Exception as e:
            # Return default classification on error
            return {
                "sentiment": "neutral",
                "emotion": "neutral",
                "category": "general",
                "confidence": 0.0,
                "error": str(e)
            }
