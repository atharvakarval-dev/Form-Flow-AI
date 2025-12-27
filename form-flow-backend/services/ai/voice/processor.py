"""
Voice Input Processor

Core voice processing functionality.
Re-exports components from submodules for backwards compatibility.
"""

import re
from typing import Dict, Any, Optional, List
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum

from services.ai.normalizers import normalize_email_smart
from utils.logging import get_logger

logger = get_logger(__name__)


class VoiceInputProcessor:
    """
    Handle voice-specific issues that text doesn't have.
    
    Converts spoken text to proper format:
    - "john at gmail dot com" → "john@gmail.com"
    - "five five five one two three four" → "555-1234"
    - "j o h n" → "john" (spelled out letters)
    """
    
    # Common STT (Speech-to-Text) articulation patterns
    STT_CORRECTIONS = {
        'at the rate': '@', 'at the rate of': '@', 'at sign': '@',
        'at symbol': '@', 'at the': '@',
        'dot com': '.com', 'dot org': '.org', 'dot net': '.net',
        'dot edu': '.edu', 'dot co': '.co', 'dot gov': '.gov', 'dot io': '.io',
        'gmail dot com': 'gmail.com', 'yahoo dot com': 'yahoo.com',
        'g mail': 'gmail', 'gee mail': 'gmail', 'hot mail': 'hotmail',
        'underscore': '_', 'under score': '_', 'hyphen': '-', 'dash': '-',
        'period': '.', 'dot': '.', 'full stop': '.', 'plus': '+',
    }
    
    # Number words to digits
    NUMBER_WORDS = {
        'zero': '0', 'oh': '0', 'o': '0', 'one': '1', 'two': '2',
        'three': '3', 'four': '4', 'five': '5', 'six': '6',
        'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
    }
    
    # Learning system for user corrections
    _user_corrections: Dict[str, str] = {}
    _correction_count: Dict[str, int] = defaultdict(int)
    
    @classmethod
    def normalize_voice_input(
        cls, 
        raw_voice_text: str,
        expected_field_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Normalize voice input with context awareness.
        
        Args:
            raw_voice_text: Raw text from STT
            expected_field_type: Hint about what type of data is expected
            context: Previous field values for cross-field validation
            
        Returns:
            Normalized text ready for extraction
        """
        if not raw_voice_text:
            return ""
        
        normalized = raw_voice_text.strip().lower()
        
        # Apply learned corrections
        normalized = cls._apply_learned_corrections(normalized)
        
        # Apply general STT corrections
        normalized = cls._apply_stt_corrections(normalized)
        
        # Handle spelled-out text
        if cls._is_spelled_out(normalized):
            normalized = cls._join_spelled_letters(normalized)
        
        # Field-specific normalization
        if expected_field_type == 'email':
            normalized = cls._normalize_email(normalized)
        elif expected_field_type in ['tel', 'phone']:
            normalized = cls._normalize_phone(normalized, context)
        elif expected_field_type == 'number':
            normalized = cls._normalize_number(normalized)
        elif expected_field_type == 'name':
            normalized = cls._normalize_name(normalized)
        
        return normalized.strip()
    
    @classmethod
    def _apply_learned_corrections(cls, text: str) -> str:
        """Apply corrections learned from user feedback."""
        result = text
        for wrong, correct in cls._user_corrections.items():
            if wrong in result:
                result = result.replace(wrong, correct)
        return result
    
    @classmethod
    def learn_from_correction(cls, heard: str, actual: str):
        """Learn from user corrections to improve over time."""
        if heard and actual and heard != actual:
            heard_lower = heard.lower().strip()
            actual_lower = actual.lower().strip()
            
            # Only learn if it's a clear pattern
            if len(heard_lower) >= 3 and len(actual_lower) >= 3:
                cls._user_corrections[heard_lower] = actual_lower
                cls._correction_count[heard_lower] += 1
    
    @classmethod
    def _apply_stt_corrections(cls, text: str) -> str:
        """Apply all STT correction patterns."""
        result = text
        for pattern, replacement in cls.STT_CORRECTIONS.items():
            result = result.replace(pattern, replacement)
        return result
    
    @classmethod
    def _is_spelled_out(cls, text: str) -> bool:
        """Detect if user is spelling out letters."""
        words = text.split()
        if len(words) < 4:
            return False
        single_letters = sum(1 for w in words if len(w) == 1 and w.isalpha())
        return single_letters >= len(words) * 0.6
    
    @classmethod
    def _join_spelled_letters(cls, text: str) -> str:
        """Join spelled out letters: 'j o h n at g m a i l' → 'john@gmail'"""
        words = text.split()
        result = []
        current = []
        
        for word in words:
            # Check for separators
            if word in ['at', '@']:
                if current:
                    result.append(''.join(current))
                    current = []
                result.append('@')
            elif word in ['dot', '.']:
                if current:
                    result.append(''.join(current))
                    current = []
                result.append('.')
            elif len(word) == 1 and word.isalpha():
                current.append(word)
            else:
                if current:
                    result.append(''.join(current))
                    current = []
                result.append(word)
        
        if current:
            result.append(''.join(current))
        
        return ''.join(result)
    
    @classmethod
    def _normalize_email(cls, text: str) -> str:
        """Normalize email using centralized smart normalizer."""
        return normalize_email_smart(text)
    
    @classmethod
    def _normalize_phone(cls, text: str, context: Optional[Dict] = None) -> str:
        """Normalize phone numbers."""
        # Convert number words to digits
        words = text.split()
        result = []
        for word in words:
            if word in cls.NUMBER_WORDS:
                result.append(cls.NUMBER_WORDS[word])
            else:
                result.append(word)
        
        text = ' '.join(result)
        
        # Extract digits only
        digits = re.sub(r'[^\d+]', '', text)
        return digits
    
    @classmethod
    def _normalize_number(cls, text: str) -> str:
        """Convert spoken numbers to digits."""
        words = text.split()
        result = []
        for word in words:
            if word in cls.NUMBER_WORDS:
                result.append(cls.NUMBER_WORDS[word])
            elif word.isdigit():
                result.append(word)
        return ''.join(result) if result else text
    
    @classmethod
    def _normalize_name(cls, text: str) -> str:
        """Normalize names with proper capitalization."""
        # Remove common prefixes
        prefixes = [
            r"^(?:my\s+)?(?:name\s+is\s+)",
            r"^(?:i'?m\s+)",
            r"^(?:this\s+is\s+)",
            r"^(?:call\s+me\s+)",
        ]
        
        for prefix in prefixes:
            text = re.sub(prefix, '', text, flags=re.IGNORECASE)
        
        return text.strip().title()
    
    @classmethod
    def detect_hesitation(cls, text: str) -> Dict[str, Any]:
        """Detect if user is hesitating/struggling."""
        filler_patterns = [
            r'\bum+\b', r'\buh+\b', r'\ber+\b', r'\bah+\b',
            r'\blike\b', r'\byou know\b', r'\bi mean\b',
            r'\bso\b', r'\bwell\b', r'\bactually\b',
        ]
        
        filler_count = sum(
            len(re.findall(pattern, text.lower()))
            for pattern in filler_patterns
        )
        
        word_count = len(text.split())
        is_hesitant = filler_count >= 2 or (word_count > 0 and filler_count / word_count > 0.3)
        
        return {
            "is_hesitant": is_hesitant,
            "filler_count": filler_count,
            "confidence_penalty": min(0.3, filler_count * 0.1)
        }
    
    @classmethod
    def extract_partial_email(cls, text: str) -> Dict[str, Any]:
        """Extract parts of an email for step-by-step entry."""
        result = {"local_part": None, "domain": None}
        
        if '@' in text:
            parts = text.split('@')
            result["local_part"] = parts[0].strip()
            if len(parts) > 1:
                result["domain"] = parts[1].strip()
        
        return result


# Re-export PhoneticMatcher for compatibility
class PhoneticMatcher:
    """Match names phonetically for better STT error handling."""
    
    PHONETIC_MAP = {
        'B': '1', 'F': '1', 'P': '1', 'V': '1',
        'C': '2', 'G': '2', 'J': '2', 'K': '2', 'Q': '2', 'S': '2', 'X': '2', 'Z': '2',
        'D': '3', 'T': '3',
        'L': '4',
        'M': '5', 'N': '5',
        'R': '6',
    }
    
    @classmethod
    def get_phonetic_key(cls, name: str) -> str:
        """Generate phonetic key for name matching."""
        if not name:
            return ""
        
        name = name.upper().strip()
        first_letter = name[0] if name else ''
        
        # Apply phonetic mapping
        key = first_letter
        prev_code = ''
        
        for char in name[1:]:
            code = cls.PHONETIC_MAP.get(char, '')
            if code and code != prev_code:
                key += code
                prev_code = code
        
        return (key + '0000')[:4]
    
    @classmethod
    def are_similar(cls, name1: str, name2: str, threshold: float = 0.8) -> bool:
        """Check if two names are phonetically similar."""
        key1 = cls.get_phonetic_key(name1)
        key2 = cls.get_phonetic_key(name2)
        
        if not key1 or not key2:
            return False
        
        # Compare keys
        matches = sum(1 for a, b in zip(key1, key2) if a == b)
        similarity = matches / max(len(key1), len(key2))
        
        return similarity >= threshold
