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


# =============================================================================
# AI Auto Edits - Text Refinement
# =============================================================================

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class RefineStyleEnum(str, Enum):
    """Output formatting styles for refined text"""
    default = "default"
    concise = "concise"
    formal = "formal"
    casual = "casual"
    bullet = "bullet"
    paragraph = "paragraph"


class RefineRequest(BaseModel):
    """Request body for text refinement"""
    text: str = Field(..., min_length=1, max_length=10000, description="Raw spoken answer to refine")
    question: str = Field(default="", max_length=500, description="The question that was asked (provides context)")
    field_type: str = Field(default="", max_length=50, description="Type hint: email, phone, name, date, number, etc.")
    style: RefineStyleEnum = Field(default=RefineStyleEnum.default, description="Output style")
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "um yeah so my email is like john dot smith at gmail dot com",
                "question": "What is your email address?",
                "field_type": "email",
                "style": "default"
            }
        }


class RefineResponse(BaseModel):
    """Response from text refinement"""
    success: bool
    original: str
    refined: str
    question: str = ""
    field_type: str = ""
    style: str
    changes_made: List[str] = []
    confidence: float = 1.0
    word_count_original: int = 0
    word_count_refined: int = 0
    reduction_percent: float = 0.0


@router.post(
    "/refine",
    summary="AI Auto Edit - Refine raw text",
    response_model=RefineResponse,
    responses={
        200: {
            "description": "Refined text",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "original": "So like um I wanted to say...",
                        "refined": "I wanted to say the project is done and we should launch it soon.",
                        "style": "default",
                        "changes_made": ["Removed filler: 'um'", "Reduced from 20 to 14 words"],
                        "confidence": 0.95,
                        "word_count_original": 20,
                        "word_count_refined": 14,
                        "reduction_percent": 30.0
                    }
                }
            }
        }
    }
)
async def refine_text(request: RefineRequest):
    """
    AI Auto Edit: Transform raw, rambling voice transcripts into clean, polished text.
    
    Features:
    - Removes filler words (um, uh, like, you know)
    - Fixes grammar and punctuation
    - Restructures rambled sentences into clear prose
    - Maintains original meaning and intent
    
    Styles:
    - **default**: Clean, natural prose
    - **concise**: Shortest possible while keeping key information
    - **formal**: Professional, business-appropriate language
    - **casual**: Friendly, conversational tone
    - **bullet**: Format as bullet point list
    - **paragraph**: Well-structured paragraphs
    
    Args:
        request: RefineRequest with text and optional style
        
    Returns:
        RefineResponse with original, refined text, and metadata
    """
    try:
        from services.ai.text_refiner import get_text_refiner, RefineStyle
        
        refiner = get_text_refiner()
        
        # Map request style to enum
        style = RefineStyle(request.style.value)
        
        # Perform refinement with question context
        result = await refiner.refine(
            raw_text=request.text,
            question=request.question,
            style=style,
            field_type=request.field_type
        )
        
        logger.info(f"Text refined: {result.word_count_original} -> {result.word_count_refined} words")
        
        return RefineResponse(
            success=True,
            original=result.original,
            refined=result.refined,
            question=request.question,
            field_type=request.field_type,
            style=result.style.value,
            changes_made=result.changes_made,
            confidence=result.confidence,
            word_count_original=result.word_count_original,
            word_count_refined=result.word_count_refined,
            reduction_percent=result.reduction_percent
        )
        
    except Exception as e:
        logger.error(f"Text refinement failed: {e}", exc_info=True)
        # Return original text on error
        return RefineResponse(
            success=False,
            original=request.text,
            refined=request.text,  # Fallback to original
            question=request.question,
            field_type=request.field_type,
            style=request.style.value,
            changes_made=[f"Error: {str(e)}"],
            confidence=0.0,
            word_count_original=len(request.text.split()),
            word_count_refined=len(request.text.split()),
            reduction_percent=0.0
        )

