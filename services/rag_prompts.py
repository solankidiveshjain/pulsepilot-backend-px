"""
Standardized RAG prompt templates with unit testing support
"""

from typing import List, Dict, Any
from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate


class RAGContext(BaseModel):
    """Structured RAG context for prompt composition"""
    similar_comments: List[Dict[str, Any]]
    persona_guidelines: str
    platform: str
    comment_text: str
    author: str
    max_length: int = 280


class RAGPromptComposer:
    """Standardized RAG prompt composition with testing support"""
    
    def __init__(self):
        self.system_template = SystemMessagePromptTemplate.from_template(
            """You are an AI assistant helping social media managers craft appropriate replies to comments using context from similar successful interactions.

Your task is to generate {num_suggestions} different reply suggestions for the given comment, considering:
1. The tone and context of the original comment
2. The brand's persona and voice guidelines
3. Similar successful replies from the past (RAG context)
4. Platform-specific best practices

Brand Persona & Guidelines:
{persona_guidelines}

Similar Successful Interactions (for context):
{context_examples}

Platform Constraints:
- Platform: {platform}
- Maximum length: {max_length} characters
- Tone should match the original comment appropriately

Guidelines:
- Keep replies concise and engaging
- Be helpful and add value
- Avoid controversial topics
- Include a call-to-action when appropriate
- Learn from the successful reply patterns shown above

Return your response as JSON with this structure:
{{
    "suggestions": [
        {{"text": "reply text", "score": 0.9, "tone": "friendly", "reasoning": "why this works"}},
        {{"text": "reply text", "score": 0.8, "tone": "professional", "reasoning": "why this works"}},
        {{"text": "reply text", "score": 0.7, "tone": "casual", "reasoning": "why this works"}}
    ],
    "context_used": "how similar examples influenced suggestions",
    "reasoning": "overall approach explanation"
}}"""
        )
        
        self.human_template = HumanMessagePromptTemplate.from_template(
            """Original Comment: "{comment_text}"
Platform: {platform}
Author: {author}

Generate {num_suggestions} contextually-aware reply suggestions:"""
        )
        
        self.prompt_template = ChatPromptTemplate.from_messages([
            self.system_template,
            self.human_template
        ])
    
    def compose_context_examples(self, similar_contexts: List[Dict[str, Any]]) -> str:
        """Compose context examples from similar interactions"""
        if not similar_contexts:
            return "No similar examples found."
        
        examples = []
        for i, ctx in enumerate(similar_contexts[:5], 1):  # Limit to 5 examples
            example = f"""
Example {i} (Similarity: {ctx['similarity_score']:.2f}):
Original Comment: "{ctx['comment_message']}"
Platform: {ctx['platform']}
Successful Reply: "{ctx['reply_message']}"
Replier: {ctx['replier_name']}
"""
            examples.append(example)
        
        return "\n".join(examples)
    
    def create_prompt_variables(self, context: RAGContext, num_suggestions: int = 3) -> Dict[str, Any]:
        """Create standardized prompt variables"""
        context_examples = self.compose_context_examples(context.similar_comments)
        
        return {
            "comment_text": context.comment_text,
            "platform": context.platform,
            "author": context.author,
            "persona_guidelines": context.persona_guidelines,
            "context_examples": context_examples,
            "num_suggestions": num_suggestions,
            "max_length": context.max_length
        }
    
    def get_prompt_template(self) -> ChatPromptTemplate:
        """Get the standardized prompt template"""
        return self.prompt_template
    
    def validate_prompt_variables(self, variables: Dict[str, Any]) -> bool:
        """Validate that all required prompt variables are present"""
        required_vars = [
            "comment_text", "platform", "author", "persona_guidelines",
            "context_examples", "num_suggestions", "max_length"
        ]
        
        missing_vars = [var for var in required_vars if var not in variables]
        if missing_vars:
            raise ValueError(f"Missing required prompt variables: {missing_vars}")
        
        return True


# Global prompt composer instance
rag_prompt_composer = RAGPromptComposer()
