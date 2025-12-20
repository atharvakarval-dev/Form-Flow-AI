"""
Text-to-Speech Service

Provides text-to-speech functionality using ElevenLabs API.
Generates natural-sounding speech prompts for form field questions.

Usage:
    from services.voice.speech import SpeechService
    
    service = SpeechService(api_key="...")
    audio_bytes = service.text_to_speech("Please enter your name")
"""

import os
import requests
from typing import Optional, Dict, Any, Generator

from utils.logging import get_logger, log_api_call
from utils.exceptions import SpeechGenerationError

logger = get_logger(__name__)


class SpeechService:
    """
    ElevenLabs Text-to-Speech service.
    
    Converts text prompts to natural-sounding audio for voice-guided
    form interaction.
    
    Attributes:
        api_key: ElevenLabs API key
        default_voice_id: Default voice to use (Rachel)
        model: TTS model (eleven_turbo_v2_5)
    """
    
    # ElevenLabs API endpoint
    API_BASE = "https://api.elevenlabs.io/v1"
    
    # Default voice settings
    DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel
    DEFAULT_MODEL = "eleven_turbo_v2_5"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        Initialize speech service.
        
        Args:
            api_key: ElevenLabs API key
            voice_id: Voice ID to use (default: Rachel)
            model: TTS model to use (default: eleven_turbo_v2_5)
        """
        self.api_key = api_key
        self.default_voice_id = voice_id or self.DEFAULT_VOICE_ID
        self.model = model or self.DEFAULT_MODEL
        
        if not self.api_key:
            logger.warning("ElevenLabs API key not configured - TTS disabled")
        else:
            logger.info("SpeechService initialized")
    
    def text_to_speech(
        self,
        text: str,
        voice_id: Optional[str] = None
    ) -> Optional[bytes]:
        """
        Convert text to speech audio.
        
        Args:
            text: Text to convert to speech
            voice_id: Optional voice ID override
            
        Returns:
            bytes: Audio data as MP3, or None on failure
            
        Example:
            audio = service.text_to_speech("Please enter your email address")
            if audio:
                with open("prompt.mp3", "wb") as f:
                    f.write(audio)
        """
        if not self.api_key:
            logger.warning("Cannot generate speech - API key not configured")
            return None
        
        target_voice_id = voice_id or self.default_voice_id
        url = f"{self.API_BASE}/text-to-speech/{target_voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        
        data = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        
        try:
            logger.debug(f"Generating speech for: '{text[:50]}...'")
            
            response = requests.post(
                url,
                json=data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.debug(f"Speech generated: {len(response.content)} bytes")
                log_api_call("ElevenLabs", "text-to-speech", success=True)
                return response.content
            else:
                error_msg = f"Status {response.status_code}: {response.text[:200]}"
                logger.error(f"ElevenLabs API error: {error_msg}")
                log_api_call("ElevenLabs", "text-to-speech", success=False, error=error_msg)
                return None
                
        except requests.Timeout:
            logger.error("ElevenLabs API timeout")
            log_api_call("ElevenLabs", "text-to-speech", success=False, error="timeout")
            return None
        except Exception as e:
            logger.error(f"ElevenLabs API exception: {e}")
            log_api_call("ElevenLabs", "text-to-speech", success=False, error=str(e))
            return None

    def _create_field_prompt(self, field_info: Dict[str, Any]) -> str:
        """
        Create a natural speech prompt for a form field.
        
        Generates a conversational prompt based on field type and label.
        
        Args:
            field_info: Field metadata with name, type, label
            
        Returns:
            str: Natural language prompt for the field
        """
        label = field_info.get('label') or field_info.get('name') or "field"
        
        # Clean up label
        label = label.replace('*', '').strip()
        
        # Special handling for different field types
        field_type = field_info.get('type', 'text')
        
        if field_type == 'file':
            return f"Please upload the document for {label}"
        elif field_type == 'submit':
            return ""
        elif field_type == 'email':
            return f"Please provide your {label}. You can say it letter by letter if needed."
        elif field_type in ('select', 'radio'):
            return f"Please select an option for {label}"
        elif field_type == 'checkbox':
            return f"Do you want to check {label}? Say yes or no."
        else:
            return f"Please provide {label}"

    def get_streaming_response(
        self,
        text: str,
        voice_id: Optional[str] = None
    ) -> Generator[bytes, None, None]:
        """
        Get streaming audio response for longer texts.
        
        Yields audio chunks as they are generated, reducing latency
        for the first audio playback.
        
        Args:
            text: Text to convert to speech
            voice_id: Optional voice ID override
            
        Yields:
            bytes: Audio chunks as they arrive
        """
        if not self.api_key:
            logger.warning("Cannot stream speech - API key not configured")
            yield b""
            return

        target_voice_id = voice_id or self.default_voice_id
        url = f"{self.API_BASE}/text-to-speech/{target_voice_id}/stream"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        
        data = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        
        try:
            response = requests.post(
                url,
                json=data,
                headers=headers,
                stream=True,
                timeout=60
            )
            
            if response.status_code == 200:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        yield chunk
            else:
                logger.error(f"ElevenLabs stream error: {response.text[:200]}")
                yield b""
                
        except Exception as e:
            logger.error(f"ElevenLabs stream exception: {e}")
            yield b""
