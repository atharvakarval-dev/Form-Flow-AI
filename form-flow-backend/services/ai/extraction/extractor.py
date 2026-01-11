"""
Unified Field Extractor

This is the SINGLE entry point for all field extraction from user input.
All normalization flows through normalizers.py.

Features:
- LLM-based extraction (primary)
- Rule-based fallback
- Multi-field extraction (user gives more than asked for)
- Consistent normalization for all field types
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from services.ai.normalizers import (
    normalize_email_smart,
    normalize_phone_smart,
    normalize_name_smart,
    normalize_text_smart,
    normalize_number_smart,
    split_full_name_smart,
)
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractionResult:
    """Result of field extraction."""
    values: Dict[str, str]  # field_name -> extracted_value
    confidence: Dict[str, float]  # field_name -> confidence score
    needs_confirmation: List[str]  # fields that need user confirmation


class FieldExtractor:
    """
    Unified field extractor that handles ALL extraction logic.
    
    This class is the SINGLE source of truth for extracting field values
    from user input. It uses LLM when available and falls back to rules.
    
    Usage:
        extractor = FieldExtractor()
        result = extractor.extract(
            user_input="my name is John and my email is john@gmail.com",
            target_fields=[{"name": "name", "type": "text"}, {"name": "email", "type": "email"}],
            remaining_fields=[{"name": "phone", "type": "tel"}]  # Also extract these if mentioned
        )
    """
    
    # Field type patterns for rule-based extraction
    FIELD_PATTERNS = {
        'email': r'[a-zA-Z0-9][a-zA-Z0-9._\-+]*\s*@\s*[a-zA-Z0-9][a-zA-Z0-9._\-]*\.[a-zA-Z]{2,}',
        'phone': r'[\+]?[\d\s\-\(\)]{10,}',
        'name': r'(?:^|(?:name\s+is\s+)|(?:i\'?m\s+)|(?:this\s+is\s+))([A-Za-z][a-z]+(?:\s+[A-Za-z][a-z]+){0,3})',
        'number': r'\b\d+(?:\.\d+)?\b',
    }
    
    # Keywords that indicate a specific field type
    FIELD_KEYWORDS = {
        'email': ['email', 'e-mail', 'mail', '@'],
        'phone': ['phone', 'mobile', 'cell', 'number', 'contact', 'call'],
        'name': ['name', 'called', 'i am', "i'm"],
        'country': ['country', 'nation', 'from'],
        'address': ['address', 'street', 'city', 'zip'],
        'company': ['company', 'organization', 'work', 'employer'],
        'message': ['message', 'comment', 'note', 'description', 'feedback', 'inquiry', 'question', 'text', 'details'],
    }
    
    def __init__(self, llm_client=None):
        """
        Initialize the field extractor.
        
        Args:
            llm_client: Optional LangChain LLM client for intelligent extraction
        """
        self.llm = llm_client
    
    def extract(
        self,
        user_input: str,
        target_fields: List[Dict[str, Any]],
        remaining_fields: Optional[List[Dict[str, Any]]] = None,
        conversation_context: Optional[str] = None
    ) -> ExtractionResult:
        """
        Extract field values from user input.
        
        This is the MAIN entry point. It will:
        1. Try LLM extraction first (if available)
        2. Fall back to rule-based extraction
        3. Always normalize values through normalizers.py
        4. Extract additional fields if user provides them
        
        Args:
            user_input: Raw text from user
            target_fields: Fields we're actively asking about
            remaining_fields: Other fields that could be mentioned
            conversation_context: Previous conversation for context
            
        Returns:
            ExtractionResult with values, confidence, and confirmation needs
        """
        # Combine all possible fields for extraction
        all_fields = list(target_fields)
        if remaining_fields:
            all_fields.extend(remaining_fields)
        
        # Try LLM extraction first
        if self.llm:
            try:
                result = self._extract_with_llm(user_input, all_fields, conversation_context)
                if result.values:
                    return result
            except Exception as e:
                logger.warning(f"LLM extraction failed, using fallback: {e}")
        
        # Rule-based fallback
        return self._extract_with_rules(user_input, all_fields)
    
    def _extract_with_llm(
        self,
        user_input: str,
        fields: List[Dict[str, Any]],
        context: Optional[str]
    ) -> ExtractionResult:
        """Extract using LLM for intelligent understanding."""
        
        # Build field descriptions for the prompt
        field_descriptions = []
        for f in fields:
            name = f.get('name', '')
            label = f.get('label', name)
            ftype = f.get('type', 'text')
            field_descriptions.append(f"- {name} ({label}): type={ftype}")
        
        prompt = f"""Extract field values from the user's message.

Fields to look for:
{chr(10).join(field_descriptions)}

User message: "{user_input}"

RULES:
1. Extract ALL values mentioned, not just the first one
2. For email: if user says "atharva karwal@ gmail.com" extract it properly
3. For phone: extract digits even if formatted with spaces
4. For country: extract country name if mentioned
5. If a value is not clearly mentioned, don't extract it

Return ONLY a JSON object with field names as keys and extracted values:
{{"field_name": "extracted_value", ...}}

If no values found, return: {{}}"""

        try:
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON from response
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if json_match:
                raw_values = json.loads(json_match.group())
                
                # Normalize all extracted values
                return self._normalize_extracted_values(raw_values, fields)
        except Exception as e:
            logger.error(f"LLM extraction error: {e}")
            raise
        
        return ExtractionResult(values={}, confidence={}, needs_confirmation=[])
    
    def _extract_with_rules(
        self,
        user_input: str,
        fields: List[Dict[str, Any]]
    ) -> ExtractionResult:
        """Rule-based extraction when LLM is unavailable."""
        
        values = {}
        confidence = {}
        needs_confirmation = []
        
        text = user_input.lower().strip()
        
        # Check if we have separate name component fields (first, middle, last)
        name_component_fields = self._detect_name_component_fields(fields)
        name_components_extracted = False
        
        # If we have name component fields, try to split a full name input
        if name_component_fields:
            split_values = self._extract_split_name(user_input, name_component_fields)
            if split_values:
                values.update(split_values)
                for field_name in split_values:
                    confidence[field_name] = 0.9
                name_components_extracted = True
        
        for field in fields:
            name = field.get('name', '')
            label = field.get('label', name)
            ftype = field.get('type', 'text')
            
            # Skip name component fields if already extracted via splitting
            if name_components_extracted and name in name_component_fields:
                continue
            
            # Determine field category
            category = self._detect_field_category(name, label, ftype)
            
            # Check if this field is mentioned
            if not self._is_field_mentioned(text, category, field):
                continue
            
            # Extract value based on category
            value = self._extract_by_category(user_input, category, field)
            
            if value:
                values[name] = value
                confidence[name] = 0.85
        
        return ExtractionResult(
            values=values,
            confidence=confidence,
            needs_confirmation=needs_confirmation
        )
    
    def _detect_name_component_fields(self, fields: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Detect if fields contain separate name components (first, middle, last).
        
        Returns:
            Dict mapping component type ('first', 'middle', 'last') to field name
        """
        components = {}
        
        for field in fields:
            name = field.get('name', '').lower()
            label = field.get('label', '').lower()
            combined = f"{name} {label}"
            
            if 'first' in combined and 'name' in combined:
                components['first'] = field.get('name')
            elif 'middle' in combined and 'name' in combined:
                components['middle'] = field.get('name')
            elif 'last' in combined and 'name' in combined:
                components['last'] = field.get('name')
            elif 'surname' in combined or 'family' in combined:
                components['last'] = field.get('name')
        
        # Only return if we have at least 2 distinct name component fields
        if len(components) >= 2:
            return components
        return {}
    
    def _extract_split_name(
        self, 
        user_input: str, 
        component_fields: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Split a full name input into components for separate name fields.
        
        Args:
            user_input: User's input text (e.g., "Samarth Mukund Patil")
            component_fields: Mapping of component type to field name
            
        Returns:
            Dict of field_name -> extracted_value
        """
        # Split the name using normalizer utility
        name_parts = split_full_name_smart(user_input)
        
        result = {}
        
        # Map split parts to field names
        if 'first' in component_fields and name_parts.get('first'):
            result[component_fields['first']] = name_parts['first']
        
        if 'middle' in component_fields and name_parts.get('middle'):
            result[component_fields['middle']] = name_parts['middle']
        
        if 'last' in component_fields and name_parts.get('last'):
            result[component_fields['last']] = name_parts['last']
        
        # Only return if we extracted at least one component
        return result if result else {}
    
    def _detect_field_category(self, name: str, label: str, ftype: str) -> str:
        """Detect what category a field belongs to."""
        combined = f"{name} {label}".lower()
        
        if ftype == 'email' or 'email' in combined:
            return 'email'
        if ftype == 'tel' or any(k in combined for k in ['phone', 'mobile', 'tel']):
            return 'phone'
        if 'name' in combined:
            return 'name'
        if 'country' in combined:
            return 'country'
        if 'company' in combined or 'organization' in combined:
            return 'company'
        if ftype == 'number' or 'age' in combined or 'year' in combined:
            return 'number'
        # message, comments, notes, textarea - free text fields
        if ftype == 'textarea' or any(k in combined for k in ['message', 'comment', 'note', 'description', 'feedback', 'inquiry', 'question']):
            return 'message'
        
        return 'text'
    
    def _is_field_mentioned(self, text: str, category: str, field: Dict) -> bool:
        """Check if this field type is mentioned in the text."""
        # Always check for email patterns
        if category == 'email' and ('@' in text or ' at ' in text):
            return True
        
        # Check for phone patterns (digits)
        if category == 'phone' and re.search(r'\d{5,}', re.sub(r'\s', '', text)):
            return True
        
        # Check for country keywords
        if category == 'country' and any(k in text for k in ['country', 'from', 'india', 'usa', 'uk']):
            return True
        
        # Message/textarea fields - almost always relevant when there's text
        if category == 'message' and len(text.strip()) > 10:
            return True
        
        # Check field keywords
        keywords = self.FIELD_KEYWORDS.get(category, [])
        if any(k in text for k in keywords):
            return True
        
        # Check if field label is mentioned
        label = field.get('label', '').lower()
        if label and label in text:
            return True
        
        return False
    
    def _extract_by_category(self, text: str, category: str, field: Dict) -> Optional[str]:
        """Extract value based on field category."""
        
        if category == 'email':
            return self._extract_email(text)
        elif category == 'phone':
            return self._extract_phone(text)
        elif category == 'name':
            return self._extract_name(text)
        elif category == 'country':
            return self._extract_country(text)
        elif category == 'number':
            return self._extract_number(text)
        elif category == 'message':
            return self._extract_message(text, field)
        else:
            return self._extract_text(text, field)
    
    def _extract_email(self, text: str) -> Optional[str]:
        """Extract and normalize email."""
        # First normalize the text
        normalized = normalize_email_smart(text)
        
        # Check if we got a valid email
        if '@' in normalized and re.search(r'\.\w{2,}$', normalized):
            # Clean up: extract just the email part if there's extra text
            email_match = re.search(r'[a-z0-9._\-+]+@[a-z0-9._\-]+\.[a-z]{2,}', normalized)
            if email_match:
                return email_match.group()
        
        return None
    
    def _extract_phone(self, text: str) -> Optional[str]:
        """Extract and normalize phone."""
        return normalize_phone_smart(text)
    
    def _extract_name(self, text: str) -> Optional[str]:
        """Extract and normalize name."""
        return normalize_name_smart(text)
    
    def _extract_country(self, text: str) -> Optional[str]:
        """Extract country from text."""
        # Common country patterns
        country_patterns = [
            r'(?:country\s+is\s+|from\s+|in\s+)([A-Za-z]+(?:\s+[A-Za-z]+)?)',
            r'\b(India|USA|UK|Canada|Australia|Germany|France|Japan|China)\b',
        ]
        
        for pattern in country_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip().title()
        
        return None
    
    def _extract_number(self, text: str) -> Optional[str]:
        """Extract and normalize number."""
        return normalize_number_smart(text)
    
    def _extract_text(self, text: str, field: Dict) -> Optional[str]:
        """Extract generic text value."""
        return normalize_text_smart(text)
    
    def _extract_message(self, text: str, field: Dict) -> Optional[str]:
        """Extract message/textarea content - captures full text."""
        # For message fields, we want the full user text (cleaned up)
        cleaned = normalize_text_smart(text)
        # Return the text if it has meaningful content
        if cleaned and len(cleaned.strip()) > 0:
            return cleaned.strip()
        return None
    
    def _normalize_extracted_values(
        self,
        raw_values: Dict[str, str],
        fields: List[Dict[str, Any]]
    ) -> ExtractionResult:
        """Normalize all extracted values based on their field types."""
        
        normalized = {}
        confidence = {}
        needs_confirmation = []
        
        # Build field type map
        field_types = {}
        for f in fields:
            name = f.get('name', '')
            label = f.get('label', name)
            ftype = f.get('type', 'text')
            field_types[name] = self._detect_field_category(name, label, ftype)
        
        # Check for name component fields and fix duplicate full names
        name_component_fields = self._detect_name_component_fields(fields)
        if name_component_fields:
            raw_values = self._fix_duplicate_name_values(raw_values, name_component_fields)
        
        for name, value in raw_values.items():
            if not value or not isinstance(value, str):
                continue
            
            category = field_types.get(name, 'text')
            
            # Normalize based on category
            if category == 'email':
                normalized_value = normalize_email_smart(value)
                conf = 0.95 if '@' in normalized_value else 0.6
            elif category == 'phone':
                normalized_value = normalize_phone_smart(value)
                conf = 0.9 if len(re.sub(r'\D', '', normalized_value)) >= 10 else 0.7
            elif category == 'name':
                normalized_value = normalize_name_smart(value)
                conf = 0.9
            elif category == 'number':
                normalized_value = normalize_number_smart(value)
                conf = 0.9
            else:
                normalized_value = normalize_text_smart(value)
                conf = 0.85
            
            normalized[name] = normalized_value
            confidence[name] = conf
            
            if conf < 0.8:
                needs_confirmation.append(name)
        
        return ExtractionResult(
            values=normalized,
            confidence=confidence,
            needs_confirmation=needs_confirmation
        )
    
    def _fix_duplicate_name_values(
        self, 
        raw_values: Dict[str, str], 
        component_fields: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Fix case where LLM puts the same full name in all name component fields.
        
        Example fix:
            {"first_name": "John Doe", "last_name": "John Doe"} 
            → {"first_name": "John", "last_name": "Doe"}
        """
        # Get the field names for name components
        component_field_names = set(component_fields.values())
        
        # Get values for name component fields
        name_values = {
            k: v for k, v in raw_values.items() 
            if k in component_field_names and v
        }
        
        # Check if multiple fields have the same multi-word value
        if len(name_values) >= 2:
            values_list = list(name_values.values())
            first_value = values_list[0]
            
            # Check if all name component fields have the same value
            # and that value contains multiple words
            if (all(v == first_value for v in values_list) and 
                len(first_value.split()) >= 2):
                
                # This is the bug case - split the name properly
                name_parts = split_full_name_smart(first_value)
                
                # Update raw_values with split values
                fixed_values = dict(raw_values)
                
                if 'first' in component_fields and name_parts.get('first'):
                    fixed_values[component_fields['first']] = name_parts['first']
                
                if 'middle' in component_fields and name_parts.get('middle'):
                    fixed_values[component_fields['middle']] = name_parts['middle']
                elif 'middle' in component_fields:
                    # Remove the duplicate full name from middle if no middle part
                    fixed_values[component_fields['middle']] = ''
                
                if 'last' in component_fields and name_parts.get('last'):
                    fixed_values[component_fields['last']] = name_parts['last']
                
                return fixed_values
        
        return raw_values


# Singleton instance
_field_extractor: Optional[FieldExtractor] = None


def get_field_extractor(llm_client=None) -> FieldExtractor:
    """Get or create the field extractor singleton."""
    global _field_extractor
    if _field_extractor is None:
        _field_extractor = FieldExtractor(llm_client)
    elif llm_client and _field_extractor.llm is None:
        _field_extractor.llm = llm_client
    return _field_extractor
