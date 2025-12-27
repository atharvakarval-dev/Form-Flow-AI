"""
STT Corrections

Speech-to-Text correction pattern application.
"""

import re
from typing import Dict, Optional

from services.ai.voice.config import get_all_stt_patterns, STT_PUNCTUATION


class STTCorrector:
    """
    Apply Speech-to-Text correction patterns.
    
    Converts spoken articulations to proper format:
    - "at sign" → "@"
    - "underscore" → "_"
    - "dot com" → ".com"
    """
    
    def __init__(self):
        """Initialize with all STT patterns."""
        self.patterns = get_all_stt_patterns()
        self._sorted_patterns = None
    
    @property
    def sorted_patterns(self):
        """Get patterns sorted by length (longest first)."""
        if self._sorted_patterns is None:
            self._sorted_patterns = sorted(
                self.patterns.items(),
                key=lambda x: len(x[0]),
                reverse=True
            )
        return self._sorted_patterns
    
    def apply_corrections(
        self, 
        text: str,
        field_type: Optional[str] = None
    ) -> str:
        """
        Apply all STT corrections to text.
        
        Args:
            text: Raw STT output
            field_type: Optional field type for context-aware corrections
            
        Returns:
            Corrected text
        """
        if not text:
            return ""
        
        result = text.lower()
        
        # Apply patterns sorted by length (longest first)
        for pattern, replacement in self.sorted_patterns:
            # Skip ' at ' in non-email contexts (handled separately)
            if pattern == ' at ' and field_type != 'email':
                continue
            result = result.replace(pattern, replacement)
        
        return result
    
    def add_pattern(self, spoken: str, written: str):
        """
        Add a custom STT pattern.
        
        Args:
            spoken: What user says
            written: What it should become
        """
        self.patterns[spoken.lower()] = written
        self._sorted_patterns = None  # Reset cache


class SpelledTextHandler:
    """
    Handle spelled-out text: "j o h n" → "john"
    """
    
    @staticmethod
    def is_spelled_out(text: str) -> bool:
        """
        Detect if user is spelling out letters.
        
        Args:
            text: Input text
            
        Returns:
            True if text appears to be spelled out
        """
        words = text.split()
        if len(words) < 4:
            return False
        
        single_chars = sum(1 for w in words if len(w) == 1 and w.isalpha())
        return single_chars >= len(words) * 0.6
    
    @staticmethod
    def join_spelled_letters(text: str) -> str:
        """
        Join spelled out letters intelligently.
        
        Handles:
        - "j o h n" → "john"
        - "j o h n at g m a i l" → "john@gmail"
        - "j o h n dot c o m" → "john.com"
        
        Args:
            text: Spelled out text
            
        Returns:
            Joined text
        """
        words = text.split()
        result = []
        current = []
        
        for word in words:
            word_lower = word.lower()
            
            # Check for separators
            if word_lower in ['at', '@']:
                if current:
                    result.append(''.join(current))
                    current = []
                result.append('@')
            elif word_lower in ['dot', '.']:
                if current:
                    result.append(''.join(current))
                    current = []
                result.append('.')
            elif len(word) == 1 and word.isalpha():
                # Single letter - add to current accumulator
                current.append(word_lower)
            else:
                # Multi-letter word
                if current:
                    result.append(''.join(current))
                    current = []
                result.append(word)
        
        # Don't forget remaining letters
        if current:
            result.append(''.join(current))
        
        return ''.join(result)
