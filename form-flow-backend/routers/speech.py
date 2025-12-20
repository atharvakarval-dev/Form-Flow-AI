"""
Speech Router

Provides endpoints for text-to-speech and speech-to-text operations.

Endpoints:
    GET /speech/{field_name} - Get TTS audio for a form field
    POST /transcribe - Transcribe audio to text using Vosk
"""

from fastapi import APIRouter, HTTPException, Depends, Response, UploadFile, File
from typing import Dict, Any

from services.voice.speech import SpeechService
from services.voice.vosk import VoskService
from core.dependencies import get_speech_service, get_vosk_service, get_speech_data
from utils.logging import get_logger, log_api_call

logger = get_logger(__name__)

router = APIRouter(tags=["Speech & Audio"])


# =============================================================================
# Text-to-Speech
# =============================================================================

@router.get(
    "/speech/{field_name}",
    summary="Get speech audio for form field",
    responses={
        200: {
            "description": "Audio file (MP3)",
            "content": {"audio/mpeg": {}}
        },
        500: {"description": "Speech generation failed"}
    }
)
async def get_field_speech_audio(
    field_name: str,
    speech_service: SpeechService = Depends(get_speech_service),
    speech_data: dict = Depends(get_speech_data)
):
    """
    Get text-to-speech audio for a specific form field.
    
    First checks the speech cache for pre-generated audio.
    If not found, generates audio on-demand using ElevenLabs.
    
    Args:
        field_name: Name of the form field
        
    Returns:
        Response: Audio file as audio/mpeg
        
    Raises:
        HTTPException: 500 if speech generation fails
    """
    try:
        logger.debug(f"Speech requested for field: {field_name}")
        
        # Check cache first
        if field_name in speech_data:
            audio_data = speech_data[field_name].get('audio')
            if audio_data:
                logger.debug(f"Returning cached audio for: {field_name}")
                return Response(content=audio_data, media_type="audio/mpeg")
        
        # Generate on demand if not cached
        logger.info(f"Generating speech on demand for: {field_name}")
        field_info = {'name': field_name, 'type': 'text', 'label': field_name}
        prompt_text = speech_service._create_field_prompt(field_info)
        audio_data = speech_service.text_to_speech(prompt_text)
        
        if audio_data:
            log_api_call("ElevenLabs", "text-to-speech", success=True)
            return Response(content=audio_data, media_type="audio/mpeg")
        else:
            log_api_call("ElevenLabs", "text-to-speech", success=False, error="No audio returned")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate speech - no audio returned"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Speech generation failed for {field_name}: {e}")
        log_api_call("ElevenLabs", "text-to-speech", success=False, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Speech generation failed: {str(e)}"
        )


# =============================================================================
# Speech-to-Text
# =============================================================================

@router.post(
    "/transcribe",
    summary="Transcribe audio to text",
    responses={
        200: {
            "description": "Transcription result",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "transcript": "Hello world",
                        "confidence": 0.95,
                        "provider": "vosk"
                    }
                }
            }
        }
    }
)
async def transcribe_audio(
    audio: UploadFile = File(..., description="Audio file to transcribe (WAV format)"),
    vosk_service: VoskService = Depends(get_vosk_service)
):
    """
    Transcribe audio using local Vosk model (Indian English).
    
    Accepts audio files in WAV or PCM format. Browser WebM format
    may not work directly and requires transcoding.
    
    Args:
        audio: Audio file upload
        
    Returns:
        dict: Transcription result with success flag, transcript, and confidence
        
    Note:
        If Vosk is not available, returns use_browser_fallback=True
        to indicate the client should use browser's Web Speech API.
    """
    try:
        # Check if Vosk is available
        if not vosk_service or not vosk_service.is_available():
            logger.warning("Vosk model not loaded - suggesting browser fallback")
            return {
                "success": False,
                "error": "Vosk model not loaded. Check backend logs.",
                "transcript": "",
                "use_browser_fallback": True
            }
        
        # Read audio data
        audio_data = await audio.read()
        content_type = audio.content_type or "audio/wav"
        
        logger.info(f"Transcribing audio: {len(audio_data)} bytes, type: {content_type}")
        
        # Transcribe using Vosk (16kHz sample rate expected)
        result = vosk_service.transcribe_audio(audio_data, sample_rate=16000)
        
        if result["success"]:
            transcript = result["transcript"]
            logger.info(f"Transcription successful: '{transcript[:50]}...'")
            log_api_call("Vosk", "transcribe", success=True)
            
            return {
                "success": True,
                "transcript": transcript,
                "confidence": result.get("confidence", 1.0),
                "provider": "vosk",
                "words": []
            }
        else:
            error = result.get("error", "Transcription failed")
            logger.warning(f"Vosk transcription failed: {error}")
            log_api_call("Vosk", "transcribe", success=False, error=error)
            
            return {
                "success": False,
                "error": error,
                "transcript": "",
                "use_browser_fallback": True
            }
            
    except Exception as e:
        logger.error(f"Transcription error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "transcript": "",
            "use_browser_fallback": True
        }
