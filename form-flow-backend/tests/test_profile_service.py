"""
Unit Tests for Profile Service

Tests for profile generation, update triggers, word limit enforcement,
caching, and privacy controls.
"""

import pytest
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from services.ai.profile_service import (
    ProfileService,
    get_profile_service,
    MIN_COMPLETION_RATE,
    MIN_QUESTIONS_FOR_PROFILE,
    UPDATE_FORM_INTERVAL,
    UPDATE_DAYS_INTERVAL,
    MAX_PROFILE_WORDS,
)
from services.ai.prompts.profile_prompts import (
    format_questions_and_answers,
    calculate_expected_confidence,
    build_create_prompt,
    build_update_prompt,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def profile_service():
    """Create a ProfileService instance with mocked LLM."""
    service = ProfileService(api_key="test-key")
    return service


@pytest.fixture
def sample_form_data():
    """Sample form responses for testing."""
    return {
        "full_name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "+1-555-123-4567",
        "company": "Tech Startup Inc",
        "job_title": "Software Engineer",
        "experience_years": "5",
        "skills": "Python, JavaScript, Machine Learning",
        "education": "BS Computer Science",
    }


@pytest.fixture
def mock_user_profile():
    """Mock UserProfile for testing updates."""
    profile = MagicMock()
    profile.user_id = 1
    profile.profile_text = "Existing profile text with behavioral insights."
    profile.confidence_score = 0.5
    profile.form_count = 2
    profile.version = 1
    profile.updated_at = datetime.now(timezone.utc) - timedelta(days=10)
    profile.metadata_json = json.dumps({"forms_analyzed": ["General"]})
    profile.to_dict = MagicMock(return_value={
        "user_id": 1,
        "profile_text": profile.profile_text,
        "confidence_score": 0.5,
        "confidence_level": "Medium",
        "form_count": 2,
        "version": 1,
    })
    return profile


# =============================================================================
# Prompt Helper Tests
# =============================================================================

class TestPromptHelpers:
    """Tests for prompt formatting helpers."""
    
    def test_format_questions_and_answers(self, sample_form_data):
        """Test formatting form data for prompts."""
        formatted = format_questions_and_answers(sample_form_data)
        
        assert "full_name" in formatted
        assert "John Doe" in formatted
        assert "1." in formatted  # Should have numbered list
    
    def test_format_questions_and_answers_empty(self):
        """Test formatting with empty data."""
        formatted = format_questions_and_answers({})
        assert formatted == "No responses provided."
    
    def test_format_questions_and_answers_filters_empty(self):
        """Test that empty values are filtered out."""
        data = {"name": "John", "empty_field": "", "null_field": None}
        formatted = format_questions_and_answers(data)
        
        assert "name" in formatted
        assert "empty_field" not in formatted
        assert "null_field" not in formatted
    
    def test_calculate_expected_confidence_high(self):
        """Test high confidence calculation."""
        confidence = calculate_expected_confidence(form_count=5, question_count=10)
        assert "High" in confidence
    
    def test_calculate_expected_confidence_medium(self):
        """Test medium confidence calculation."""
        confidence = calculate_expected_confidence(form_count=2, question_count=8)
        assert "Medium" in confidence
    
    def test_calculate_expected_confidence_low(self):
        """Test low confidence calculation."""
        confidence = calculate_expected_confidence(form_count=1, question_count=3)
        assert "Low" in confidence
    
    def test_build_create_prompt(self, sample_form_data):
        """Test create prompt building."""
        prompt = build_create_prompt(sample_form_data, "Application", "Job Application")
        
        assert "CREATE" in prompt
        assert "Application" in prompt
        assert "Job Application" in prompt
        assert "John Doe" in prompt
    
    def test_build_update_prompt(self, sample_form_data):
        """Test update prompt building."""
        existing = "Existing profile text."
        prompt = build_update_prompt(existing, sample_form_data, 2, "Survey", "Feedback")
        
        assert "UPDATE" in prompt
        assert "70/30 rule" in prompt
        assert "Existing profile text" in prompt
        assert "2" in prompt  # previous form count


# =============================================================================
# Smart Trigger Tests
# =============================================================================

class TestSmartTriggers:
    """Tests for profile update trigger logic."""
    
    def test_trigger_new_user(self, profile_service, sample_form_data):
        """New user should always trigger profile creation."""
        result = profile_service.should_update_profile(
            form_data=sample_form_data,
            user_profile=None,
            total_questions=10
        )
        assert result is True
    
    def test_trigger_too_few_questions(self, profile_service):
        """Should not trigger with too few questions."""
        form_data = {"name": "John", "email": "john@test.com"}  # Only 2 answers
        
        result = profile_service.should_update_profile(
            form_data=form_data,
            user_profile=None,
            total_questions=2
        )
        assert result is False
    
    def test_trigger_low_completion_rate(self, profile_service, sample_form_data):
        """Should not trigger with low completion rate."""
        result = profile_service.should_update_profile(
            form_data=sample_form_data,  # 8 answers
            user_profile=None,
            total_questions=20  # 8/20 = 40% completion
        )
        assert result is False
    
    def test_trigger_form_count_interval(self, profile_service, sample_form_data, mock_user_profile):
        """Should trigger every N forms."""
        # Form count = 3, which is divisible by UPDATE_FORM_INTERVAL (3)
        mock_user_profile.form_count = 3
        
        result = profile_service.should_update_profile(
            form_data=sample_form_data,
            user_profile=mock_user_profile,
            total_questions=10
        )
        assert result is True
    
    def test_trigger_stale_profile(self, profile_service, sample_form_data, mock_user_profile):
        """Should trigger if profile is stale (30+ days)."""
        mock_user_profile.form_count = 2  # Not interval
        mock_user_profile.updated_at = datetime.now(timezone.utc) - timedelta(days=35)
        
        result = profile_service.should_update_profile(
            form_data=sample_form_data,
            user_profile=mock_user_profile,
            total_questions=10
        )
        assert result is True
    
    def test_no_trigger_recent_profile(self, profile_service, sample_form_data, mock_user_profile):
        """Should not trigger for recent, non-interval profile."""
        mock_user_profile.form_count = 2  # Not interval (3)
        mock_user_profile.updated_at = datetime.now(timezone.utc) - timedelta(days=5)  # Recent
        
        result = profile_service.should_update_profile(
            form_data=sample_form_data,
            user_profile=mock_user_profile,
            total_questions=10
        )
        assert result is False


# =============================================================================
# Confidence Calculation Tests
# =============================================================================

class TestConfidenceCalculation:
    """Tests for confidence score calculation."""
    
    def test_confidence_new_user(self, profile_service):
        """New user with few questions = low confidence."""
        confidence = profile_service._calculate_confidence(form_count=1, question_count=5)
        assert confidence < 0.5
    
    def test_confidence_experienced_user(self, profile_service):
        """Experienced user with many questions = high confidence."""
        confidence = profile_service._calculate_confidence(form_count=5, question_count=15)
        assert confidence >= 0.8
    
    def test_confidence_capped_at_one(self, profile_service):
        """Confidence should never exceed 1.0."""
        confidence = profile_service._calculate_confidence(form_count=100, question_count=100)
        assert confidence <= 1.0


# =============================================================================
# Word Limit Tests
# =============================================================================

class TestWordLimitEnforcement:
    """Tests for 500-word limit enforcement."""
    
    @pytest.mark.asyncio
    async def test_short_profile_unchanged(self, profile_service):
        """Profile under 500 words should be unchanged."""
        short_text = "This is a short profile. " * 50  # ~250 words
        
        with patch.object(profile_service, '_call_llm', new_callable=AsyncMock) as mock_llm:
            result = await profile_service._enforce_word_limit(short_text)
            
            assert result == short_text
            mock_llm.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_long_profile_condensed(self, profile_service):
        """Profile over 500 words should be condensed."""
        long_text = "This is a long profile text. " * 200  # ~1000 words
        condensed = "Condensed profile text under 500 words."
        
        with patch.object(profile_service, '_call_llm', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = condensed
            result = await profile_service._enforce_word_limit(long_text)
            
            assert result == condensed
            mock_llm.assert_called_once()


# =============================================================================
# Privacy Control Tests
# =============================================================================

class TestPrivacyControls:
    """Tests for privacy-related functionality."""
    
    @pytest.mark.asyncio
    async def test_profiling_disabled_user(self, profile_service, sample_form_data):
        """Should skip generation for users who opted out."""
        mock_db = AsyncMock()
        mock_user = MagicMock()
        mock_user.profiling_enabled = False
        mock_db.get = AsyncMock(return_value=mock_user)
        
        result = await profile_service.generate_profile(
            db=mock_db,
            user_id=1,
            form_data=sample_form_data
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_profile(self, profile_service, mock_user_profile):
        """Should delete profile and invalidate cache."""
        mock_db = AsyncMock()
        
        with patch.object(profile_service, '_get_profile_from_db', new_callable=AsyncMock) as mock_get:
            with patch.object(profile_service, 'invalidate_cache', new_callable=AsyncMock) as mock_cache:
                mock_get.return_value = mock_user_profile
                
                result = await profile_service.delete_profile(mock_db, user_id=1)
                
                assert result is True
                mock_db.delete.assert_called_once_with(mock_user_profile)
                mock_cache.assert_called_once_with(1)
    
    @pytest.mark.asyncio
    async def test_delete_profile_not_found(self, profile_service):
        """Should return False if profile doesn't exist."""
        mock_db = AsyncMock()
        
        with patch.object(profile_service, '_get_profile_from_db', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            
            result = await profile_service.delete_profile(mock_db, user_id=1)
            
            assert result is False


# =============================================================================
# Caching Tests
# =============================================================================

class TestCaching:
    """Tests for profile caching functionality."""
    
    @pytest.mark.asyncio
    async def test_get_cached_profile(self, profile_service, mock_user_profile):
        """Should return cached profile when available."""
        with patch('services.ai.profile_service.get_cached', new_callable=AsyncMock) as mock_cache:
            mock_cache.return_value = mock_user_profile.to_dict()
            
            result = await profile_service.get_cached_profile(user_id=1)
            
            assert result is not None
            assert result["user_id"] == 1
            mock_cache.assert_called_once_with("profile:1")
    
    @pytest.mark.asyncio
    async def test_cache_profile(self, profile_service, mock_user_profile):
        """Should cache profile with correct keys."""
        with patch('services.ai.profile_service.set_cached', new_callable=AsyncMock) as mock_set:
            await profile_service._cache_profile(user_id=1, profile=mock_user_profile)
            
            # Should set both profile and ready flag
            assert mock_set.call_count == 2


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for complete flows."""
    
    def test_singleton_instance(self):
        """get_profile_service should return singleton."""
        service1 = get_profile_service()
        service2 = get_profile_service()
        
        assert service1 is service2
