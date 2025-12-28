"""
Unit Tests for State Management Classes

Tests for FieldData, FormDataManager, InferenceCache, and ContextWindow.
These classes implement industry-grade state management for form-filling conversations.
"""

import pytest
from datetime import datetime

from services.ai.models.state import (
    FieldStatus,
    ValidationStatus,
    UserIntent,
    FieldData,
    PatternMatch,
    ContextualSuggestion,
    InferenceCache,
    ContextWindow,
    FormDataManager,
)


# =============================================================================
# FieldData Tests
# =============================================================================

class TestFieldData:
    """Tests for FieldData immutable field metadata."""
    
    def test_create_field_data_defaults(self):
        """Test creating a FieldData with default values."""
        field = FieldData()
        
        assert field.value is None
        assert field.status == FieldStatus.EMPTY
        assert field.confidence == 0.0
        assert field.captured_in_turn == 0
        assert field.user_intent == UserIntent.DIRECT_ANSWER
    
    def test_field_data_with_values(self):
        """Test creating FieldData with explicit values."""
        field = FieldData(
            value="John Doe",
            status=FieldStatus.FILLED,
            confidence=0.95,
            captured_in_turn=1,
            user_intent=UserIntent.DIRECT_ANSWER
        )
        
        assert field.value == "John Doe"
        assert field.status == FieldStatus.FILLED
        assert field.confidence == 0.95
        assert field.captured_in_turn == 1
    
    def test_field_data_immutability(self):
        """Test that FieldData is frozen (immutable)."""
        field = FieldData(
            value="test@example.com",
            status=FieldStatus.FILLED,
            confidence=0.9
        )
        
        # Should raise FrozenInstanceError when trying to modify
        with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
            field.value = "new@example.com"
    
    def test_field_data_to_dict(self):
        """Test serialization to dictionary."""
        field = FieldData(
            value="John",
            status=FieldStatus.FILLED,
            confidence=0.85,
            captured_in_turn=2,
            user_intent=UserIntent.CORRECTION
        )
        
        data = field.to_dict()
        
        assert data['value'] == "John"
        assert data['status'] == "filled"
        assert data['confidence'] == 0.85
        assert data['captured_in_turn'] == 2
        assert data['user_intent'] == "correction"
    
    def test_field_data_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            'value': 'test@example.com',
            'status': 'filled',
            'confidence': 0.9,
            'captured_in_turn': 1,
            'user_intent': 'direct_answer',
            'captured_at': '2024-01-01T12:00:00'
        }
        
        field = FieldData.from_dict(data)
        
        assert field.value == 'test@example.com'
        assert field.status == FieldStatus.FILLED
        assert field.confidence == 0.9
    
    def test_field_data_with_value(self):
        """Test creating new FieldData with updated value."""
        field = FieldData(value="old", status=FieldStatus.FILLED, confidence=0.8)
        
        new_field = field.with_value(
            value="new",
            confidence=0.95,
            turn=2,
            intent=UserIntent.DIRECT_ANSWER
        )
        
        assert new_field.value == "new"
        assert new_field.confidence == 0.95
        assert new_field.captured_in_turn == 2
        # Original unchanged
        assert field.value == "old"
    
    def test_field_data_with_skip(self):
        """Test marking field as skipped."""
        field = FieldData(value=None, status=FieldStatus.EMPTY)
        
        skipped = field.with_skip(turn=3)
        
        assert skipped.status == FieldStatus.SKIPPED
        assert skipped.captured_in_turn == 3


# =============================================================================
# FormDataManager Tests
# =============================================================================

class TestFormDataManager:
    """Tests for FormDataManager atomic state mutations."""
    
    def test_create_empty_manager(self):
        """Test creating an empty FormDataManager."""
        manager = FormDataManager()
        
        assert len(manager._fields) == 0
        assert manager.get_filled_fields() == {}
    
    def test_update_field(self):
        """Test atomic field update."""
        manager = FormDataManager()
        
        manager.update_field(
            field_name="email",
            value="test@example.com",
            confidence=0.95,
            turn=1,
            intent=UserIntent.DIRECT_ANSWER
        )
        
        assert "email" in manager._fields
        assert manager._fields["email"].value == "test@example.com"
        assert manager._fields["email"].status == FieldStatus.FILLED
        assert manager._fields["email"].confidence == 0.95
    
    def test_get_filled_fields(self):
        """Test getting all filled field values as dict."""
        manager = FormDataManager()
        manager.update_field("name", "John Doe", 0.9, turn=1)
        manager.update_field("email", "john@example.com", 0.85, turn=2)
        
        values = manager.get_filled_fields()
        
        assert values == {
            "name": "John Doe",
            "email": "john@example.com"
        }
    
    def test_get_confidence_scores(self):
        """Test getting all confidence scores."""
        manager = FormDataManager()
        manager.update_field("name", "John", 0.95, turn=1)
        manager.update_field("email", "john@test.com", 0.80, turn=2)
        
        confidences = manager.get_confidence_scores()
        
        assert confidences["name"] == 0.95
        assert confidences["email"] == 0.80
    
    def test_skip_field(self):
        """Test marking a field as skipped."""
        manager = FormDataManager()
        
        manager.skip_field("phone", turn=3)
        
        assert "phone" in manager._fields
        assert manager._fields["phone"].status == FieldStatus.SKIPPED
    
    def test_get_skipped_field_names(self):
        """Test getting list of skipped field names."""
        manager = FormDataManager()
        manager.update_field("name", "John", 0.9, turn=1)
        manager.skip_field("phone", turn=2)
        manager.skip_field("address", turn=3)
        
        skipped = manager.get_skipped_field_names()
        
        assert "phone" in skipped
        assert "address" in skipped
        assert "name" not in skipped
    
    def test_to_dict_from_dict(self):
        """Test serialization and deserialization."""
        manager = FormDataManager()
        manager.update_field("name", "John Doe", 0.95, turn=1, intent=UserIntent.DIRECT_ANSWER)
        manager.skip_field("phone", turn=2)
        
        data = manager.to_dict()
        restored = FormDataManager.from_dict(data)
        
        assert restored._fields["name"].value == "John Doe"
        assert restored._fields["name"].confidence == 0.95
        assert restored._fields["phone"].status == FieldStatus.SKIPPED


# =============================================================================
# InferenceCache Tests
# =============================================================================

class TestInferenceCache:
    """Tests for InferenceCache pattern storage."""
    
    def test_create_empty_cache(self):
        """Test creating an empty InferenceCache."""
        cache = InferenceCache()
        
        assert cache.detected_patterns == {}
        assert cache.suggestions == {}
    
    def test_add_pattern_match(self):
        """Test adding a PatternMatch object."""
        cache = InferenceCache()
        
        pattern = PatternMatch(
            pattern_type="email_format",
            pattern_value="first.last",
            confidence=0.9,
            source_field="personal_email"
        )
        
        cache.add_pattern(pattern)
        
        # Pattern is stored with key format "type:source_field"
        retrieved = cache.get_pattern("email_format", "personal_email")
        assert retrieved is not None
        assert retrieved.pattern_value == "first.last"
    
    def test_add_suggestion_object(self):
        """Test adding ContextualSuggestion object."""
        cache = InferenceCache()
        
        suggestion = ContextualSuggestion(
            target_field="work_email",
            suggested_value="john@company.com",
            reasoning="Based on email pattern",
            confidence=0.8
        )
        
        cache.add_suggestion(suggestion)
        
        retrieved = cache.get_suggestion("work_email")
        assert retrieved is not None
        assert retrieved.suggested_value == "john@company.com"
    
    def test_cache_serialization(self):
        """Test to_dict and from_dict."""
        cache = InferenceCache()
        
        pattern = PatternMatch(
            pattern_type="phone_country",
            pattern_value="India",
            confidence=0.9,
            source_field="phone"
        )
        cache.add_pattern(pattern)
        
        suggestion = ContextualSuggestion(
            target_field="country",
            suggested_value="India",
            reasoning="From phone prefix",
            confidence=0.9
        )
        cache.add_suggestion(suggestion)
        
        data = cache.to_dict()
        restored = InferenceCache.from_dict(data)
        
        # Check pattern was restored
        assert len(restored.detected_patterns) > 0
        # Check suggestion was restored
        assert "country" in restored.suggestions
    
    def test_suggestion_acceptance_rate(self):
        """Test suggestion acceptance rate calculation."""
        cache = InferenceCache()
        
        # Initially 50% (no data)
        assert cache.suggestion_acceptance_rate == 0.5
        
        # Add some acceptances and rejections
        cache.suggestion_acceptance_count = 3
        cache.suggestion_rejection_count = 1
        
        assert cache.suggestion_acceptance_rate == 0.75


# =============================================================================
# ContextWindow Tests
# =============================================================================

class TestContextWindow:
    """Tests for ContextWindow field navigation tracking."""
    
    def test_create_context_window(self):
        """Test creating a ContextWindow."""
        window = ContextWindow()
        
        assert window.active_field is None
        assert window.previous_field is None
        assert window.next_field is None
        assert window.current_turn == 0
        assert window.current_batch == []
    
    def test_set_active_field(self):
        """Test setting active field properly."""
        window = ContextWindow()
        
        window.set_active_field("email", {"name": "email", "type": "email"})
        
        assert window.active_field == "email"
        assert window.active_field_schema == {"name": "email", "type": "email"}
    
    def test_advance_turn(self):
        """Test turn advancement."""
        window = ContextWindow()
        assert window.current_turn == 0
        
        turn = window.advance_turn()
        assert turn == 1
        assert window.current_turn == 1
        
        turn = window.advance_turn()
        assert turn == 2
    
    def test_mark_field_completed(self):
        """Test marking field as completed."""
        window = ContextWindow()
        window.pending_fields = ["name", "email", "phone"]
        
        window.mark_field_completed("name")
        
        assert "name" in window.completed_fields
        assert "name" not in window.pending_fields
    
    def test_mark_field_skipped(self):
        """Test marking field as skipped."""
        window = ContextWindow()
        window.pending_fields = ["name", "email", "phone"]
        
        window.mark_field_skipped("email")
        
        assert "email" in window.skipped_fields
        assert "email" not in window.pending_fields
    
    def test_context_window_serialization(self):
        """Test to_dict and from_dict."""
        window = ContextWindow()
        window.active_field = "name"
        window.current_turn = 5
        window.current_batch = ["name", "email"]
        window.completed_fields = ["address"]
        
        data = window.to_dict()
        restored = ContextWindow.from_dict(data)
        
        assert restored.active_field == "name"
        assert restored.current_turn == 5
        assert restored.current_batch == ["name", "email"]
        assert restored.completed_fields == ["address"]


# =============================================================================
# Integration Tests
# =============================================================================

class TestStateIntegration:
    """Integration tests for state management workflow."""
    
    def test_complete_form_filling_workflow(self):
        """Test a complete form-filling workflow with all state classes."""
        # Initialize state components
        form_data = FormDataManager()
        inference_cache = InferenceCache()
        context_window = ContextWindow()
        
        # Turn 1: User provides name
        context_window.current_turn = 1
        context_window.active_field = "name"
        context_window.next_field = "email"
        
        form_data.update_field(
            field_name="name",
            value="John Doe",
            confidence=0.95,
            turn=1,
            intent=UserIntent.DIRECT_ANSWER
        )
        
        # Detect patterns
        pattern = PatternMatch(
            pattern_type="name_format",
            pattern_value="full_name",
            confidence=0.9,
            source_field="name"
        )
        inference_cache.add_pattern(pattern)
        
        # Turn 2: User provides email
        context_window.current_turn = 2
        context_window.previous_field = "name"
        context_window.active_field = "email"
        context_window.next_field = "phone"
        
        form_data.update_field(
            field_name="email",
            value="john.doe@gmail.com",
            confidence=0.9,
            turn=2,
            intent=UserIntent.DIRECT_ANSWER
        )
        
        # Turn 3: User skips phone
        context_window.current_turn = 3
        context_window.previous_field = "email"
        context_window.active_field = "phone"
        
        form_data.skip_field("phone", turn=3)
        
        # Verify final state
        values = form_data.get_filled_fields()
        assert values["name"] == "John Doe"
        assert values["email"] == "john.doe@gmail.com"
        assert "phone" not in values  # Skipped fields don't have values
        
        assert "phone" in form_data.get_skipped_field_names()
        assert context_window.current_turn == 3
    
    def test_correction_workflow(self):
        """Test correction intent workflow."""
        form_data = FormDataManager()
        
        # Initial fill
        form_data.update_field("email", "john@example.com", 0.9, turn=1, intent=UserIntent.DIRECT_ANSWER)
        
        # Correction
        form_data.update_field("email", "john.doe@example.com", 0.95, turn=2, intent=UserIntent.CORRECTION)
        
        # Verify only latest value is stored
        assert form_data._fields["email"].value == "john.doe@example.com"
        assert form_data._fields["email"].user_intent == UserIntent.CORRECTION
        assert form_data._fields["email"].captured_in_turn == 2


# =============================================================================
# Validation Scenario Tests
# =============================================================================

class TestValidationScenarios:
    """Tests for validation scenarios from specification."""
    
    def test_skip_only_affects_current_field(self):
        """Verify skip only marks current field, not filled fields."""
        form_data = FormDataManager()
        
        # Fill some fields
        form_data.update_field("name", "John Doe", 0.95, turn=1)
        form_data.update_field("email", "john@example.com", 0.9, turn=2)
        
        # Skip the next field
        form_data.skip_field("phone", turn=3)
        
        # Verify filled fields are untouched
        assert form_data._fields["name"].status == FieldStatus.FILLED
        assert form_data._fields["email"].status == FieldStatus.FILLED
        assert form_data._fields["phone"].status == FieldStatus.SKIPPED
        
        # Values should still be there
        values = form_data.get_filled_fields()
        assert "name" in values
        assert "email" in values
    
    def test_correction_preserves_other_fields(self):
        """Verify correction only updates specified field."""
        form_data = FormDataManager()
        
        # Fill multiple fields
        form_data.update_field("name", "John Doe", 0.95, turn=1)
        form_data.update_field("email", "john@example.com", 0.9, turn=2)
        form_data.update_field("phone", "1234567890", 0.85, turn=3)
        
        # Correct email only
        form_data.update_field("email", "john.doe@gmail.com", 0.95, 
                                turn=4, intent=UserIntent.CORRECTION)
        
        # Verify other fields unchanged
        assert form_data._fields["name"].value == "John Doe"
        assert form_data._fields["name"].captured_in_turn == 1  # Original turn
        assert form_data._fields["phone"].value == "1234567890"
        
        # Email should be updated
        assert form_data._fields["email"].value == "john.doe@gmail.com"
        assert form_data._fields["email"].captured_in_turn == 4  # New turn
    
    def test_confidence_thresholds(self):
        """Test confidence scoring and retrieval."""
        form_data = FormDataManager()
        
        form_data.update_field("high_conf", "value1", 0.95, turn=1)
        form_data.update_field("medium_conf", "value2", 0.75, turn=2)
        form_data.update_field("low_conf", "value3", 0.55, turn=3)
        
        confidences = form_data.get_confidence_scores()
        
        assert confidences["high_conf"] >= 0.9
        assert 0.7 <= confidences["medium_conf"] < 0.9
        assert confidences["low_conf"] < 0.7
