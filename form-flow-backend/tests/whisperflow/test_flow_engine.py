"""
Unit Tests for WhisperFlow - Flow Engine

Tests for FlowEngine, snippet expansion, self-correction handling,
action detection, and smart formatting.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from dataclasses import asdict

from services.ai.flow_engine import (
    FlowEngine,
    FlowEngineResult,
    ActionPayload,
    get_flow_engine,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_db():
    """Create mock database session."""
    return Mock()


@pytest.fixture
def mock_user():
    """Create mock user."""
    user = Mock()
    user.id = 1
    return user


@pytest.fixture
def flow_engine(mock_db, mock_user):
    """Create FlowEngine instance with mocked dependencies."""
    with patch('services.ai.flow_engine.settings') as mock_settings:
        mock_settings.GEMMA_API_KEY = None
        mock_settings.GOOGLE_API_KEY = None  # Disable LLM for rule-based tests
        engine = FlowEngine(db=mock_db, user=mock_user)
        return engine


# =============================================================================
# FlowEngineResult Tests
# =============================================================================

class TestFlowEngineResult:
    """Tests for FlowEngineResult dataclass."""
    
    def test_default_values(self):
        """Test default values are set correctly."""
        result = FlowEngineResult(display_text="Hello", intent="typing")
        assert result.display_text == "Hello"
        assert result.intent == "typing"
        assert result.detected_apps == []
        assert result.actions == []
        assert result.corrections_applied == []
        assert result.snippets_expanded == []
        assert result.confidence == 1.0
    
    def test_with_actions(self):
        """Test result with actions."""
        action = ActionPayload(tool="calendar", action_type="create_event", payload={"title": "Meeting"})
        result = FlowEngineResult(
            display_text="Create meeting",
            intent="command",
            detected_apps=["calendar"],
            actions=[action]
        )
        assert result.intent == "command"
        assert len(result.actions) == 1
        assert result.actions[0].tool == "calendar"


# =============================================================================
# Snippet Expansion Tests
# =============================================================================

class TestSnippetExpansion:
    """Tests for snippet expansion functionality."""
    
    def test_expand_single_snippet(self, flow_engine):
        """Test expanding a single snippet."""
        snippets = {"calendar link": "https://calendly.com/user/30min"}
        text = "Let's meet, here's my calendar link"
        
        result, expanded = flow_engine._expand_snippets(text, snippets)
        
        assert "https://calendly.com/user/30min" in result
        assert "calendar link" in expanded
    
    def test_expand_multiple_snippets(self, flow_engine):
        """Test expanding multiple snippets."""
        snippets = {
            "my email": "user@example.com",
            "my phone": "+1-555-123-4567"
        }
        text = "Contact me at my email or my phone"
        
        result, expanded = flow_engine._expand_snippets(text, snippets)
        
        assert "user@example.com" in result
        assert "+1-555-123-4567" in result
        assert len(expanded) == 2
    
    def test_case_insensitive_expansion(self, flow_engine):
        """Test that snippet expansion is case-insensitive."""
        snippets = {"github": "https://github.com/user"}
        text = "Check my GITHUB profile"
        
        result, expanded = flow_engine._expand_snippets(text, snippets)
        
        assert "https://github.com/user" in result
        assert "github" in expanded
    
    def test_no_snippets_matched(self, flow_engine):
        """Test when no snippets match."""
        snippets = {"calendar link": "https://calendly.com"}
        text = "Hello world"
        
        result, expanded = flow_engine._expand_snippets(text, snippets)
        
        assert result == text
        assert expanded == []


# =============================================================================
# Action Detection Tests (Rule-based)
# =============================================================================

class TestActionDetection:
    """Tests for action detection functionality."""
    
    def test_detect_calendar_action(self, flow_engine):
        """Test detecting calendar-related actions."""
        text = "Schedule a meeting for tomorrow"
        result = flow_engine._process_with_rules(text, [], [])
        
        assert "calendar" in result.detected_apps
        assert result.intent == "command"
    
    def test_detect_jira_action(self, flow_engine):
        """Test detecting Jira-related actions."""
        text = "Create a Jira ticket for the login bug"
        result = flow_engine._process_with_rules(text, [], [])
        
        assert "jira" in result.detected_apps
        assert result.intent == "command"
    
    def test_detect_slack_action(self, flow_engine):
        """Test detecting Slack-related actions."""
        text = "Send a message on Slack to the team"
        result = flow_engine._process_with_rules(text, [], [])
        
        assert "slack" in result.detected_apps
        assert result.intent == "command"
    
    def test_detect_email_action(self, flow_engine):
        """Test detecting email-related actions."""
        text = "Send an email to John"
        result = flow_engine._process_with_rules(text, [], [])
        
        assert "email" in result.detected_apps
        assert result.intent == "command"
    
    def test_detect_multiple_apps(self, flow_engine):
        """Test detecting multiple apps in one utterance."""
        text = "Create a Jira ticket and send an email about it"
        result = flow_engine._process_with_rules(text, [], [])
        
        assert "jira" in result.detected_apps
        assert "email" in result.detected_apps
        assert len(result.detected_apps) == 2
    
    def test_no_action_detected(self, flow_engine):
        """Test when no action is detected."""
        text = "Hello, how are you today?"
        result = flow_engine._process_with_rules(text, [], [])
        
        assert result.detected_apps == []
        assert result.intent == "typing"


# =============================================================================
# Basic Formatting Tests
# =============================================================================

class TestBasicFormatting:
    """Tests for basic text formatting."""
    
    def test_capitalize_first_letter(self, flow_engine):
        """Test that first letter is capitalized."""
        text = "hello world"
        result = flow_engine._apply_basic_formatting(text)
        assert result.startswith("H")
    
    def test_add_period_if_missing(self, flow_engine):
        """Test that period is added if missing."""
        text = "Hello world"
        result = flow_engine._apply_basic_formatting(text)
        assert result.endswith(".")
    
    def test_keep_existing_punctuation(self, flow_engine):
        """Test that existing punctuation is preserved."""
        text = "Hello world!"
        result = flow_engine._apply_basic_formatting(text)
        assert result.endswith("!")
        assert not result.endswith("!.")
    
    def test_capitalize_tech_terms(self, flow_engine):
        """Test that tech terms are properly capitalized."""
        text = "I'm using react and fastapi"
        result = flow_engine._apply_basic_formatting(text)
        assert "React" in result
        assert "FastAPI" in result


# =============================================================================
# Full Pipeline Tests
# =============================================================================

class TestFlowEnginePipeline:
    """Tests for the full Flow Engine pipeline."""
    
    @pytest.mark.asyncio
    async def test_empty_input(self, flow_engine):
        """Test that empty input returns empty result."""
        result = await flow_engine.process("")
        assert result.display_text == ""
        assert result.intent == "typing"
    
    @pytest.mark.asyncio
    async def test_whitespace_input(self, flow_engine):
        """Test that whitespace-only input returns empty result."""
        result = await flow_engine.process("   ")
        assert result.display_text == ""
        assert result.intent == "typing"
    
    @pytest.mark.asyncio
    async def test_simple_text_processing(self, flow_engine, mock_db):
        """Test simple text passes through rule-based processing."""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = await flow_engine.process("hello world")
        
        assert result.display_text == "Hello world."
        assert result.intent == "typing"
    
    @pytest.mark.asyncio
    async def test_action_detection_in_pipeline(self, flow_engine, mock_db):
        """Test action detection works in full pipeline."""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = await flow_engine.process("create a jira ticket for bug fix")
        
        assert "jira" in result.detected_apps
        assert result.intent == "command"


# =============================================================================
# Singleton Tests
# =============================================================================

class TestFlowEngineSingleton:
    """Tests for Flow Engine singleton behavior."""
    
    def test_get_flow_engine_creates_instance(self, mock_db, mock_user):
        """Test that get_flow_engine creates a new instance."""
        with patch('services.ai.flow_engine.settings') as mock_settings:
            mock_settings.GEMMA_API_KEY = None
            mock_settings.GOOGLE_API_KEY = None
            
            # Clear cache first
            from services.ai import flow_engine as fe_module
            fe_module._engine_cache.clear()
            
            engine = get_flow_engine(mock_db, mock_user)
            assert isinstance(engine, FlowEngine)
