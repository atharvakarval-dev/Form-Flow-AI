"""
Contextual Suggestion Engine

Industry-grade pattern detection and intelligent suggestions for form-filling.
Implements patterns from modern conversational AI systems:

1. EMAIL PATTERN INFERENCE: Detects email format from personal email and 
   suggests work email with company domain when available.

2. GEOGRAPHIC INFERENCE: Extracts country/region from phone number prefixes
   and uses this to suggest country/region fields.

3. FORMAT CONSISTENCY: Learns user's formatting preferences (capitalization,
   date formats) and applies them consistently across fields.

4. NAME PATTERN DETECTION: Extracts first/last name patterns for related fields.

5. ADAPTIVE SUGGESTIONS: Tracks suggestion acceptance rate to improve future
   suggestions (suggests less aggressively if user often rejects).

Version: 1.0.0
Author: Form-Flow AI
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum

from utils.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Pattern Types
# =============================================================================

class PatternType(str, Enum):
    """Types of patterns the engine can detect."""
    EMAIL_FORMAT = "email_format"       # user.name@domain format
    EMAIL_DOMAIN = "email_domain"       # gmail.com, company.com
    NAME_FORMAT = "name_format"         # First Last, FIRST LAST, first last
    PHONE_COUNTRY = "phone_country"     # Country code from phone prefix
    DATE_FORMAT = "date_format"         # MM/DD, DD/MM, YYYY-MM-DD
    CAPITALIZATION = "capitalization"   # Title Case, UPPER, lower


# =============================================================================
# Phone Country Codes
# =============================================================================

# Common international dialing codes mapped to countries
PHONE_COUNTRY_CODES: Dict[str, Dict[str, str]] = {
    # North America
    "+1": {"country": "United States", "country_code": "US", "region": "North America"},
    "1": {"country": "United States", "country_code": "US", "region": "North America"},
    
    # India
    "+91": {"country": "India", "country_code": "IN", "region": "South Asia"},
    "91": {"country": "India", "country_code": "IN", "region": "South Asia"},
    
    # UK
    "+44": {"country": "United Kingdom", "country_code": "GB", "region": "Europe"},
    "44": {"country": "United Kingdom", "country_code": "GB", "region": "Europe"},
    
    # Australia
    "+61": {"country": "Australia", "country_code": "AU", "region": "Oceania"},
    "61": {"country": "Australia", "country_code": "AU", "region": "Oceania"},
    
    # Germany
    "+49": {"country": "Germany", "country_code": "DE", "region": "Europe"},
    "49": {"country": "Germany", "country_code": "DE", "region": "Europe"},
    
    # France
    "+33": {"country": "France", "country_code": "FR", "region": "Europe"},
    "33": {"country": "France", "country_code": "FR", "region": "Europe"},
    
    # Canada (shares +1 with US, but area codes differ)
    # Common Canadian area codes
    "+1204": {"country": "Canada", "country_code": "CA", "region": "North America"},
    "+1416": {"country": "Canada", "country_code": "CA", "region": "North America"},
    "+1604": {"country": "Canada", "country_code": "CA", "region": "North America"},
    
    # China
    "+86": {"country": "China", "country_code": "CN", "region": "East Asia"},
    "86": {"country": "China", "country_code": "CN", "region": "East Asia"},
    
    # Japan
    "+81": {"country": "Japan", "country_code": "JP", "region": "East Asia"},
    "81": {"country": "Japan", "country_code": "JP", "region": "East Asia"},
    
    # UAE
    "+971": {"country": "United Arab Emirates", "country_code": "AE", "region": "Middle East"},
    "971": {"country": "United Arab Emirates", "country_code": "AE", "region": "Middle East"},
    
    # Singapore
    "+65": {"country": "Singapore", "country_code": "SG", "region": "Southeast Asia"},
    "65": {"country": "Singapore", "country_code": "SG", "region": "Southeast Asia"},
}


# =============================================================================
# Email Domain Patterns
# =============================================================================

# Common personal email domains
PERSONAL_EMAIL_DOMAINS = {
    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 
    'icloud.com', 'aol.com', 'protonmail.com', 'live.com',
    'mail.com', 'ymail.com', 'msn.com', 'me.com'
}


# =============================================================================
# Suggestion Result
# =============================================================================

@dataclass
class Suggestion:
    """A contextual suggestion for a form field."""
    target_field: str              # Field this suggestion is for
    suggested_value: str           # The suggested value
    confidence: float              # 0.0 - 1.0
    reasoning: str                 # Why this was suggested
    source_patterns: List[str]     # Patterns that led to this suggestion
    prompt_template: str = ""      # How to present to user
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'target_field': self.target_field,
            'suggested_value': self.suggested_value,
            'confidence': self.confidence,
            'reasoning': self.reasoning,
            'source_patterns': self.source_patterns,
            'prompt_template': self.prompt_template
        }


# =============================================================================
# Suggestion Engine
# =============================================================================

class SuggestionEngine:
    """
    Contextual suggestion engine for intelligent form-filling assistance.
    
    Uses pattern detection from completed fields to generate suggestions
    for upcoming fields. Implements patterns similar to how modern LLM
    systems use retrieved context for generation.
    
    Features:
    - Email pattern inference (personal → work email)
    - Geographic inference from phone prefixes
    - Format consistency (capitalization, date formats)
    - Name pattern detection (first/last name splitting)
    - Adaptive suggestion confidence based on acceptance rate
    
    Usage:
        engine = SuggestionEngine()
        
        # Detect patterns from completed field
        patterns = engine.detect_patterns(
            field_name='personal_email',
            field_value='john.doe@gmail.com',
            field_type='email'
        )
        
        # Generate suggestions for upcoming fields
        suggestions = engine.generate_suggestions(
            target_fields=[{'name': 'work_email', 'type': 'email'}],
            extracted_fields={'personal_email': 'john.doe@gmail.com', 'company': 'Acme Corp'},
            detected_patterns=patterns
        )
    """
    
    def __init__(self, suggestion_threshold: float = 0.6):
        """
        Initialize the suggestion engine.
        
        Args:
            suggestion_threshold: Minimum confidence to generate suggestion
        """
        self.suggestion_threshold = suggestion_threshold
        self._pattern_cache: Dict[str, Dict[str, Any]] = {}
    
    # =========================================================================
    # Pattern Detection
    # =========================================================================
    
    def detect_patterns(
        self,
        field_name: str,
        field_value: str,
        field_type: str,
        field_label: str = ""
    ) -> Dict[str, Dict[str, Any]]:
        """
        Detect all patterns from a completed field.
        
        Args:
            field_name: Name of the field
            field_value: Value provided by user
            field_type: Field type (email, tel, text, etc.)
            field_label: Human-readable label
            
        Returns:
            Dictionary of pattern_type -> pattern_data
        """
        patterns = {}
        
        if not field_value:
            return patterns
        
        # Detect email patterns
        if field_type == 'email' or 'email' in (field_name or '').lower():
            email_patterns = self._detect_email_patterns(field_value, field_name)
            patterns.update(email_patterns)
        
        # Detect phone patterns
        if field_type == 'tel' or any(k in (field_name or '').lower() for k in ['phone', 'mobile', 'tel']):
            phone_patterns = self._detect_phone_patterns(field_value)
            patterns.update(phone_patterns)
        
        # Detect name patterns
        if 'name' in (field_name or '').lower() or 'name' in (field_label or '').lower():
            name_patterns = self._detect_name_patterns(field_value, field_name)
            patterns.update(name_patterns)
        
        # Detect capitalization patterns (for any text field)
        cap_patterns = self._detect_capitalization_patterns(field_value)
        patterns.update(cap_patterns)
        
        # Cache patterns for later use
        for pattern_type, pattern_data in patterns.items():
            cache_key = f"{pattern_type}:{field_name}"
            self._pattern_cache[cache_key] = pattern_data
        
        logger.debug(f"Detected {len(patterns)} patterns from {field_name}: {list(patterns.keys())}")
        
        return patterns
    
    def _detect_email_patterns(
        self, 
        email: str, 
        field_name: str
    ) -> Dict[str, Dict[str, Any]]:
        """Detect patterns from an email address."""
        patterns = {}
        
        if '@' not in email:
            return patterns
        
        try:
            local_part, domain = email.rsplit('@', 1)
        except ValueError:
            return patterns
        
        # Store domain pattern
        patterns[PatternType.EMAIL_DOMAIN] = {
            'value': domain,
            'source_field': field_name,
            'is_personal': domain.lower() in PERSONAL_EMAIL_DOMAINS,
            'confidence': 0.95,
            'detected_at': datetime.now().isoformat()
        }
        
        # Detect email format (separator pattern)
        email_format = self._analyze_email_format(local_part)
        patterns[PatternType.EMAIL_FORMAT] = {
            'value': email_format,
            'local_part': local_part,
            'source_field': field_name,
            'confidence': 0.90,
            'detected_at': datetime.now().isoformat()
        }
        
        return patterns
    
    def _analyze_email_format(self, local_part: str) -> str:
        """
        Analyze the format of email local part.
        
        Returns format like:
        - 'first.last' (john.doe)
        - 'firstlast' (johndoe)
        - 'first_last' (john_doe)
        - 'firstl' (johnd)
        - 'flast' (jdoe)
        - 'other'
        """
        # Check for separator patterns
        if '.' in local_part:
            parts = local_part.split('.')
            if len(parts) == 2:
                return 'first.last'
            return 'dotted'
        
        if '_' in local_part:
            parts = local_part.split('_')
            if len(parts) == 2:
                return 'first_last'
            return 'underscored'
        
        # Check for common patterns without separator
        if re.match(r'^[a-z]+[a-z]$', local_part.lower()) and len(local_part) > 5:
            return 'firstlast'
        
        if re.match(r'^[a-z][a-z]+$', local_part.lower()) and len(local_part) <= 5:
            return 'firstl'
        
        return 'other'
    
    def _detect_phone_patterns(self, phone: str) -> Dict[str, Dict[str, Any]]:
        """Detect patterns from a phone number."""
        patterns = {}
        
        # Clean phone number
        cleaned = re.sub(r'[^\d+]', '', phone)
        
        # Try to match country code
        country_info = self._extract_country_from_phone(cleaned)
        
        if country_info:
            patterns[PatternType.PHONE_COUNTRY] = {
                'value': country_info['country'],
                'country_code': country_info['country_code'],
                'region': country_info['region'],
                'phone_prefix': country_info.get('prefix', ''),
                'confidence': country_info['confidence'],
                'detected_at': datetime.now().isoformat()
            }
        
        return patterns
    
    def _extract_country_from_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Extract country information from phone number prefix."""
        # Remove any leading zeros (common in some formats)
        if phone.startswith('00'):
            phone = '+' + phone[2:]
        
        # Try matching with + prefix
        if phone.startswith('+'):
            # Try longer prefixes first (e.g., +1204 before +1)
            for length in [5, 4, 3, 2]:
                prefix = phone[:length]
                if prefix in PHONE_COUNTRY_CODES:
                    info = PHONE_COUNTRY_CODES[prefix].copy()
                    info['prefix'] = prefix
                    info['confidence'] = 0.95 if length > 2 else 0.85
                    return info
        
        # Try matching without + (for numbers like 91XXXXXXXXXX)
        for length in [4, 3, 2]:
            prefix = phone[:length]
            if prefix in PHONE_COUNTRY_CODES:
                info = PHONE_COUNTRY_CODES[prefix].copy()
                info['prefix'] = prefix
                info['confidence'] = 0.80 if length > 2 else 0.70
                return info
        
        # Default to US for 10-digit numbers without prefix
        if len(phone) == 10 and phone[0] in '2345678':
            return {
                'country': 'United States',
                'country_code': 'US',
                'region': 'North America',
                'prefix': '',
                'confidence': 0.60
            }
        
        return None
    
    def _detect_name_patterns(
        self, 
        name: str, 
        field_name: str
    ) -> Dict[str, Dict[str, Any]]:
        """Detect patterns from a name field."""
        patterns = {}
        
        parts = name.strip().split()
        
        if len(parts) >= 2:
            patterns[PatternType.NAME_FORMAT] = {
                'value': 'full_name',
                'first_name': parts[0],
                'last_name': parts[-1],
                'middle_parts': parts[1:-1] if len(parts) > 2 else [],
                'source_field': field_name,
                'confidence': 0.90,
                'detected_at': datetime.now().isoformat()
            }
        elif len(parts) == 1:
            patterns[PatternType.NAME_FORMAT] = {
                'value': 'single_name',
                'name': parts[0],
                'source_field': field_name,
                'confidence': 0.70,
                'detected_at': datetime.now().isoformat()
            }
        
        return patterns
    
    def _detect_capitalization_patterns(self, value: str) -> Dict[str, Dict[str, Any]]:
        """Detect capitalization style from any text value."""
        patterns = {}
        
        if not value or len(value) < 2:
            return patterns
        
        words = value.split()
        
        if all(w.isupper() for w in words):
            cap_style = 'UPPER'
        elif all(w.islower() for w in words):
            cap_style = 'lower'
        elif all(w[0].isupper() and w[1:].islower() for w in words if len(w) > 1):
            cap_style = 'Title Case'
        else:
            cap_style = 'Mixed'
        
        patterns[PatternType.CAPITALIZATION] = {
            'value': cap_style,
            'sample': value,
            'confidence': 0.75,
            'detected_at': datetime.now().isoformat()
        }
        
        return patterns
    
    # =========================================================================
    # Suggestion Generation
    # =========================================================================
    
    def generate_suggestions(
        self,
        target_fields: List[Dict[str, Any]],
        extracted_fields: Dict[str, str],
        detected_patterns: Dict[str, Dict[str, Any]],
        acceptance_rate: float = 0.5
    ) -> List[Suggestion]:
        """
        Generate suggestions for target fields based on detected patterns.
        
        Args:
            target_fields: Fields to generate suggestions for
            extracted_fields: Already extracted field values
            detected_patterns: Patterns detected from previous fields
            acceptance_rate: Historical suggestion acceptance rate (0.0 - 1.0)
            
        Returns:
            List of suggestions for target fields
        """
        suggestions = []
        
        # Adjust threshold based on acceptance rate
        # If user often rejects suggestions, be more conservative
        adjusted_threshold = self.suggestion_threshold
        if acceptance_rate < 0.3:
            adjusted_threshold = 0.8  # Only very confident suggestions
        elif acceptance_rate > 0.7:
            adjusted_threshold = 0.5  # More willing to suggest
        
        for field in target_fields:
            field_name = field.get('name', '')
            field_type = field.get('type', 'text')
            field_label = field.get('label', field_name)
            
            # Try different suggestion strategies
            suggestion = None
            
            # Strategy 1: Work email from personal email + company
            if 'work' in (field_name or '').lower() and 'email' in (field_name or '').lower():
                suggestion = self._suggest_work_email(
                    extracted_fields, 
                    detected_patterns,
                    field_name
                )
            
            # Strategy 2: Country from phone
            elif 'country' in (field_name or '').lower() or 'country' in (field_label or '').lower():
                suggestion = self._suggest_country_from_phone(
                    detected_patterns,
                    field_name
                )
            
            # Strategy 3: First/Last name from full name
            elif 'first' in (field_name or '').lower() and 'name' in (field_name or '').lower():
                suggestion = self._suggest_first_name(
                    detected_patterns,
                    field_name
                )
            elif 'last' in (field_name or '').lower() and 'name' in (field_name or '').lower():
                suggestion = self._suggest_last_name(
                    detected_patterns,
                    field_name
                )
            
            # Strategy 4: Region from phone
            elif 'region' in field_name.lower() or 'state' in field_name.lower():
                suggestion = self._suggest_region_from_phone(
                    detected_patterns,
                    field_name
                )
            
            # Add to results if above threshold
            if suggestion and suggestion.confidence >= adjusted_threshold:
                suggestions.append(suggestion)
                logger.info(f"Generated suggestion for {field_name}: {suggestion.suggested_value} ({suggestion.confidence:.2f})")
        
        return suggestions
    
    def _suggest_work_email(
        self,
        extracted_fields: Dict[str, str],
        detected_patterns: Dict[str, Dict[str, Any]],
        target_field: str
    ) -> Optional[Suggestion]:
        """
        Suggest work email based on personal email format and company name.
        
        Examples:
        - Personal: john.doe@gmail.com + Company: Acme Corp → john.doe@acmecorp.com
        - Personal: jdoe@yahoo.com + Company: Tech Inc → jdoe@techinc.com
        """
        # Get email format pattern
        email_format = detected_patterns.get(PatternType.EMAIL_FORMAT)
        if not email_format:
            return None
        
        local_part = email_format.get('local_part', '')
        if not local_part:
            return None
        
        # Find company name
        company = None
        for field_name, value in extracted_fields.items():
            if any(k in field_name.lower() for k in ['company', 'organization', 'employer', 'business']):
                company = value
                break
        
        if not company:
            return None
        
        # Generate company domain
        company_domain = self._generate_company_domain(company)
        
        # Create suggested email
        suggested_email = f"{local_part}@{company_domain}"
        
        return Suggestion(
            target_field=target_field,
            suggested_value=suggested_email,
            confidence=0.75,
            reasoning=f"Based on your personal email format ({local_part}@...) and company ({company})",
            source_patterns=[PatternType.EMAIL_FORMAT, 'company_name'],
            prompt_template=f"Would your work email be {suggested_email}?"
        )
    
    def _generate_company_domain(self, company: str) -> str:
        """Generate a likely company domain from company name."""
        company_clean = company.lower().strip()
        
        # Remove common suffixes - using regex to match at end only
        # Order matters: longer suffixes first to avoid partial matches
        suffixes = [
            r'\s+corporation$',
            r'\s+incorporated$',
            r'\s+company$',
            r'\s+corp\.?$',
            r'\s+inc\.?$',
            r'\s+llc\.?$',
            r'\s+ltd\.?$',
            r'\s+co\.?$',
        ]
        
        for suffix in suffixes:
            company_clean = re.sub(suffix, '', company_clean, flags=re.IGNORECASE)
        
        # Remove special characters and spaces
        company_clean = re.sub(r'[^a-z0-9]', '', company_clean)
        
        return f"{company_clean}.com"
    
    def _suggest_country_from_phone(
        self,
        detected_patterns: Dict[str, Dict[str, Any]],
        target_field: str
    ) -> Optional[Suggestion]:
        """Suggest country based on phone number country code."""
        phone_pattern = detected_patterns.get(PatternType.PHONE_COUNTRY)
        
        if not phone_pattern:
            return None
        
        country = phone_pattern.get('value', '')
        confidence = phone_pattern.get('confidence', 0.5)
        
        if not country:
            return None
        
        return Suggestion(
            target_field=target_field,
            suggested_value=country,
            confidence=confidence,
            reasoning=f"Based on your phone number prefix ({phone_pattern.get('phone_prefix', 'detected')})",
            source_patterns=[PatternType.PHONE_COUNTRY],
            prompt_template=f"Is your country {country}?"
        )
    
    def _suggest_region_from_phone(
        self,
        detected_patterns: Dict[str, Dict[str, Any]],
        target_field: str
    ) -> Optional[Suggestion]:
        """Suggest region based on phone number."""
        phone_pattern = detected_patterns.get(PatternType.PHONE_COUNTRY)
        
        if not phone_pattern:
            return None
        
        region = phone_pattern.get('region', '')
        
        if not region:
            return None
        
        return Suggestion(
            target_field=target_field,
            suggested_value=region,
            confidence=phone_pattern.get('confidence', 0.5) * 0.8,  # Lower confidence for region
            reasoning=f"Based on your phone number country ({phone_pattern.get('value', '')})",
            source_patterns=[PatternType.PHONE_COUNTRY],
            prompt_template=f"Is your region {region}?"
        )
    
    def _suggest_first_name(
        self,
        detected_patterns: Dict[str, Dict[str, Any]],
        target_field: str
    ) -> Optional[Suggestion]:
        """Suggest first name from full name pattern."""
        name_pattern = detected_patterns.get(PatternType.NAME_FORMAT)
        
        if not name_pattern or name_pattern.get('value') != 'full_name':
            return None
        
        first_name = name_pattern.get('first_name', '')
        
        if not first_name:
            return None
        
        return Suggestion(
            target_field=target_field,
            suggested_value=first_name,
            confidence=0.90,
            reasoning=f"Extracted from your full name",
            source_patterns=[PatternType.NAME_FORMAT],
            prompt_template=f"Is your first name {first_name}?"
        )
    
    def _suggest_last_name(
        self,
        detected_patterns: Dict[str, Dict[str, Any]],
        target_field: str
    ) -> Optional[Suggestion]:
        """Suggest last name from full name pattern."""
        name_pattern = detected_patterns.get(PatternType.NAME_FORMAT)
        
        if not name_pattern or name_pattern.get('value') != 'full_name':
            return None
        
        last_name = name_pattern.get('last_name', '')
        
        if not last_name:
            return None
        
        return Suggestion(
            target_field=target_field,
            suggested_value=last_name,
            confidence=0.90,
            reasoning=f"Extracted from your full name",
            source_patterns=[PatternType.NAME_FORMAT],
            prompt_template=f"Is your last name {last_name}?"
        )
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def get_cached_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Get all cached patterns."""
        return self._pattern_cache.copy()
    
    def clear_cache(self) -> None:
        """Clear the pattern cache."""
        self._pattern_cache.clear()
    
    def apply_format_consistency(
        self,
        value: str,
        detected_patterns: Dict[str, Dict[str, Any]]
    ) -> str:
        """
        Apply detected formatting patterns to a new value.
        
        Args:
            value: Value to format
            detected_patterns: Detected patterns including capitalization
            
        Returns:
            Formatted value
        """
        cap_pattern = detected_patterns.get(PatternType.CAPITALIZATION)
        
        if not cap_pattern:
            return value
        
        cap_style = cap_pattern.get('value', 'Mixed')
        
        if cap_style == 'UPPER':
            return value.upper()
        elif cap_style == 'lower':
            return value.lower()
        elif cap_style == 'Title Case':
            return value.title()
        
        return value


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'PatternType',
    'Suggestion',
    'SuggestionEngine',
    'PHONE_COUNTRY_CODES',
    'PERSONAL_EMAIL_DOMAINS',
]
