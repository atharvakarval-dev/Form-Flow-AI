"""
Phone Normalizer

Phone number voice input normalization with international support.
"""

import re
from typing import Dict, Any, Optional, Tuple

from services.ai.voice.normalization.base_normalizer import BaseNormalizer
from services.ai.voice.config import NUMBER_WORDS, COMPOUND_NUMBERS


class PhoneNormalizer(BaseNormalizer):
    """
    Normalize phone numbers from voice input.
    
    Handles:
    - Number words: "five five five" → "555"
    - Compound numbers: "twenty three" → "23"
    - International formats: +1, +44, +91
    - Various input formats
    """
    
    # Prefixes to strip
    PREFIXES = [
        r"^(?:my\s+)?(?:phone|mobile|cell|contact|number)\s+(?:number\s+)?(?:is\s+)?",
        r"^(?:it'?s?\s+)?",
        r"^(?:call\s+me\s+(?:at|on)\s+)?",
        r"^(?:you\s+can\s+reach\s+me\s+(?:at|on)\s+)?",
    ]
    
    def normalize(
        self, 
        text: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Normalize phone number from voice input.
        
        Args:
            text: Raw voice input
            context: Optional context (may contain country hint)
            
        Returns:
            Normalized phone number
        """
        if not text:
            return ""
        
        result = text.lower().strip()
        
        # Strip conversational prefixes
        result = self.strip_conversational_prefix(result, self.PREFIXES)
        
        # Handle compound numbers first (twenty three → 23)
        result = self._convert_compound_numbers(result)
        
        # Convert number words to digits
        result = self._convert_number_words(result)
        
        # Extract just digits and + sign
        phone = re.sub(r'[^\d+]', '', result)
        
        # Format if we have a valid phone
        if phone:
            phone = self._format_phone(phone, context)
        
        return phone if phone else result.strip()
    
    def _convert_compound_numbers(self, text: str) -> str:
        """Convert compound number words like 'twenty three' → '23'."""
        result = text
        for compound, digit in COMPOUND_NUMBERS.items():
            result = result.replace(compound, digit)
        return result
    
    def _convert_number_words(self, text: str) -> str:
        """Convert individual number words to digits."""
        words = text.split()
        result = []
        for word in words:
            if word in NUMBER_WORDS:
                result.append(NUMBER_WORDS[word])
            else:
                result.append(word)
        return ' '.join(result)
    
    def _format_phone(
        self, 
        phone: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Format phone number based on length and context.
        
        Args:
            phone: Raw digits (with optional +)
            context: Context with potential country hint
            
        Returns:
            Formatted phone number
        """
        # Check for existing country code
        if phone.startswith('+'):
            return phone
        
        # Get country hint from context
        country = None
        if context:
            country = context.get('country', '').lower()
        
        # Format based on digit count
        digits_only = phone.replace('+', '')
        
        if len(digits_only) == 10:
            # US format: (XXX) XXX-XXXX
            if country in ['us', 'usa', 'united states', '']:
                return f"({digits_only[:3]}) {digits_only[3:6]}-{digits_only[6:]}"
            
            # India context
            if country in ['india', 'in']:
                return f"+91 {digits_only}"
                
        # Handle 10 digits with India context but no country code
        if country in ['india', 'in'] and len(digits_only) == 10:
             return f"+91 {digits_only}"
        
        if len(digits_only) == 11 and digits_only.startswith('1'):
            # US with country code
            return f"+1 ({digits_only[1:4]}) {digits_only[4:7]}-{digits_only[7:]}"
        
        # Default: return as-is
        return phone
    
    def validate(self, phone: str) -> Tuple[bool, float]:
        """
        Validate phone format.
        
        Args:
            phone: Normalized phone number
            
        Returns:
            Tuple of (is_valid, confidence)
        """
        if not phone:
            return False, 0.0
        
        # Extract just digits
        digits = re.sub(r'[^\d]', '', phone)
        
        # Valid phone: 10-15 digits
        if 10 <= len(digits) <= 15:
            return True, 0.92
        
        # Too short or too long
        if len(digits) < 10:
            return False, 0.4
        
        return False, 0.3
