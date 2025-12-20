"""
FastAPI Dependencies Module

Provides LAZY dependency injection for services.
Services are only initialized when first requested, reducing memory usage.

Usage:
    from core.dependencies import get_voice_processor, get_speech_service
    
    @router.post("/process")
    async def process(
        voice_processor: VoiceProcessor = Depends(get_voice_processor)
    ):
        ...
"""

from typing import Optional, Dict, Any

from config.settings import settings
from utils.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Lazy Service Singletons (only created when needed)
# =============================================================================

_voice_processor = None
_speech_service = None
_form_submitter = None
_gemini_service = None
_vosk_service = None
_services_initialized = False


def _log_lazy_init(service_name: str) -> None:
    """Log when a service is lazily initialized."""
    logger.info(f"🔧 Lazy initializing: {service_name}")


# =============================================================================
# Lazy Service Providers (initialized on first call)
# =============================================================================

def get_voice_processor():
    """
    Get VoiceProcessor - LAZY loaded on first call.
    """
    global _voice_processor
    
    if _voice_processor is None:
        _log_lazy_init("VoiceProcessor")
        from services.voice.processor import VoiceProcessor
        
        _voice_processor = VoiceProcessor(
            openai_key=settings.OPENAI_API_KEY,
            gemini_key=settings.GOOGLE_API_KEY
        )
    
    return _voice_processor


def get_speech_service():
    """
    Get SpeechService - LAZY loaded on first call.
    """
    global _speech_service
    
    if _speech_service is None:
        _log_lazy_init("SpeechService")
        from services.voice.speech import SpeechService
        
        _speech_service = SpeechService(api_key=settings.ELEVENLABS_API_KEY)
    
    return _speech_service


def get_form_submitter():
    """
    Get FormSubmitter - LAZY loaded on first call.
    
    Note: This is the most memory-intensive service (Playwright).
    Only initialized when user actually submits a form.
    """
    global _form_submitter
    
    if _form_submitter is None:
        _log_lazy_init("FormSubmitter")
        from services.form.submitter import FormSubmitter
        
        _form_submitter = FormSubmitter()
    
    return _form_submitter


def get_gemini_service():
    """
    Get GeminiService - LAZY loaded on first call.
    """
    global _gemini_service
    
    if _gemini_service is None:
        if settings.GOOGLE_API_KEY:
            _log_lazy_init("GeminiService")
            try:
                from services.ai.gemini import GeminiService
                _gemini_service = GeminiService(api_key=settings.GOOGLE_API_KEY)
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
                return None
        else:
            logger.warning("GOOGLE_API_KEY not configured")
            return None
    
    return _gemini_service


def get_vosk_service():
    """
    Get VoskService - LAZY loaded on first transcription request.
    
    Note: Vosk model loading is memory-intensive (~50-100MB).
    Only load when user actually uses speech-to-text.
    """
    global _vosk_service
    
    if _vosk_service is None:
        _log_lazy_init("VoskService (this may take a moment...)")
        from services.voice.vosk import VoskService
        
        _vosk_service = VoskService()
    
    return _vosk_service


# =============================================================================
# Speech Data Cache (now uses Redis when available)
# =============================================================================

_global_speech_data: Dict[str, Any] = {}


def get_speech_data() -> Dict[str, Any]:
    """Get speech data cache."""
    return _global_speech_data


def update_speech_data(new_data: Dict[str, Any]) -> None:
    """Update speech data cache."""
    global _global_speech_data
    _global_speech_data.update(new_data)


def clear_speech_data() -> None:
    """Clear speech data cache."""
    global _global_speech_data
    _global_speech_data.clear()


# =============================================================================
# Health Check
# =============================================================================

def get_initialized_services() -> Dict[str, bool]:
    """Get status of which services have been initialized."""
    return {
        "voice_processor": _voice_processor is not None,
        "speech_service": _speech_service is not None,
        "form_submitter": _form_submitter is not None,
        "gemini_service": _gemini_service is not None,
        "vosk_service": _vosk_service is not None,
    }
