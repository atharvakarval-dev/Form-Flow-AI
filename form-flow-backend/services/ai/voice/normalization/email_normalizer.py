"""
Email Normalizer

Email-specific voice input normalization.
"""

import re
from typing import Dict, Any, Optional, Tuple

from services.ai.voice.normalization.base_normalizer import BaseNormalizer
from services.ai.voice.config import (
    STT_EMAIL_PATTERNS,
    apply_domain_corrections,
    apply_tld_corrections,
    COMMON_DOMAINS,
    COMMON_TLDS,
)


class EmailNormalizer(BaseNormalizer):
    """
    Normalize email addresses from voice input.
    
    Handles:
    - "john at gmail dot com" → "john@gmail.com"
    - Domain corrections: "gee mail" → "gmail"
    - TLD corrections: "dot calm" → ".com"
    - Spelled out: "j o h n" → "john"
    - Space handling around @ and dots
    """
    
    # Prefixes to strip
    PREFIXES = [
        r"^(?:my\s+)?(?:email\s+(?:address\s+)?)?(?:is\s+)?",
        r"^(?:it'?s?\s+)?",
        r"^(?:the\s+email\s+is\s+)?",
    ]
    
    def normalize(
        self, 
        text: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Normalize email from voice input.
        
        Args:
            text: Raw voice input
            context: Optional context
            
        Returns:
            Normalized email address
        """
        if not text:
            return ""
        
        result = text.lower().strip()
        
        # Strip conversational prefixes
        result = self.strip_conversational_prefix(result, self.PREFIXES)
        
        # Apply TLD corrections first (before @ replacement)
        result = apply_tld_corrections(result)
        
        # Apply domain corrections
        result = apply_domain_corrections(result)
        
        # Apply STT email patterns
        for pattern, replacement in STT_EMAIL_PATTERNS.items():
            result = result.replace(pattern, replacement)
        
        # Handle spaces around @ (context-aware)
        result = self._smart_at_replacement(result)
        
        # Remove spaces around @ and dots
        result = re.sub(r'\s*@\s*', '@', result)
        result = re.sub(r'\s*\.\s*', '.', result)
        
        # Autocomplete common domains if TLD is missing
        # e.g. "john@gmail" -> "john@gmail.com"
        if '@' in result:
            parts = result.split('@', 1)
            if len(parts) == 2:
                local, domain = parts
                domain = domain.strip()
                # If domain has no dot and is a common provider base
                if '.' not in domain:
                    common_bases = ['gmail', 'yahoo', 'hotmail', 'outlook', 'aol', 'msn', 'icloud', 'live']
                    if domain in common_bases:
                        result = f"{local}@{domain}.com"
        
        # Remove any remaining spaces (emails don't have spaces)
        result = result.replace(' ', '')
        
        return result
    
    def _smart_at_replacement(self, text: str) -> str:
        """
        Context-aware @ replacement.
        
        Only replaces ' at ' when followed by domain-like words,
        preventing corruption of names like "Atharva".
        """
        # If already has @, just clean it
        if '@' in text:
            return text
        
        # Known domain patterns that indicate email context
        domain_indicators = [
            'gmail', 'yahoo', 'hotmail', 'outlook', 'aol', 'icloud',
            'protonmail', 'live', 'msn', 'mail'
        ]
        
        # Check if text looks like an email
        text_lower = text.lower()
        has_domain = any(d in text_lower for d in domain_indicators)
        has_tld = any(f'.{tld}' in text_lower or f'dot {tld}' in text_lower 
                     for tld in COMMON_TLDS)
        
        if has_domain or has_tld:
            # Safe to replace ' at '
            text = re.sub(r'\s+at\s+', '@', text, flags=re.IGNORECASE)
        
        return text
    
    def validate(self, email: str) -> Tuple[bool, float]:
        """
        Validate email format.
        
        Args:
            email: Normalized email
            
        Returns:
            Tuple of (is_valid, confidence)
        """
        if not email:
            return False, 0.0
        
        # Basic email pattern
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        is_valid = bool(re.match(pattern, email))
        
        if not is_valid:
            return False, 0.3
        
        # Check for common domain (higher confidence)
        domain = email.split('@')[1] if '@' in email else ''
        if domain in COMMON_DOMAINS:
            return True, 0.98
        
        return True, 0.92
