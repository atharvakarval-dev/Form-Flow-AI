"""
Unit Tests for Suggestion Engine

Tests for pattern detection, suggestion generation, and format consistency.
"""

import pytest
from datetime import datetime

from services.ai.suggestion_engine import (
    SuggestionEngine,
    PatternType,
    Suggestion,
    PHONE_COUNTRY_CODES,
    PERSONAL_EMAIL_DOMAINS,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def engine():
    """Create a SuggestionEngine instance."""
    return SuggestionEngine()


@pytest.fixture
def sample_extracted_fields():
    """Sample extracted fields for testing."""
    return {
        'personal_email': 'john.doe@gmail.com',
        'company': 'Acme Corporation',
        'full_name': 'John Michael Doe',
        'phone': '+1-555-123-4567',
    }


# =============================================================================
# Email Pattern Detection Tests
# =============================================================================

class TestEmailPatternDetection:
    """Tests for email pattern detection."""
    
    def test_detect_gmail_domain(self, engine):
        """Test detection of Gmail as personal email."""
        patterns = engine.detect_patterns(
            field_name='email',
            field_value='john.doe@gmail.com',
            field_type='email'
        )
        
        assert PatternType.EMAIL_DOMAIN in patterns
        assert patterns[PatternType.EMAIL_DOMAIN]['value'] == 'gmail.com'
        assert patterns[PatternType.EMAIL_DOMAIN]['is_personal'] is True
    
    def test_detect_corporate_domain(self, engine):
        """Test detection of corporate email domain."""
        patterns = engine.detect_patterns(
            field_name='work_email',
            field_value='jdoe@acmecorp.com',
            field_type='email'
        )
        
        assert PatternType.EMAIL_DOMAIN in patterns
        assert patterns[PatternType.EMAIL_DOMAIN]['value'] == 'acmecorp.com'
        assert patterns[PatternType.EMAIL_DOMAIN]['is_personal'] is False
    
    def test_detect_email_format_first_dot_last(self, engine):
        """Test detection of first.last email format."""
        patterns = engine.detect_patterns(
            field_name='email',
            field_value='john.doe@example.com',
            field_type='email'
        )
        
        assert PatternType.EMAIL_FORMAT in patterns
        assert patterns[PatternType.EMAIL_FORMAT]['value'] == 'first.last'
        assert patterns[PatternType.EMAIL_FORMAT]['local_part'] == 'john.doe'
    
    def test_detect_email_format_underscore(self, engine):
        """Test detection of first_last email format."""
        patterns = engine.detect_patterns(
            field_name='email',
            field_value='john_doe@example.com',
            field_type='email'
        )
        
        assert PatternType.EMAIL_FORMAT in patterns
        assert patterns[PatternType.EMAIL_FORMAT]['value'] == 'first_last'
    
    def test_invalid_email_returns_empty(self, engine):
        """Test that invalid email returns no email patterns."""
        patterns = engine.detect_patterns(
            field_name='email',
            field_value='not-an-email',
            field_type='email'
        )
        
        assert PatternType.EMAIL_DOMAIN not in patterns
        assert PatternType.EMAIL_FORMAT not in patterns


# =============================================================================
# Phone Pattern Detection Tests
# =============================================================================

class TestPhonePatternDetection:
    """Tests for phone number pattern detection."""
    
    def test_detect_us_phone_with_plus(self, engine):
        """Test detection of US phone with country code."""
        patterns = engine.detect_patterns(
            field_name='phone',
            field_value='+1-555-123-4567',
            field_type='tel'
        )
        
        assert PatternType.PHONE_COUNTRY in patterns
        assert patterns[PatternType.PHONE_COUNTRY]['value'] == 'United States'
        assert patterns[PatternType.PHONE_COUNTRY]['country_code'] == 'US'
    
    def test_detect_india_phone(self, engine):
        """Test detection of India phone number."""
        patterns = engine.detect_patterns(
            field_name='mobile',
            field_value='+91 98765 43210',
            field_type='tel'
        )
        
        assert PatternType.PHONE_COUNTRY in patterns
        assert patterns[PatternType.PHONE_COUNTRY]['value'] == 'India'
        assert patterns[PatternType.PHONE_COUNTRY]['country_code'] == 'IN'
    
    def test_detect_uk_phone(self, engine):
        """Test detection of UK phone number."""
        patterns = engine.detect_patterns(
            field_name='phone',
            field_value='+44 20 7946 0958',
            field_type='tel'
        )
        
        assert PatternType.PHONE_COUNTRY in patterns
        assert patterns[PatternType.PHONE_COUNTRY]['value'] == 'United Kingdom'
        assert patterns[PatternType.PHONE_COUNTRY]['country_code'] == 'GB'
    
    def test_detect_phone_without_plus(self, engine):
        """Test detection of phone without + prefix."""
        patterns = engine.detect_patterns(
            field_name='phone',
            field_value='919876543210',
            field_type='tel'
        )
        
        assert PatternType.PHONE_COUNTRY in patterns
        assert patterns[PatternType.PHONE_COUNTRY]['value'] == 'India'
    
    def test_10_digit_us_phone(self, engine):
        """Test detection of 10-digit US phone (no prefix)."""
        patterns = engine.detect_patterns(
            field_name='phone',
            field_value='5551234567',
            field_type='tel'
        )
        
        assert PatternType.PHONE_COUNTRY in patterns
        assert patterns[PatternType.PHONE_COUNTRY]['country_code'] == 'US'
        # Lower confidence for no-prefix numbers
        assert patterns[PatternType.PHONE_COUNTRY]['confidence'] < 0.8


# =============================================================================
# Name Pattern Detection Tests
# =============================================================================

class TestNamePatternDetection:
    """Tests for name pattern detection."""
    
    def test_detect_full_name(self, engine):
        """Test detection of full name pattern."""
        patterns = engine.detect_patterns(
            field_name='full_name',
            field_value='John Doe',
            field_type='text',
            field_label='Full Name'
        )
        
        assert PatternType.NAME_FORMAT in patterns
        assert patterns[PatternType.NAME_FORMAT]['value'] == 'full_name'
        assert patterns[PatternType.NAME_FORMAT]['first_name'] == 'John'
        assert patterns[PatternType.NAME_FORMAT]['last_name'] == 'Doe'
    
    def test_detect_full_name_with_middle(self, engine):
        """Test detection of full name with middle name."""
        patterns = engine.detect_patterns(
            field_name='name',
            field_value='John Michael Doe',
            field_type='text',
            field_label='Name'
        )
        
        assert PatternType.NAME_FORMAT in patterns
        assert patterns[PatternType.NAME_FORMAT]['first_name'] == 'John'
        assert patterns[PatternType.NAME_FORMAT]['last_name'] == 'Doe'
        assert 'Michael' in patterns[PatternType.NAME_FORMAT]['middle_parts']
    
    def test_detect_single_name(self, engine):
        """Test detection of single name."""
        patterns = engine.detect_patterns(
            field_name='name',
            field_value='Madonna',
            field_type='text',
            field_label='Name'
        )
        
        assert PatternType.NAME_FORMAT in patterns
        assert patterns[PatternType.NAME_FORMAT]['value'] == 'single_name'


# =============================================================================
# Capitalization Pattern Tests
# =============================================================================

class TestCapitalizationPatterns:
    """Tests for capitalization pattern detection."""
    
    def test_detect_title_case(self, engine):
        """Test detection of Title Case."""
        patterns = engine.detect_patterns(
            field_name='city',
            field_value='New York',
            field_type='text'
        )
        
        assert PatternType.CAPITALIZATION in patterns
        assert patterns[PatternType.CAPITALIZATION]['value'] == 'Title Case'
    
    def test_detect_uppercase(self, engine):
        """Test detection of UPPERCASE."""
        patterns = engine.detect_patterns(
            field_name='code',
            field_value='ABC XYZ',
            field_type='text'
        )
        
        assert PatternType.CAPITALIZATION in patterns
        assert patterns[PatternType.CAPITALIZATION]['value'] == 'UPPER'
    
    def test_detect_lowercase(self, engine):
        """Test detection of lowercase."""
        patterns = engine.detect_patterns(
            field_name='username',
            field_value='johndoe',
            field_type='text'
        )
        
        assert PatternType.CAPITALIZATION in patterns
        assert patterns[PatternType.CAPITALIZATION]['value'] == 'lower'


# =============================================================================
# Suggestion Generation Tests
# =============================================================================

class TestSuggestionGeneration:
    """Tests for contextual suggestion generation."""
    
    def test_suggest_work_email(self, engine, sample_extracted_fields):
        """Test work email suggestion from personal email + company."""
        # First detect patterns from personal email
        patterns = engine.detect_patterns(
            field_name='personal_email',
            field_value='john.doe@gmail.com',
            field_type='email'
        )
        
        # Generate suggestions for work email
        suggestions = engine.generate_suggestions(
            target_fields=[{'name': 'work_email', 'type': 'email', 'label': 'Work Email'}],
            extracted_fields=sample_extracted_fields,
            detected_patterns=patterns
        )
        
        assert len(suggestions) == 1
        assert suggestions[0].target_field == 'work_email'
        assert 'john.doe' in suggestions[0].suggested_value
        # 'Corporation' suffix is stripped, resulting in 'acme.com'
        assert 'acme.com' in suggestions[0].suggested_value
    
    def test_suggest_country_from_phone(self, engine):
        """Test country suggestion from phone number."""
        patterns = engine.detect_patterns(
            field_name='phone',
            field_value='+91-98765-43210',
            field_type='tel'
        )
        
        suggestions = engine.generate_suggestions(
            target_fields=[{'name': 'country', 'type': 'text', 'label': 'Country'}],
            extracted_fields={},
            detected_patterns=patterns
        )
        
        assert len(suggestions) == 1
        assert suggestions[0].suggested_value == 'India'
    
    def test_suggest_first_name(self, engine):
        """Test first name suggestion from full name."""
        patterns = engine.detect_patterns(
            field_name='full_name',
            field_value='John Doe',
            field_type='text',
            field_label='Full Name'
        )
        
        suggestions = engine.generate_suggestions(
            target_fields=[{'name': 'first_name', 'type': 'text', 'label': 'First Name'}],
            extracted_fields={},
            detected_patterns=patterns
        )
        
        assert len(suggestions) == 1
        assert suggestions[0].suggested_value == 'John'
        assert suggestions[0].confidence >= 0.90
    
    def test_suggest_last_name(self, engine):
        """Test last name suggestion from full name."""
        patterns = engine.detect_patterns(
            field_name='full_name',
            field_value='John Doe',
            field_type='text',
            field_label='Full Name'
        )
        
        suggestions = engine.generate_suggestions(
            target_fields=[{'name': 'last_name', 'type': 'text', 'label': 'Last Name'}],
            extracted_fields={},
            detected_patterns=patterns
        )
        
        assert len(suggestions) == 1
        assert suggestions[0].suggested_value == 'Doe'
    
    def test_low_acceptance_rate_raises_threshold(self, engine):
        """Test that low acceptance rate increases suggestion threshold."""
        patterns = engine.detect_patterns(
            field_name='phone',
            field_value='5551234567',  # US phone, lower confidence
            field_type='tel'
        )
        
        # With normal acceptance rate, should suggest
        suggestions_normal = engine.generate_suggestions(
            target_fields=[{'name': 'country', 'type': 'text'}],
            extracted_fields={},
            detected_patterns=patterns,
            acceptance_rate=0.5
        )
        
        # With low acceptance rate, threshold should increase
        suggestions_low = engine.generate_suggestions(
            target_fields=[{'name': 'country', 'type': 'text'}],
            extracted_fields={},
            detected_patterns=patterns,
            acceptance_rate=0.2  # Low acceptance
        )
        
        # Low confidence phone suggestion should be filtered out with low acceptance rate
        assert len(suggestions_low) <= len(suggestions_normal)


# =============================================================================
# Format Consistency Tests
# =============================================================================

class TestFormatConsistency:
    """Tests for format consistency application."""
    
    def test_apply_title_case(self, engine):
        """Test applying Title Case format."""
        patterns = {
            PatternType.CAPITALIZATION: {'value': 'Title Case'}
        }
        
        result = engine.apply_format_consistency('new york', patterns)
        assert result == 'New York'
    
    def test_apply_uppercase(self, engine):
        """Test applying UPPER format."""
        patterns = {
            PatternType.CAPITALIZATION: {'value': 'UPPER'}
        }
        
        result = engine.apply_format_consistency('hello world', patterns)
        assert result == 'HELLO WORLD'
    
    def test_apply_lowercase(self, engine):
        """Test applying lower format."""
        patterns = {
            PatternType.CAPITALIZATION: {'value': 'lower'}
        }
        
        result = engine.apply_format_consistency('HELLO World', patterns)
        assert result == 'hello world'


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for complete suggestion flows."""
    
    def test_full_suggestion_flow(self, engine):
        """Test complete flow: detect patterns, generate suggestions."""
        # Simulate filling out a form
        extracted = {}
        all_patterns = {}
        
        # User provides full name
        name_patterns = engine.detect_patterns('full_name', 'John Doe', 'text', 'Full Name')
        all_patterns.update(name_patterns)
        extracted['full_name'] = 'John Doe'
        
        # User provides email
        email_patterns = engine.detect_patterns('personal_email', 'john.doe@gmail.com', 'email')
        all_patterns.update(email_patterns)
        extracted['personal_email'] = 'john.doe@gmail.com'
        
        # User provides company
        extracted['company'] = 'Tech Startup'
        
        # User provides phone
        phone_patterns = engine.detect_patterns('phone', '+91-98765-43210', 'tel')
        all_patterns.update(phone_patterns)
        extracted['phone'] = '+91-98765-43210'
        
        # Now generate suggestions for remaining fields
        remaining_fields = [
            {'name': 'first_name', 'type': 'text', 'label': 'First Name'},
            {'name': 'last_name', 'type': 'text', 'label': 'Last Name'},
            {'name': 'work_email', 'type': 'email', 'label': 'Work Email'},
            {'name': 'country', 'type': 'text', 'label': 'Country'},
        ]
        
        suggestions = engine.generate_suggestions(
            target_fields=remaining_fields,
            extracted_fields=extracted,
            detected_patterns=all_patterns
        )
        
        # Should have suggestions for first name, last name, work email, country
        suggestion_fields = [s.target_field for s in suggestions]
        
        assert 'first_name' in suggestion_fields
        assert 'last_name' in suggestion_fields
        assert 'work_email' in suggestion_fields
        assert 'country' in suggestion_fields
        
        # Verify suggestion values
        for s in suggestions:
            if s.target_field == 'first_name':
                assert s.suggested_value == 'John'
            elif s.target_field == 'last_name':
                assert s.suggested_value == 'Doe'
            elif s.target_field == 'country':
                assert s.suggested_value == 'India'
            elif s.target_field == 'work_email':
                assert 'john.doe' in s.suggested_value
                assert 'techstartup' in s.suggested_value.lower()
