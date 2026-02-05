"""
Value Refiner

Post-extraction value cleanup and formatting.
Centralizes ALL value cleaning logic in one place.
"""

import re
from typing import Dict, List, Any, Optional

from services.ai.normalizers import (
    normalize_email_smart,
    normalize_phone_smart,
    normalize_name_smart,
    normalize_text_smart,
    normalize_number_smart,
)
from utils.logging import get_logger

logger = get_logger(__name__)

# Import TextRefiner if available
try:
    from services.ai.text_refiner import get_text_refiner
    TEXT_REFINER_AVAILABLE = True
except ImportError:
    TEXT_REFINER_AVAILABLE = False


class ValueRefiner:
    """
    Post-extraction value cleanup and formatting.
    
    Centralizes all value cleaning:
    - Removes conversational prefixes
    - Normalizes formats (email, phone, etc.)
    - Uses TextRefiner for AI-powered cleanup if available
    """
    
    # Transition words that should be stripped from values
    TRANSITION_WORDS = [
        r'\band\s+my\b',
        r'\band\s+the\b', 
        r'\balso\b',
        r'\bplus\b',
        r'\bmy\s+\w+\s+is\b',
    ]
    
    def __init__(self, use_text_refiner: bool = False):
        """
        Initialize value refiner.
        
        Args:
            use_text_refiner: Whether to use AI text refiner if available
        """
        self.use_text_refiner = use_text_refiner and TEXT_REFINER_AVAILABLE
        self._text_refiner = None
    
    def refine_values(
        self,
        extracted: Dict[str, str],
        field_definitions: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        Clean and format extracted values.
        
        Args:
            extracted: Raw extracted values
            field_definitions: Field definitions for type-aware cleaning
            
        Returns:
            Refined values
        """
        refined = {}
        
        for field_name, value in extracted.items():
            if not value:
                continue
            
            # Find field definition
            field_info = next(
                (f for f in field_definitions if f.get('name') == field_name),
                {}
            )
            
            # Apply refinement
            refined_value = self._refine_single_value(value, field_info)
            if refined_value:
                refined[field_name] = refined_value
        
        return refined
    
    def _refine_single_value(
        self, 
        value: str, 
        field_info: Dict[str, Any]
    ) -> str:
        """
        Refine a single extracted value.
        
        Args:
            value: Raw extracted value
            field_info: Field definition
            
        Returns:
            Refined value
        """
        if value is None:
            return None
            
        # Ensure value is string
        if not isinstance(value, str):
            value = str(value)
        if not value.strip():
            return ""
        
        field_type = field_info.get('type', 'text')
        field_name = field_info.get('name', '').lower()
        field_label = field_info.get('label', '').lower()
        
        # Step 1: Remove transition words
        value = self._strip_transitions(value)
        
        # Step 2: Apply type-specific normalization
        if field_type == 'email' or 'email' in field_name or 'email' in field_label:
            value = normalize_email_smart(value)
        elif field_type == 'tel' or any(k in field_name for k in ['phone', 'mobile', 'tel']):
            value = normalize_phone_smart(value)
        elif 'name' in field_name or 'name' in field_label:
            value = normalize_name_smart(value)
        elif field_type == 'number':
            value = normalize_number_smart(value)
        else:
            value = normalize_text_smart(value)
        
        # Step 3: Use TextRefiner for AI-powered cleanup (optional)
        if self.use_text_refiner and field_type in ['text', 'textarea']:
            value = self._apply_text_refiner(value, field_info)
            
        # Step 4: Validate against options if available (Select/Dropdown)
        # This fixes "British Indian Ocean Territory" vs "India"
        options = field_info.get('options', [])
        if options and isinstance(options, list):
            matched_option = self._refine_against_options(value, options)
            if matched_option:
                return matched_option

        return value.strip()
        
    def _refine_against_options(self, value: str, options: List[str]) -> Optional[str]:
        """
        Match value against a list of options using fuzzy logic using Python's difflib.
        Prioritizes exact matches and word-boundary matches.
        """
        if not value or not options:
            return None
            
        if not value or not options:
            return None
            
        value_lower = value.lower().strip()
        
        # Normalize options to strings for matching
        # If option is dict, use 'label' or 'value'
        normalized_options = []
        original_map = {} # Map lower->original
        
        for opt in options:
            if isinstance(opt, dict):
                # Prefer label/text for matching user speech
                opt_str = opt.get('label') or opt.get('text') or opt.get('name') or opt.get('value') or str(opt)
            else:
                opt_str = str(opt)
            
            if opt_str:
                normalized_options.append(opt_str)
                # Store mapping to return the ORIGINAL option format (dict or string) 
                # OR should we return just the string? 
                # The Extractor generally returns the STRING value to be filled in the form.
                # If the form expects the 'value' ID (e.g. "IN" for India), we might need that.
                # But for now, let's stick to returning the label/string so the frontend can handle selection?
                # Actually, if we return the label "India", frontend can select "India".
                # If we return "IN", frontend select might fail if it matches by label text from user input.
                # Let's return the MATCHED STRING for now to be safe with existing logic.
                original_map[opt_str.lower().strip()] = opt_str
        
        # 1. Exact Match (Case Insensitive)
        if value_lower in original_map:
            return original_map[value_lower]
                
        # 2. Starts With Match
        for opt_str in normalized_options:
             if opt_str.lower().strip().startswith(value_lower):
                 return original_map[opt_str.lower().strip()]

        # 3. Fuzzy Match
        import difflib
        matches = difflib.get_close_matches(value, normalized_options, n=1, cutoff=0.6)
        
        if matches:
            return original_map[matches[0].lower().strip()]
            
        return None
    
    def _strip_transitions(self, value: str) -> str:
        """
        Remove transition words from values.
        
        Args:
            value: Raw value that may contain transitions
            
        Returns:
            Value with transitions removed
        """
        result = value
        
        for pattern in self.TRANSITION_WORDS:
            # Only match at the END of the value
            result = re.sub(pattern + r'\s*.*$', '', result, flags=re.IGNORECASE)
        
        return result.strip()
    
    def _apply_text_refiner(
        self, 
        value: str, 
        field_info: Dict[str, Any]
    ) -> str:
        """
        Apply AI text refiner for sophisticated cleanup.
        
        Args:
            value: Value to refine
            field_info: Field definition
            
        Returns:
            Refined value
        """
        try:
            if not self._text_refiner:
                self._text_refiner = get_text_refiner()
            
            if self._text_refiner:
                refined = self._text_refiner.refine_extracted_value(
                    value,
                    field_type=field_info.get('type', 'text'),
                    field_name=field_info.get('name', ''),
                    field_label=field_info.get('label', '')
                )
                if refined:
                    return refined
        except Exception as e:
            logger.debug(f"TextRefiner error (falling back to original): {e}")
        
        return value
    
    def validate_value(
        self, 
        value: str, 
        field_info: Dict[str, Any]
    ) -> bool:
        """
        Validate a refined value against field type expectations.
        
        Args:
            value: Refined value
            field_info: Field definition
            
        Returns:
            True if value is valid
        """
        if not value:
            return False
        
        field_type = field_info.get('type', 'text')
        field_name = field_info.get('name', '').lower()
        
        # Email validation
        if field_type == 'email' or 'email' in field_name:
            return '@' in value and '.' in value.split('@')[-1]
        
        # Phone validation
        if field_type == 'tel' or 'phone' in field_name:
            digits = re.sub(r'[^\d]', '', value)
            return 10 <= len(digits) <= 15
        
        # Name validation
        if 'name' in field_name:
            words = value.split()
            return len(words) >= 1 and all(w.isalpha() for w in words)
        
        # Number validation
        if field_type == 'number':
            try:
                float(value)
                return True
            except ValueError:
                return False
        
        # Generic text - just needs content
        return len(value) >= 1
