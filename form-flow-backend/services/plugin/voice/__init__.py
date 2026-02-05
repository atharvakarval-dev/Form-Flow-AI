"""
Plugin Voice Collection Package

Provides voice data collection for plugins:
- PluginSessionManager: Session state with timeout and cleanup
- PluginExtractor: Multi-field extraction with confidence
- ValidationEngine: Extensible validation rules

All components follow DRY principles and reuse existing infrastructure.
"""

from services.plugin.voice.session_manager import (
    PluginSessionManager,
    PluginSessionData,
    SessionState,
    get_plugin_session_manager,
)
from services.plugin.voice.extractor import (
    PluginExtractor,
    ExtractionResult,
    BatchExtractionResult,
    get_plugin_extractor,
)
from services.plugin.voice.validation import (
    ValidationEngine,
    ValidationResult,
    ValidationError,
    Validator,
    get_validation_engine,
)

__all__ = [
    # Session Manager
    "PluginSessionManager",
    "PluginSessionData",
    "SessionState",
    "get_plugin_session_manager",
    # Extractor
    "PluginExtractor",
    "ExtractionResult",
    "BatchExtractionResult",
    "get_plugin_extractor",
    # Validation
    "ValidationEngine",
    "ValidationResult",
    "ValidationError",
    "Validator",
    "get_validation_engine",
]
