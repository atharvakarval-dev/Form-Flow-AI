# AI services module - Unified exports

from .gemini import GeminiService
from .conversation_agent import ConversationAgent, FieldClusterer
from .session_manager import SessionManager, get_session_manager
from .text_refiner import TextRefiner, get_text_refiner, RefineStyle, RefinedText
from .smart_autofill import SmartAutofill, get_smart_autofill
from .analytics import FormAnalytics, get_form_analytics
from .multilingual import MultilingualProcessor, get_multilingual_processor, Language
from .profile_service import ProfileService, get_profile_service, generate_profile_background
from .profile_suggestions import (
    ProfileSuggestionEngine,
    get_profile_suggestion_engine,
    get_intelligent_suggestions,
    IntelligentSuggestion,
    SuggestionTier,
)

__all__ = [
    # Gemini
    "GeminiService",
    # Conversation
    "ConversationAgent",
    "FieldClusterer",
    # Session
    "SessionManager",
    "get_session_manager",
    # Text Refinement
    "TextRefiner",
    "get_text_refiner",
    "RefineStyle",
    "RefinedText",
    # Smart Autofill
    "SmartAutofill",
    "get_smart_autofill",
    # Analytics
    "FormAnalytics",
    "get_form_analytics",
    # Multilingual
    "MultilingualProcessor",
    "get_multilingual_processor",
    "Language",
    # Profile Service
    "ProfileService",
    "get_profile_service",
    "generate_profile_background",
    # Intelligent Suggestions
    "ProfileSuggestionEngine",
    "get_profile_suggestion_engine",
    "get_intelligent_suggestions",
    "IntelligentSuggestion",
    "SuggestionTier",
]


