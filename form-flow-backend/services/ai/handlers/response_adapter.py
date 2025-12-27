"""
Response Adapter

Adapts responses to user style preferences.
"""

import re
from typing import Optional


class ResponseAdapter:
    """
    Adapt responses to user preference style.
    
    Detects and adapts to user communication style:
    - Concise: Short, to-the-point responses
    - Casual: Friendly, relaxed tone
    - Formal: Professional, polished tone
    """
    
    # Patterns for detecting user style
    CONCISE_PATTERNS = [
        r'^[a-zA-Z0-9@._\-+\s]{1,30}$',  # Short answers
        r'^\d+$',  # Just numbers
    ]
    
    CASUAL_PATTERNS = [
        r'\b(hey|hi|hiya|yo|sup)\b',
        r'\b(cool|awesome|yeah|yep|nope)\b',
        r'!{2,}',  # Multiple exclamation marks
    ]
    
    FORMAL_PATTERNS = [
        r'\b(please|kindly|would you|could you)\b',
        r'\b(sir|madam|mr|mrs|ms)\b',
        r'\b(thank you|thanks)\b',
    ]
    
    @staticmethod
    def detect_style(user_input: str) -> Optional[str]:
        """
        Detect user communication style from input.
        
        Args:
            user_input: User's input text
            
        Returns:
            Style name ('concise', 'casual', 'formal') or None
        """
        user_input_lower = user_input.lower()
        
        # Check for concise style
        for pattern in ResponseAdapter.CONCISE_PATTERNS:
            if re.match(pattern, user_input.strip()):
                return 'concise'
        
        # Check for casual style
        for pattern in ResponseAdapter.CASUAL_PATTERNS:
            if re.search(pattern, user_input_lower):
                return 'casual'
        
        # Check for formal style
        for pattern in ResponseAdapter.FORMAL_PATTERNS:
            if re.search(pattern, user_input_lower):
                return 'formal'
        
        return None
    
    @staticmethod
    def adapt_response(
        message: str, 
        style: Optional[str] = None,
        session_context = None
    ) -> str:
        """
        Adapt message to user preference style.
        
        Args:
            message: Original response message
            style: User style preference
            session_context: Session context with preference tracking
            
        Returns:
            Style-adapted message
        """
        if not style and session_context:
            style = getattr(session_context, 'user_preference_style', None)
        
        if not style:
            return message
        
        if style == 'concise':
            return ResponseAdapter._make_concise(message)
        elif style == 'casual':
            return ResponseAdapter._make_casual(message)
        elif style == 'formal':
            return ResponseAdapter._make_formal(message)
        
        return message
    
    @staticmethod
    def _make_concise(message: str) -> str:
        """
        Shorten message for concise preference users.
        
        Removes filler words and unnecessary phrases.
        """
        # Remove filler phrases
        fillers = [
            r"(?:^|\.\s*)(?:Great|Okay|Alright|Perfect|Excellent)[!,.]?\s*",
            r"\s*(?:please|if you don't mind|when you're ready)\s*",
            r"\s*Let me (?:just |quickly )?",
        ]
        
        result = message
        for pattern in fillers:
            result = re.sub(pattern, ' ', result, flags=re.IGNORECASE)
        
        # Clean up extra spaces
        result = re.sub(r'\s+', ' ', result).strip()
        
        return result
    
    @staticmethod
    def _make_casual(message: str) -> str:
        """
        Add casual tone for casual preference users.
        """
        replacements = {
            r'\bPlease\b': 'Hey,',
            r'\bThank you\b': 'Thanks',
            r'\bCould you\b': 'Can you',
            r'\bI would like\b': "I'd like",
            r'\bYou have entered\b': 'Got',
        }
        
        result = message
        for pattern, replacement in replacements.items():
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        return result
    
    @staticmethod
    def _make_formal(message: str) -> str:
        """
        Add formal tone for formal preference users.
        """
        replacements = {
            r'\bHey\b': 'Hello',
            r'\bThanks\b': 'Thank you',
            r"\bCan't\b": 'Cannot',
            r"\bWon't\b": 'Will not',
            r'\bGot it\b': 'Understood',
        }
        
        result = message
        for pattern, replacement in replacements.items():
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        return result
