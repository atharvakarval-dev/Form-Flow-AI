"""
FastAPI Dependencies Module

Provides dependency injection for services and shared state.
All service instances are singletons to reuse connections/resources.

Usage:
    from core.dependencies import get_voice_processor, get_speech_service
    
    @router.post("/process")
    async def process(
        voice_processor: VoiceProcessor = Depends(get_voice_processor)
    ):
        ...
"""

from typing import Optional, Dict, Any
from functools import lru_cache

from config.settings import settings
from utils.logging import get_logger

# Lazy imports to avoid circular dependencies
_voice_processor = None
_speech_service = None
_form_submitter = None
_gemini_service = None
_vosk_service = None

logger = get_logger(__name__)


# =============================================================================
# Service Initialization
# =============================================================================

def _initialize_services() -> None:
    """
    Initialize all service singletons.
    
    Called lazily on first access to any service.
    Logs warnings if required API keys are missing.
    """
    global _voice_processor, _speech_service, _form_submitter, _gemini_service, _vosk_service
    
    from services.ai.gemini import GeminiService
    from services.voice.processor import VoiceProcessor
    from services.voice.speech import SpeechService
    from services.voice.vosk import VoskService
    from services.form.submitter import FormSubmitter
    
    # Log API key status
    if not settings.GOOGLE_API_KEY:
        logger.warning("GOOGLE_API_KEY not configured - Gemini AI features disabled")
    if not settings.ELEVENLABS_API_KEY:
        logger.warning("ELEVENLABS_API_KEY not configured - Text-to-speech disabled")
    
    # Initialize services
    _voice_processor = VoiceProcessor(
        openai_key=settings.OPENAI_API_KEY,
        gemini_key=settings.GOOGLE_API_KEY
    )
    
    _speech_service = SpeechService(api_key=settings.ELEVENLABS_API_KEY)
    
    _form_submitter = FormSubmitter()
    
    if settings.GOOGLE_API_KEY:
        try:
            _gemini_service = GeminiService(api_key=settings.GOOGLE_API_KEY)
        except Exception as e:
            logger.error(f"Failed to initialize Gemini service: {e}")
            _gemini_service = None
    
    _vosk_service = VoskService()
    
    logger.info("Services initialized successfully")


def _ensure_initialized() -> None:
    """Ensure services are initialized."""
    global _voice_processor
    if _voice_processor is None:
        _initialize_services()


# =============================================================================
# Service Providers
# =============================================================================

def get_voice_processor():
    """
    Get VoiceProcessor singleton for voice input processing.
    
    Returns:
        VoiceProcessor: Configured voice processor instance
    """
    _ensure_initialized()
    return _voice_processor


def get_speech_service():
    """
    Get SpeechService singleton for text-to-speech.
    
    Returns:
        SpeechService: Configured ElevenLabs TTS service
    """
    _ensure_initialized()
    return _speech_service


def get_form_submitter():
    """
    Get FormSubmitter singleton for form automation.
    
    Returns:
        FormSubmitter: Configured Playwright form submitter
    """
    _ensure_initialized()
    return _form_submitter


def get_gemini_service():
    """
    Get GeminiService singleton for AI features.
    
    Returns:
        Optional[GeminiService]: Gemini service or None if not configured
    """
    _ensure_initialized()
    return _gemini_service


def get_vosk_service():
    """
    Get VoskService singleton for speech-to-text.
    
    Returns:
        VoskService: Configured Vosk STT service
    """
    _ensure_initialized()
    return _vosk_service


# =============================================================================
# Speech Data Cache
# =============================================================================

# Global state for speech data (field prompts with audio)
# In production, consider using Redis or similar
_global_speech_data: Dict[str, Any] = {}


def get_speech_data() -> Dict[str, Any]:
    """
    Get cached speech data dictionary.
    
    Contains pre-generated audio prompts keyed by field name.
    
    Returns:
        dict: Speech data cache
    """
    return _global_speech_data


def update_speech_data(new_data: Dict[str, Any]) -> None:
    """
    Update speech data cache with new entries.
    
    Args:
        new_data: Dictionary of field_name -> speech data
    """
    global _global_speech_data
    _global_speech_data.update(new_data)
    logger.debug(f"Updated speech cache with {len(new_data)} entries")


def clear_speech_data() -> None:
    """Clear all cached speech data."""
    global _global_speech_data
    _global_speech_data.clear()
    logger.debug("Cleared speech cache")
