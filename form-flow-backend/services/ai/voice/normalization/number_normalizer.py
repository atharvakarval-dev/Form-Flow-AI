"""
Number Normalizer

Generic number voice input normalization.
"""

import re
from typing import Dict, Any, Optional, Tuple

from services.ai.voice.normalization.base_normalizer import BaseNormalizer
from services.ai.voice.config import NUMBER_WORDS, COMPOUND_NUMBERS


class NumberNormalizer(BaseNormalizer):
    """
    Normalize numbers from voice input.
    
    Handles:
    - Number words: "twenty three" → "23"
    - Compound numbers
    - Decimals: "three point one four" → "3.14"
    - Fractions: "one half" → "0.5"
    """
    
    # Prefixes to strip
    PREFIXES = [
        r"^(?:it'?s?\s+)?",
        r"^(?:i\s+have\s+)?",
        r"^(?:my\s+\w+\s+is\s+)?",
        r"^(?:about\s+)?",
        r"^(?:around\s+)?",
        r"^(?:approximately\s+)?",
    ]
    
    # Fraction mappings
    FRACTIONS = {
        'half': '0.5',
        'quarter': '0.25',
        'third': '0.33',
        'fourth': '0.25',
    }
    
    def normalize(
        self, 
        text: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Normalize number from voice input.
        
        Args:
            text: Raw voice input
            context: Optional context
            
        Returns:
            Normalized number string
        """
        if not text:
            return ""
        
        result = text.lower().strip()
        
        # Strip conversational prefixes
        result = self.strip_conversational_prefix(result, self.PREFIXES)
        
        # Handle decimals (point/dot)
        if 'point' in result or 'dot' in result:
            result = self._handle_decimal(result)
        else:
            # Handle compound numbers
            for compound, digit in COMPOUND_NUMBERS.items():
                result = result.replace(compound, digit)
            
            # Convert number words
            result = self.convert_words_to_digits(result)
        
        # Extract the first number found
        match = re.search(r'\d+(?:\.\d+)?', result)
        if match:
            return match.group()
        
        return result.strip()
    
    def _handle_decimal(self, text: str) -> str:
        """Handle decimal numbers like 'three point one four'."""
        # Split on point/dot
        parts = re.split(r'\s+(?:point|dot)\s+', text)
        
        if len(parts) == 2:
            # Convert each part
            whole = self.convert_words_to_digits(parts[0])
            decimal = self.convert_words_to_digits(parts[1])
            
            # Extract digits
            whole_num = re.search(r'\d+', whole)
            decimal_num = re.search(r'\d+', decimal)
            
            if whole_num and decimal_num:
                return f"{whole_num.group()}.{decimal_num.group()}"
        
        return text
    
    def convert_words_to_digits(self, text: str) -> str:
        """Convert number words to digits (preserves other text)."""
        words = text.split()
        result = []
        
        for word in words:
            if word in NUMBER_WORDS:
                result.append(NUMBER_WORDS[word])
            elif word in self.FRACTIONS:
                result.append(self.FRACTIONS[word])
            elif word.isdigit():
                result.append(word)
            else:
                result.append(word)
        
        return ' '.join(result)
    
    def validate(self, number: str) -> Tuple[bool, float]:
        """
        Validate number format.
        
        Args:
            number: Normalized number
            
        Returns:
            Tuple of (is_valid, confidence)
        """
        if not number:
            return False, 0.0
        
        try:
            float(number)
            return True, 0.95
        except ValueError:
            return False, 0.3
