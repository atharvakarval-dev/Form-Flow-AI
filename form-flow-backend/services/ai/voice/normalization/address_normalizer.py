"""
Address Normalizer

Normalize spoken addresses.
"""

import re
from typing import Dict, Any, Optional, Tuple

from services.ai.voice.normalization.base_normalizer import BaseNormalizer
from services.ai.voice.normalization.number_normalizer import NumberNormalizer


class AddressNormalizer(BaseNormalizer):
    """Normalize spoken addresses."""
    
    STREET_TYPES = {
        'street': 'St',
        'avenue': 'Ave',
        'road': 'Rd',
        'drive': 'Dr',
        'lane': 'Ln',
        'boulevard': 'Blvd',
        'court': 'Ct',
        'circle': 'Cir',
        'place': 'Pl',
        'square': 'Sq',
        'highway': 'Hwy',
        'way': 'Way',
    }
    
    DIRECTIONS = {
        'north': 'N',
        'south': 'S',
        'east': 'E',
        'west': 'W',
        'northeast': 'NE',
        'northwest': 'NW',
        'southeast': 'SE',
        'southwest': 'SW',
    }
    
    def __init__(self):
        super().__init__()
        self.number_normalizer = NumberNormalizer()
    
    def normalize(self, text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Normalize address string.
        
        Args:
            text: Spoken address
            context: Context
            
        Returns:
            Formatted address
        """
        if not text:
            return ""
        
        # 1. Convert street numbers handling "one two three" -> "123"
        # We assume standard NumberNormalizer handles specific digit sequences if configured,
        # but for addresses, "one two three" often means "123".
        # Let's simple apply number normalizer.
        result = self.number_normalizer.convert_words_to_digits(text)
        
        # Merge consecutive single digits (e.g. "1 2 3" -> "123")
        # useful for "one two three main street"
        result = re.sub(r'(?<=\d)\s+(?=\d)', '', result)
        
        # 2. Capitalize Words
        words = result.split()
        result_words = []
        
        for word in words:
            word_lower = word.lower()
            
            # 3. Standardize directions
            if word_lower in self.DIRECTIONS:
                result_words.append(self.DIRECTIONS[word_lower])
                continue
                
            # 4. Standardize street types
            # Remove punctuation
            clean_word = word_lower.rstrip('.')
            if clean_word in self.STREET_TYPES:
                result_words.append(self.STREET_TYPES[clean_word])
                continue
            
            # Default capitalization
            result_words.append(word.capitalize())
        
        return " ".join(result_words)
    
    def validate(self, text: str) -> Tuple[bool, float]:
        """Validate normalized address."""
        if not text or len(text) < 5:
            return False, 0.0
        
        # Check if it has a number (often required for address)
        has_digit = any(char.isdigit() for char in text)
        
        # Should be reasonable length and have digit
        if has_digit and len(text.split()) >= 2:
            return True, 0.95
        
        return True, 0.6  # Maybe just street name? Valid but lower confidence.
