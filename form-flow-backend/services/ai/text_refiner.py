"""
Text Refiner Service

AI-powered text refinement that transforms raw, rambling voice transcripts
into clean, perfectly formatted text.

Features:
- Removes filler words (um, uh, like, you know)
- Fixes grammar and punctuation
- Restructures rambled sentences into clear prose
- Maintains original meaning and intent
- Supports multiple output styles
"""

import os
import re
import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain.schema import HumanMessage, SystemMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

logger = logging.getLogger(__name__)


class RefineStyle(str, Enum):
    """Output formatting styles for refined text"""
    DEFAULT = "default"  # Clean prose
    CONCISE = "concise"  # Shortest possible
    FORMAL = "formal"    # Professional/business
    CASUAL = "casual"    # Friendly/conversational
    BULLET = "bullet"    # Bullet point list
    PARAGRAPH = "paragraph"  # Well-structured paragraphs


@dataclass
class RefinedText:
    """Result of text refinement"""
    original: str
    refined: str
    style: RefineStyle
    question: str = ""  # The question context that was provided
    changes_made: List[str] = field(default_factory=list)
    confidence: float = 1.0
    word_count_original: int = 0
    word_count_refined: int = 0
    
    @property
    def reduction_percent(self) -> float:
        """How much the text was shortened"""
        if self.word_count_original == 0:
            return 0.0
        return round((1 - self.word_count_refined / self.word_count_original) * 100, 1)


class TextRefiner:
    """
    AI-powered text refinement service.
    
    Transforms raw voice transcripts into clean, polished text using
    Google Gemini for intelligent text processing.
    """
    
    # Common filler words to remove
    FILLER_WORDS = [
        "um", "uh", "umm", "uhh", "er", "ah", "hmm",
        "like", "you know", "I mean", "basically", "literally",
        "actually", "honestly", "so yeah", "right", "okay so",
        "kind of", "sort of", "I guess", "I think like"
    ]
    
    SYSTEM_PROMPT = """You are an expert text editor specializing in refining voice transcripts into form field answers.

Your task is to transform raw, spoken answers into clean, properly formatted responses while:

1. **Remove filler words**: "um", "uh", "like", "you know", "I mean", "basically", etc.
2. **Extract the actual answer**: If the user said "my email is john dot smith at gmail dot com", extract "john.smith@gmail.com"
3. **Format appropriately**: Based on the question context, format the answer correctly:
   - Email addresses: lowercase, proper @ and . formatting
   - Phone numbers: clean digits, proper formatting
   - Names: Proper capitalization
   - Dates: Standard date format
   - Numbers: Digits not words ("five" → "5")
4. **Maintain meaning**: Keep the original intent and all important information
5. **Be concise**: For form fields, shorter is better

IMPORTANT:
- If a QUESTION is provided, understand what type of answer is expected
- Extract ONLY the relevant answer, not conversational fluff
- Output ONLY the refined answer, nothing else
- Do NOT add explanations or commentary"""

    STYLE_INSTRUCTIONS = {
        RefineStyle.DEFAULT: "Write clean, natural prose.",
        RefineStyle.CONCISE: "Be as brief as possible while keeping all key information.",
        RefineStyle.FORMAL: "Use professional, business-appropriate language.",
        RefineStyle.CASUAL: "Keep a friendly, conversational tone.",
        RefineStyle.BULLET: "Format as a bullet point list with key points.",
        RefineStyle.PARAGRAPH: "Structure into well-organized paragraphs with topic sentences.",
    }
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash-lite"):
        """
        Initialize the text refiner.
        
        Args:
            api_key: Google API key. Falls back to GOOGLE_API_KEY env var.
            model: Gemini model to use.
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model_name = model
        self.llm = None
        
        if LANGCHAIN_AVAILABLE and self.api_key:
            try:
                self.llm = ChatGoogleGenerativeAI(
                    model=model,
                    google_api_key=self.api_key,
                    temperature=0.3,  # Low temp for consistent refinement
                    max_output_tokens=2048,
                )
                logger.info(f"TextRefiner initialized with {model}")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM: {e}")
    
    async def refine(
        self, 
        raw_text: str, 
        question: str = "",
        style: RefineStyle = RefineStyle.DEFAULT,
        field_type: str = ""
    ) -> RefinedText:
        """
        Refine raw voice transcript into clean text.
        
        Args:
            raw_text: The raw transcript from speech recognition
            question: The question/prompt that was asked (provides context)
            style: Desired output formatting style
            field_type: Optional field type hint (email, phone, date, etc.)
            
        Returns:
            RefinedText with original, refined text, and metadata
        """
        if not raw_text or not raw_text.strip():
            return RefinedText(
                original=raw_text,
                refined=raw_text,
                style=style,
                confidence=1.0
            )
        
        # Count original words
        word_count_original = len(raw_text.split())
        
        # Try LLM refinement first
        if self.llm:
            try:
                refined = await self._refine_with_llm(raw_text, question, style, field_type)
                return RefinedText(
                    original=raw_text,
                    refined=refined,
                    style=style,
                    question=question,
                    changes_made=self._detect_changes(raw_text, refined),
                    confidence=0.95,
                    word_count_original=word_count_original,
                    word_count_refined=len(refined.split())
                )
            except Exception as e:
                logger.warning(f"LLM refinement failed, using fallback: {e}")
        
        # Fallback to rule-based refinement
        refined = self._refine_with_rules(raw_text, field_type)
        return RefinedText(
            original=raw_text,
            refined=refined,
            style=style,
            question=question,
            changes_made=self._detect_changes(raw_text, refined),
            confidence=0.7,  # Lower confidence for rule-based
            word_count_original=word_count_original,
            word_count_refined=len(refined.split())
        )
    
    async def _refine_with_llm(self, text: str, question: str, style: RefineStyle, field_type: str = "") -> str:
        """Use Gemini to intelligently refine the text with question context."""
        style_instruction = self.STYLE_INSTRUCTIONS.get(style, "")
        
        # Build context-aware prompt
        context_parts = []
        if question:
            context_parts.append(f"QUESTION ASKED: \"{question}\"")
        if field_type:
            context_parts.append(f"FIELD TYPE: {field_type}")
        
        context_block = "\n".join(context_parts) if context_parts else "No specific question context."
        
        prompt = f"""{context_block}

USER'S SPOKEN ANSWER:
"{text}"

Style: {style_instruction}

Extract and refine the answer. Output ONLY the cleaned answer:"""
        
        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ]
        
        response = self.llm.invoke(messages)
        refined = response.content.strip()
        
        # Remove any quotation marks the model might have added
        if refined.startswith('"') and refined.endswith('"'):
            refined = refined[1:-1]
        
        return refined
    
    def _refine_with_rules(self, text: str, field_type: str = "") -> str:
        """
        Rule-based fallback refinement.
        Removes filler words and applies type-specific formatting.
        """
        refined = text
        
        # Remove filler words (case insensitive)
        for filler in self.FILLER_WORDS:
            pattern = r'\b' + re.escape(filler) + r'\b'
            refined = re.sub(pattern, '', refined, flags=re.IGNORECASE)
        
        # Clean up extra spaces
        refined = re.sub(r'\s+', ' ', refined).strip()
        
        # Apply type-specific formatting
        if field_type.lower() in ['email', 'e-mail']:
            # Extract email pattern
            email_pattern = r'[\w\.-]+\s*(?:at|@)\s*[\w\.-]+\s*(?:dot|\.)\s*\w+'
            match = re.search(email_pattern, refined, re.IGNORECASE)
            if match:
                email = match.group()
                email = re.sub(r'\s*at\s*', '@', email, flags=re.IGNORECASE)
                email = re.sub(r'\s*dot\s*', '.', email, flags=re.IGNORECASE)
                email = email.replace(' ', '').lower()
                return email
        
        elif field_type.lower() in ['phone', 'telephone', 'mobile']:
            # Extract digits
            digits = re.sub(r'[^\d]', '', refined)
            if len(digits) >= 10:
                return digits
        
        elif field_type.lower() in ['number', 'age', 'years', 'experience']:
            # Convert word numbers to digits
            word_to_num = {
                'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
                'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
                'ten': '10', 'eleven': '11', 'twelve': '12'
            }
            for word, num in word_to_num.items():
                refined = re.sub(r'\b' + word + r'\b', num, refined, flags=re.IGNORECASE)
        
        # Fix multiple punctuation
        refined = re.sub(r'([.!?])\1+', r'\1', refined)
        
        # Capitalize first letter of sentences (only for prose)
        if field_type.lower() not in ['email', 'phone']:
            refined = re.sub(r'(^|[.!?]\s+)([a-z])', lambda m: m.group(1) + m.group(2).upper(), refined)
        
        # Ensure ends with punctuation (only for prose fields)
        if field_type.lower() not in ['email', 'phone', 'number', 'age']:
            if refined and refined[-1] not in '.!?':
                refined += '.'
        
        return refined
    
    def _detect_changes(self, original: str, refined: str) -> List[str]:
        """Detect what types of changes were made."""
        changes = []
        
        original_lower = original.lower()
        refined_lower = refined.lower()
        
        # Check for filler removal
        for filler in self.FILLER_WORDS:
            if filler.lower() in original_lower and filler.lower() not in refined_lower:
                changes.append(f"Removed filler: '{filler}'")
                break  # Only note once
        
        # Check for length reduction
        orig_words = len(original.split())
        ref_words = len(refined.split())
        if ref_words < orig_words:
            changes.append(f"Reduced from {orig_words} to {ref_words} words")
        
        # Check for punctuation fixes
        if original.count('.') < refined.count('.'):
            changes.append("Added sentence punctuation")
        
        return changes[:5]  # Limit to 5 changes
    
    def quick_clean(self, text: str) -> str:
        """
        Synchronous quick clean - just removes obvious fillers.
        Use for real-time display before full refinement.
        """
        cleaned = text
        for filler in self.FILLER_WORDS[:8]:  # Just the most common
            pattern = r'\b' + re.escape(filler) + r'\b'
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        return re.sub(r'\s+', ' ', cleaned).strip()


# Singleton instance
_refiner_instance: Optional[TextRefiner] = None


def get_text_refiner() -> TextRefiner:
    """Get or create the TextRefiner singleton."""
    global _refiner_instance
    if _refiner_instance is None:
        _refiner_instance = TextRefiner()
    return _refiner_instance
