"""
Plugin Test Package

Test configuration and shared fixtures for plugin tests.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock


# ============================================================================
# Pytest Configuration
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Shared Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock async database session."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    return db


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.exists = AsyncMock(return_value=0)
    redis.setex = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def sample_plugin():
    """Sample plugin model."""
    return MagicMock(
        id=1,
        name="Test Plugin",
        owner_id=1,
        db_type="postgresql",
        connection_config_encrypted="encrypted_config",
        is_active=True,
        api_key_hash="hashed_key",
        tables=[
            {
                "table_name": "customers",
                "fields": [
                    {
                        "column_name": "name",
                        "column_type": "string",
                        "question_text": "What is your name?",
                        "is_required": True
                    },
                    {
                        "column_name": "email",
                        "column_type": "email",
                        "question_text": "What is your email?",
                        "is_required": True
                    }
                ]
            }
        ]
    )


@pytest.fixture
def sample_session():
    """Sample session data."""
    from services.plugin.voice.session_manager import PluginSessionData, SessionState
    from datetime import datetime, timedelta
    
    return PluginSessionData(
        session_id="test_session_123",
        plugin_id=1,
        state=SessionState.ACTIVE,
        pending_fields=["name", "email"],
        completed_fields=[],
        extracted_values={},
        confidence_scores={},
        processed_requests=[],
        created_at=datetime.now(),
        expires_at=datetime.now() + timedelta(minutes=30)
    )


@pytest.fixture
def sample_extraction_result():
    """Sample extraction result."""
    from services.plugin.voice.extractor import ExtractionResult
    
    return {
        "name": ExtractionResult(
            field_name="name",
            value="John Doe",
            confidence=0.95,
            raw_text="my name is John Doe"
        ),
        "email": ExtractionResult(
            field_name="email",
            value="john@example.com",
            confidence=0.92,
            raw_text="email is john@example.com"
        )
    }


# ============================================================================
# Test Utilities
# ============================================================================

def generate_test_api_key():
    """Generate a test API key."""
    import secrets
    return f"ff_test_{secrets.token_hex(16)}"


def create_mock_plugin_service(db=None):
    """Create a mock plugin service."""
    from services.plugin.plugin_service import PluginService
    return PluginService(db or AsyncMock())


def create_mock_session_manager(use_redis=False):
    """Create a mock session manager."""
    from services.plugin.voice.session_manager import PluginSessionManager
    manager = PluginSessionManager()
    manager._use_redis = use_redis
    return manager
