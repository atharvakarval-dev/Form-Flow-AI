"""
Plugin Session Unit Tests

Tests for session management, extraction, and validation.

Run: pytest tests/plugin/test_session.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from services.plugin.voice.session_manager import (
    PluginSessionManager,
    PluginSessionData,
    SessionState
)
from services.plugin.voice.extractor import (
    PluginExtractor,
    ExtractionResult,
    BatchExtractionResult
)
from services.plugin.voice.validation import (
    ValidationEngine,
    ValidationResult,
    ValidationError
)


# ============================================================================
# Session Manager Tests
# ============================================================================

class TestPluginSessionManager:
    """Tests for session manager."""
    
    @pytest.fixture
    def session_manager(self):
        """Create session manager with mocked Redis."""
        manager = PluginSessionManager()
        manager._use_redis = False  # Use local cache
        return manager
    
    @pytest.mark.asyncio
    async def test_create_session(self, session_manager):
        """Should create session with correct initial state."""
        session = await session_manager.create_session(
            session_id="test_123",
            plugin_id=1,
            fields=["name", "email", "phone"]
        )
        
        assert session.session_id == "test_123"
        assert session.plugin_id == 1
        assert session.state == SessionState.ACTIVE
        assert len(session.pending_fields) == 3
        assert len(session.completed_fields) == 0
    
    @pytest.mark.asyncio
    async def test_get_session(self, session_manager):
        """Should retrieve existing session."""
        await session_manager.create_session(
            session_id="get_test",
            plugin_id=1,
            fields=["name"]
        )
        
        session = await session_manager.get_session("get_test")
        
        assert session is not None
        assert session.session_id == "get_test"
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, session_manager):
        """Should return None for missing session."""
        result = await session_manager.get_session("nonexistent")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_session_expiry(self, session_manager):
        """Should detect expired sessions."""
        session = await session_manager.create_session(
            session_id="expiry_test",
            plugin_id=1,
            fields=["name"],
            ttl_minutes=0  # Expire immediately
        )
        
        session.expires_at = datetime.now() - timedelta(minutes=1)
        await session_manager._save_session(session)
        
        result = await session_manager.get_session("expiry_test")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_update_session(self, session_manager):
        """Should update session data."""
        session = await session_manager.create_session(
            session_id="update_test",
            plugin_id=1,
            fields=["name"]
        )
        
        session.extracted_values["name"] = "John"
        session.completed_fields.append("name")
        session.pending_fields.remove("name")
        
        await session_manager.update_session(session)
        
        retrieved = await session_manager.get_session("update_test")
        assert retrieved.extracted_values["name"] == "John"
    
    @pytest.mark.asyncio
    async def test_session_progress(self, session_manager):
        """Should calculate progress correctly."""
        session = await session_manager.create_session(
            session_id="progress_test",
            plugin_id=1,
            fields=["name", "email", "phone", "age"]
        )
        
        # Complete 2 of 4 fields
        session.completed_fields = ["name", "email"]
        session.pending_fields = ["phone", "age"]
        
        progress = session.get_progress()
        
        assert progress["total_fields"] == 4
        assert progress["completed"] == 2
        assert progress["percentage"] == 50.0
    
    @pytest.mark.asyncio
    async def test_idempotency_check(self, session_manager):
        """Should detect duplicate request IDs."""
        session = await session_manager.create_session(
            session_id="idempotency_test",
            plugin_id=1,
            fields=["name"]
        )
        
        # First request
        is_dup1 = await session_manager.check_idempotency(session, "req_001")
        assert is_dup1 is False
        
        await session_manager.mark_request_processed(session, "req_001")
        
        # Same request again
        session = await session_manager.get_session("idempotency_test")
        is_dup2 = await session_manager.check_idempotency(session, "req_001")
        assert is_dup2 is True
    
    @pytest.mark.asyncio
    async def test_complete_session(self, session_manager):
        """Should mark session as completed."""
        session = await session_manager.create_session(
            session_id="complete_test",
            plugin_id=1,
            fields=["name"]
        )
        
        session.extracted_values = {"name": "John"}
        result = await session_manager.complete_session(session)
        
        assert result["session_id"] == "complete_test"
        assert result["extracted_values"]["name"] == "John"
        assert session.state == SessionState.COMPLETED


# ============================================================================
# Extractor Tests
# ============================================================================

class TestPluginExtractor:
    """Tests for field extraction."""
    
    @pytest.fixture
    def extractor(self):
        """Create extractor with mocked LLM."""
        return PluginExtractor(llm_client=MagicMock())
    
    def test_normalize_integer(self, extractor):
        """Should normalize integer values."""
        result = extractor._normalize_value("42", {"column_type": "integer"})
        assert result == 42
        
        result = extractor._normalize_value("1,234", {"column_type": "integer"})
        assert result == 1234
    
    def test_normalize_float(self, extractor):
        """Should normalize float values."""
        result = extractor._normalize_value("3.14", {"column_type": "float"})
        assert result == 3.14
    
    def test_normalize_boolean(self, extractor):
        """Should normalize boolean values."""
        assert extractor._normalize_value("yes", {"column_type": "boolean"}) is True
        assert extractor._normalize_value("true", {"column_type": "boolean"}) is True
        assert extractor._normalize_value("no", {"column_type": "boolean"}) is False
    
    def test_normalize_email(self, extractor):
        """Should normalize email addresses."""
        result = extractor._normalize_value("  John@Example.COM  ", {"column_type": "email"})
        assert result == "john@example.com"
    
    def test_normalize_phone(self, extractor):
        """Should normalize phone numbers."""
        result = extractor._normalize_value("+1 (555) 123-4567", {"column_type": "phone"})
        assert result == "+15551234567"
    
    def test_parse_valid_response(self, extractor):
        """Should parse valid LLM response."""
        response = '{"extracted": {"name": "John"}, "confidence": {"name": 0.95}}'
        fields = [{"column_name": "name", "column_type": "string"}]
        
        result = extractor._parse_extraction_response(response, fields, 100)
        
        assert "name" in result.extracted
        assert result.extracted["name"].value == "John"
        assert result.extracted["name"].confidence == 0.95
    
    def test_parse_invalid_json(self, extractor):
        """Should handle invalid JSON response."""
        response = "not json"
        fields = [{"column_name": "name"}]
        
        result = extractor._parse_extraction_response(response, fields, 50)
        
        assert len(result.extracted) == 0
        assert result.message_to_user is not None
    
    def test_confidence_threshold(self, extractor):
        """Should flag low confidence extractions."""
        result = ExtractionResult(
            field_name="name",
            value="J",
            confidence=0.4
        )
        
        assert result.needs_confirmation is True


# ============================================================================
# Validation Tests
# ============================================================================

class TestValidationEngine:
    """Tests for field validation."""
    
    @pytest.fixture
    def engine(self):
        return ValidationEngine()
    
    def test_required_validation(self, engine):
        """Should validate required fields."""
        errors = engine.validate_field(
            "name",
            None,
            {"is_required": True}
        )
        assert len(errors) == 1
        assert errors[0].rule == "required"
    
    def test_email_validation(self, engine):
        """Should validate email format."""
        # Valid
        errors = engine.validate_field("email", "test@example.com", {"column_type": "email"})
        assert len(errors) == 0
        
        # Invalid
        errors = engine.validate_field("email", "invalid-email", {"column_type": "email"})
        assert len(errors) == 1
    
    def test_phone_validation(self, engine):
        """Should validate phone format."""
        # Valid
        errors = engine.validate_field("phone", "+15551234567", {"column_type": "phone"})
        assert len(errors) == 0
        
        # Invalid (too short)
        errors = engine.validate_field("phone", "123", {"column_type": "phone"})
        assert len(errors) == 1
    
    def test_min_length_validation(self, engine):
        """Should validate minimum length."""
        errors = engine.validate_field(
            "name",
            "Jo",
            {"validation_rules": {"min_length": 3}}
        )
        assert len(errors) == 1
    
    def test_max_value_validation(self, engine):
        """Should validate maximum value."""
        errors = engine.validate_field(
            "age",
            150,
            {"validation_rules": {"max_value": 120}}
        )
        assert len(errors) == 1
    
    def test_regex_validation(self, engine):
        """Should validate regex patterns."""
        errors = engine.validate_field(
            "code",
            "ABCD",
            {"validation_rules": {"regex": {"pattern": r"^\d{4}$", "message": "Must be 4 digits"}}}
        )
        assert len(errors) == 1
    
    def test_enum_validation(self, engine):
        """Should validate enum values."""
        errors = engine.validate_field(
            "status",
            "invalid",
            {"validation_rules": {"enum": {"allowed_values": ["active", "inactive"]}}}
        )
        assert len(errors) == 1
    
    def test_validate_all_fields(self, engine):
        """Should validate all fields and aggregate errors."""
        values = {"name": "", "email": "invalid", "age": 150}
        fields = [
            {"column_name": "name", "is_required": True},
            {"column_name": "email", "column_type": "email"},
            {"column_name": "age", "validation_rules": {"max_value": 120}}
        ]
        
        result = engine.validate_all(values, fields)
        
        assert result.is_valid is False
        assert len(result.errors) == 3


# ============================================================================
# Run configuration
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
