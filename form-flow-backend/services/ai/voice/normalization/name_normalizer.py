"""
Name Normalizer

Name voice input normalization with proper capitalization.
"""

import re
from typing import Dict, Any, Optional, Tuple

from services.ai.voice.normalization.base_normalizer import BaseNormalizer


class NameNormalizer(BaseNormalizer):
    """
    Normalize names from voice input.
    
    Handles:
    - Capitalization: "john smith" → "John Smith"
    - Hyphenated: "mary-jane" → "Mary-Jane"
    - Apostrophes: "o'connor" → "O'Connor"
    - Prefixes: "my name is john" → "John"
    """
    
    # Prefixes to strip
    PREFIXES = [
        r"^(?:hi\s+)?(?:my\s+)?(?:name\s+is\s+)",
        r"^(?:i'?m\s+)",
        r"^(?:this\s+is\s+)",
        r"^(?:it'?s?\s+)",
        r"^(?:call\s+me\s+)",
        r"^(?:you\s+can\s+call\s+me\s+)",
        r"^(?:hey\s+)?(?:i\s+am\s+)",
    ]
    
    # Name parts that should stay lowercase
    LOWERCASE_PARTS = {'van', 'der', 'de', 'la', 'le', 'du', 'von'}
    
    def normalize(
        self, 
        text: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Normalize name from voice input.
        
        Args:
            text: Raw voice input
            context: Optional context
            
        Returns:
            Properly capitalized name
        """
        if not text:
            return ""
        
        result = text.strip()
        
        # Strip conversational prefixes
        result = self.strip_conversational_prefix(result, self.PREFIXES)
        
        # Handle empty after prefix strip
        if not result:
            return ""
        
        # Smart capitalization
        result = self._smart_capitalize(result)
        
        return result
    
    def _smart_capitalize(self, text: str) -> str:
        """
        Smart capitalization handling various name formats.
        
        Handles:
        - Regular: "john smith" → "John Smith"
        - Hyphenated: "mary-jane" → "Mary-Jane"
        - Apostrophes: "o'connor" → "O'Connor"
        - Compound: "mcdonald" → "McDonald"
        """
        words = text.split()
        result_words = []
        
        for i, word in enumerate(words):
            capitalized = self._capitalize_word(word, is_first=(i == 0))
            result_words.append(capitalized)
        
        return ' '.join(result_words)
    
    def _capitalize_word(self, word: str, is_first: bool = False) -> str:
        """
        Capitalize a single word properly.
        
        Args:
            word: Word to capitalize
            is_first: Whether this is the first word in name
            
        Returns:
            Properly capitalized word
        """
        word_lower = word.lower()
        
        # Handle prefixes (van, de, etc.) - usually lowercase unless first
        if word_lower in self.LOWERCASE_PARTS and not is_first:
            return word_lower
        
        # Handle hyphenated names
        if '-' in word:
            parts = word.split('-')
            return '-'.join(p.capitalize() for p in parts)
        
        # Handle apostrophes (O'Connor, McDonald's)
        if "'" in word:
            parts = word.split("'")
            return "'".join(p.capitalize() for p in parts)
        
        # Handle Mc/Mac patterns
        if word_lower.startswith('mc') and len(word_lower) > 2:
            return 'Mc' + word_lower[2:].capitalize()
        if word_lower.startswith('mac') and len(word_lower) > 3:
            return 'Mac' + word_lower[3:].capitalize()
        
        # Standard capitalize
        return word.capitalize()
    
    def validate(self, name: str) -> Tuple[bool, float]:
        """
        Validate name format.
        
        Args:
            name: Normalized name
            
        Returns:
            Tuple of (is_valid, confidence)
        """
        if not name:
            return False, 0.0
        
        words = name.split()
        
        # Full name: 2-4 words
        if 2 <= len(words) <= 4:
            # All words should be mostly alphabetic
            if all(self._is_name_word(w) for w in words):
                return True, 0.90
            return True, 0.75
        
        # Single name (first or last only)
        if len(words) == 1:
            if self._is_name_word(words[0]) and len(words[0]) >= 2:
                return True, 0.80
            return False, 0.5
        
        # Too many words
        return False, 0.4
    
    def _is_name_word(self, word: str) -> bool:
        """Check if word looks like a name part."""
        # Remove hyphens and apostrophes for checking
        cleaned = word.replace('-', '').replace("'", '')
        return cleaned.isalpha() and len(cleaned) >= 1
