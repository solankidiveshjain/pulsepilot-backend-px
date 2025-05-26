"""
Modular prompt building and LLM pipeline components
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from enum import Enum

from utils.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)


class PromptTone(str, Enum):
    """Available prompt tones"""
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    CASUAL = "casual"
    FORMAL = "formal"
    EMPATHETIC = "empathetic"
    ENTHUSIASTIC = "enthusiastic"


class PromptPersona(str, Enum):
    """Available brand personas"""
    CORPORATE = "corporate"
    STARTUP = "startup"
    PERSONAL_BRAND = "personal_brand"
    NONPROFIT = "nonprofit"
    ECOMMERCE = "ecommerce"
    TECH_COMPANY = "tech_company"


class PromptContext(BaseModel):
    """Context data for prompt generation"""
    comment_text: str
    platform: str
    author: str
    tone: PromptTone = PromptTone.PROFESSIONAL
    persona: PromptPersona = PromptPersona.CORPORATE
    max_length: int = 280
    similar_examples: List[Dict[str, Any]] = []
    brand_guidelines: Optional[str] = None
    custom_instructions: Optional[str] = None


class BasePromptBuilder(ABC):
    """Abstract base class for prompt builders"""
    
    @abstractmethod
    def build_system_prompt(self, context: PromptContext) -> str:
        """Build system prompt for LLM"""
        pass
    
    @abstractmethod
    def build_user_prompt(self, context: PromptContext) -> str:
        """Build user prompt for LLM"""
        pass
    
    @abstractmethod
    def get_prompt_template(self) -> str:
        """Get prompt template string"""
        pass


class ReplyPromptBuilder(BasePromptBuilder):
    """Prompt builder for reply suggestions"""
    
    def __init__(self):
        """Initialize reply prompt builder"""
        self.tone_instructions = {
            PromptTone.PROFESSIONAL: "Maintain a professional, courteous tone",
            PromptTone.FRIENDLY: "Use a warm, approachable tone",
            PromptTone.CASUAL: "Keep it relaxed and conversational",
            PromptTone.FORMAL: "Use formal language and structure",
            PromptTone.EMPATHETIC: "Show understanding and compassion",
            PromptTone.ENTHUSIASTIC: "Express excitement and positivity"
        }
        
        self.persona_guidelines = {
            PromptPersona.CORPORATE: "Represent a large, established company",
            PromptPersona.STARTUP: "Embody innovation and agility",
            PromptPersona.PERSONAL_BRAND: "Reflect individual personality",
            PromptPersona.NONPROFIT: "Focus on mission and impact",
            PromptPersona.ECOMMERCE: "Emphasize customer service and products",
            PromptPersona.TECH_COMPANY: "Highlight technical expertise and innovation"
        }
    
    def build_system_prompt(self, context: PromptContext) -> str:
        """
        Build system prompt for reply generation
        
        Args:
            context: Prompt context data
            
        Returns:
            System prompt string
        """
        tone_instruction = self.tone_instructions.get(context.tone, "")
        persona_guideline = self.persona_guidelines.get(context.persona, "")
        
        system_prompt = f"""You are an AI assistant helping social media managers craft appropriate replies.

BRAND PERSONA: {persona_guideline}
TONE REQUIREMENTS: {tone_instruction}
PLATFORM: {context.platform}
MAX LENGTH: {context.max_length} characters

GUIDELINES:
- Generate 3 different reply suggestions
- Match the tone and context of the original comment
- Be helpful and add value to the conversation
- Avoid controversial topics
- Include call-to-action when appropriate
- Stay within character limits

{context.brand_guidelines or ""}

{context.custom_instructions or ""}

Return JSON with this structure:
{{
    "suggestions": [
        {{"text": "reply text", "score": 0.9, "tone": "{context.tone}", "reasoning": "explanation"}},
        {{"text": "reply text", "score": 0.8, "tone": "{context.tone}", "reasoning": "explanation"}},
        {{"text": "reply text", "score": 0.7, "tone": "{context.tone}", "reasoning": "explanation"}}
    ],
    "reasoning": "overall approach explanation"
}}"""
        
        return system_prompt
    
    def build_user_prompt(self, context: PromptContext) -> str:
        """
        Build user prompt for reply generation
        
        Args:
            context: Prompt context data
            
        Returns:
            User prompt string
        """
        similar_examples_text = self._format_similar_examples(context.similar_examples)
        
        user_prompt = f"""Original Comment: "{context.comment_text}"
Author: {context.author}
Platform: {context.platform}

{similar_examples_text}

Generate 3 contextually-aware reply suggestions following the guidelines above."""
        
        return user_prompt
    
    def get_prompt_template(self) -> str:
        """Get prompt template for testing"""
        return "Reply generation template for {platform} with {tone} tone"
    
    def _format_similar_examples(self, examples: List[Dict[str, Any]]) -> str:
        """
        Format similar examples for context
        
        Args:
            examples: List of similar comment/reply examples
            
        Returns:
            Formatted examples string
        """
        if not examples:
            return "No similar examples available."
        
        formatted_examples = []
        for i, example in enumerate(examples[:3], 1):
            formatted_examples.append(f"""
Example {i}:
Comment: "{example.get('comment', '')}"
Reply: "{example.get('reply', '')}"
Platform: {example.get('platform', 'unknown')}
""")
        
        return "Similar successful interactions:\n" + "\n".join(formatted_examples)


class ModerationPromptBuilder(BasePromptBuilder):
    """Prompt builder for content moderation"""
    
    def build_system_prompt(self, context: PromptContext) -> str:
        """Build system prompt for moderation"""
        return """You are a content moderation AI. Analyze the comment for:
- Spam or promotional content
- Offensive or inappropriate language
- Harassment or bullying
- Misinformation or false claims

Return JSON with moderation results."""
    
    def build_user_prompt(self, context: PromptContext) -> str:
        """Build user prompt for moderation"""
        return f"""Analyze this comment for moderation:
Comment: "{context.comment_text}"
Author: {context.author}
Platform: {context.platform}

Provide moderation assessment."""
    
    def get_prompt_template(self) -> str:
        """Get moderation template"""
        return "Content moderation template for {platform}"


class PromptPipeline:
    """Modular prompt pipeline for different use cases"""
    
    def __init__(self):
        """Initialize prompt pipeline with builders"""
        self.builders = {
            "reply": ReplyPromptBuilder(),
            "moderation": ModerationPromptBuilder()
        }
    
    def get_builder(self, builder_type: str) -> BasePromptBuilder:
        """
        Get prompt builder by type
        
        Args:
            builder_type: Type of prompt builder
            
        Returns:
            Prompt builder instance
        """
        if builder_type not in self.builders:
            raise ValueError(f"Unknown builder type: {builder_type}")
        
        return self.builders[builder_type]
    
    def build_prompts(
        self,
        builder_type: str,
        context: PromptContext
    ) -> Dict[str, str]:
        """
        Build system and user prompts
        
        Args:
            builder_type: Type of prompt builder
            context: Prompt context data
            
        Returns:
            Dictionary with system and user prompts
        """
        builder = self.get_builder(builder_type)
        
        return {
            "system": builder.build_system_prompt(context),
            "user": builder.build_user_prompt(context),
            "template": builder.get_prompt_template()
        }
    
    def register_builder(self, name: str, builder: BasePromptBuilder) -> None:
        """
        Register custom prompt builder
        
        Args:
            name: Builder name
            builder: Builder instance
        """
        self.builders[name] = builder
        logger.info("Registered custom prompt builder", name=name)


# Global prompt pipeline
prompt_pipeline = PromptPipeline()
