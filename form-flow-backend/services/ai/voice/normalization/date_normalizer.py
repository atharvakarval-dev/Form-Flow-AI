"""
Date Normalizer

Normalize spoken dates to standard format (MM/DD/YYYY).
"""

import re
from typing import Dict, Any, Optional, Tuple

from services.ai.voice.normalization.base_normalizer import BaseNormalizer
from services.ai.voice.normalization.number_normalizer import NumberNormalizer


class DateNormalizer(BaseNormalizer):
    """Normalize spoken dates."""
    
    MONTHS = {
        'january': '01', 'jan': '01',
        'february': '02', 'feb': '02',
        'march': '03', 'mar': '03',
        'april': '04', 'apr': '04',
        'may': '05',
        'june': '06', 'jun': '06',
        'july': '07', 'jul': '07',
        'august': '08', 'aug': '08',
        'september': '09', 'sep': '09', 'sept': '09',
        'october': '10', 'oct': '10',
        'november': '11', 'nov': '11',
        'december': '12', 'dec': '12',
    }
    
    def __init__(self):
        super().__init__()
        self.number_normalizer = NumberNormalizer()
    
    def normalize(self, text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Normalize date string.
        
        Args:
            text: Spoken date
            context: Context
            
        Returns:
            Formatted date (MM/DD/YYYY) or original
        """
        if not text:
            return ""
        
        # 1. Convert any number words first (fifth -> 5th, one -> 1)
        # We use number normalizer but keep ordinal suffixes if possible?
        # NumberNormalizer converts "fifth" to "5". "first" to "1".
        clean_text = self.number_normalizer.convert_words_to_digits(text)
        
        clean_text = clean_text.lower()
        
        # 2. Extract components
        # Pattern: Month Day Year
        # e.g. "january 5 2024", "01 05 2024"
        
        match = re.search(r'([a-z]+|\d+)\s+(\d+)(?:st|nd|rd|th)?(?:,)?\s+(\d{4})', clean_text)
        if match:
            month_raw, day, year = match.groups()
            
            month = self._parse_month(month_raw)
            if month:
                return f"{month}/{day.zfill(2)}/{year}"
        
        return text
    
    def validate(self, text: str) -> Tuple[bool, float]:
        """Validate normalized date."""
        if not text:
            return False, 0.0
        
        # Check MM/DD/YYYY format
        if re.match(r'^\d{2}/\d{2}/\d{4}$', text):
            return True, 1.0
        
        return False, 0.5
    
    def _parse_month(self, text: str) -> Optional[str]:
        """Parse month name or number."""
        if text.isdigit():
            val = int(text)
            if 1 <= val <= 12:
                return str(val).zfill(2)
            return None
            
        return self.MONTHS.get(text)
