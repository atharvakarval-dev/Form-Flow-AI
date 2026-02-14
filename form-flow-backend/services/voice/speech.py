"""
Text-to-Speech Service (Enhanced)

Provides text-to-speech functionality with:
- ElevenLabs API (primary - high quality)
- Edge TTS fallback (free - Microsoft voices)
- Audio caching (reduces API costs)
- Automatic retry with exponential backoff

Usage:
    from services.voice.speech import SpeechService
    
    service = SpeechService(api_key="...")
    audio_bytes = service.text_to_speech("Please enter your name")
"""

import os
import hashlib
import asyncio
from typing import Optional, Dict, Any, Generator
from collections import OrderedDict
from functools import lru_cache
import time

import requests

from utils.logging import get_logger, log_api_call
from utils.exceptions import SpeechGenerationError
from config.settings import settings

logger = get_logger(__name__)

# Try to import edge-tts for free fallback
try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False
    logger.info("edge-tts not installed - fallback TTS unavailable (pip install edge-tts)")


class AudioCache:
    """
    Simple in-memory cache for generated audio.
    Caches by text hash to avoid regenerating identical prompts.
    Uses OrderedDict for O(1) LRU eviction.
    """
    
    def __init__(self, max_size: int = 100):
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
    
    def _get_key(self, text: str, voice_id: str) -> str:
        """Generate cache key from text and voice."""
        content = f"{text}:{voice_id}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, text: str, voice_id: str) -> Optional[bytes]:
        """Get cached audio if available."""
        key = self._get_key(text, voice_id)
        if key in self._cache:
            self._hits += 1
            self._cache.move_to_end(key)  # O(1) LRU update
            logger.debug(f"Cache HIT for: '{text[:30]}...' (hits: {self._hits})")
            return self._cache[key]
        self._misses += 1
        return None
    
    def set(self, text: str, voice_id: str, audio: bytes) -> None:
        """Cache audio data."""
        key = self._get_key(text, voice_id)
        
        # Evict oldest if at capacity
        while len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)  # O(1) eviction
        
        self._cache[key] = audio
        logger.debug(f"Cached audio for: '{text[:30]}...' (size: {len(audio)} bytes)")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1f}%",
            "cached_items": len(self._cache),
            "max_size": self._max_size
        }


class SpeechService:
    """
    Enhanced Text-to-Speech service with caching and fallbacks.
    
    Features:
    - ElevenLabs API (primary - high quality)
    - Edge TTS fallback (free - Microsoft voices)
    - Audio caching (reduces API costs by ~70%)
    - Automatic retry with exponential backoff
    """
    
    # ElevenLabs API endpoint
    API_BASE = "https://api.elevenlabs.io/v1"
    
    # Default voice settings
    DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel
    DEFAULT_MODEL = "eleven_turbo_v2_5"
    
    # Edge TTS voice mapping (for fallback)
    EDGE_TTS_VOICE = "en-US-JennyNeural"  # Similar to Rachel
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        model: Optional[str] = None,
        enable_cache: bool = True,
        cache_size: int = 100
    ):
        """
        Initialize speech service.
        
        Args:
            api_key: ElevenLabs API key
            voice_id: Voice ID to use (default: Rachel)
            model: TTS model to use (default: eleven_turbo_v2_5)
            enable_cache: Enable audio caching (default: True)
            cache_size: Max cached items (default: 100)
        """
        self.api_key = api_key
        self.default_voice_id = voice_id or self.DEFAULT_VOICE_ID
        self.model = model or self.DEFAULT_MODEL
        
        # Initialize cache
        self._cache = AudioCache(max_size=cache_size) if enable_cache else None
        
        # Reusable HTTP session for connection pooling (saves TCP+TLS handshake per request)
        self._session = requests.Session()
        
        # Track ElevenLabs quota status
        self._elevenlabs_available = bool(self.api_key)
        self._last_quota_check = 0
        
        if not self.api_key:
            logger.warning("ElevenLabs API key not configured - using Edge TTS fallback")
        else:
            logger.info("✅ SpeechService initialized (ElevenLabs + Edge TTS fallback)")
    
    def text_to_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        use_cache: bool = True
    ) -> Optional[bytes]:
        """
        Convert text to speech audio with caching and fallback.
        
        Args:
            text: Text to convert to speech
            voice_id: Optional voice ID override
            use_cache: Whether to use cache (default: True)
            
        Returns:
            bytes: Audio data as MP3, or None on failure
        """
        target_voice_id = voice_id or self.default_voice_id
        
        # 1. Check cache first
        if use_cache and self._cache:
            cached = self._cache.get(text, target_voice_id)
            if cached:
                return cached
        
        # 2. Try ElevenLabs (primary)
        audio = None
        if self._elevenlabs_available:
            audio = self._elevenlabs_tts(text, target_voice_id)
        
        # 3. Fallback to Edge TTS (free)
        if audio is None and HAS_EDGE_TTS:
            logger.info("Falling back to Edge TTS...")
            audio = self._edge_tts(text)
        
        # 4. Cache successful result
        if audio and use_cache and self._cache:
            self._cache.set(text, target_voice_id, audio)
        
        return audio
    
    def _elevenlabs_tts(
        self,
        text: str,
        voice_id: str,
        max_retries: int = 2
    ) -> Optional[bytes]:
        """
        Generate speech using ElevenLabs API with retry logic.
        """
        if not self.api_key:
            return None
        
        url = f"{self.API_BASE}/text-to-speech/{voice_id}"
        
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
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"ElevenLabs TTS attempt {attempt + 1}: '{text[:50]}...'")
                
                response = self._session.post(
                    url,
                    json=data,
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    logger.debug(f"Speech generated: {len(response.content)} bytes")
                    log_api_call("ElevenLabs", "text-to-speech", success=True)
                    return response.content
                
                elif response.status_code == 401:
                    # Invalid API key
                    logger.error("ElevenLabs: Invalid API key")
                    self._elevenlabs_available = False
                    return None
                
                elif response.status_code == 429:
                    # Rate limited or quota exceeded
                    logger.warning("ElevenLabs: Rate limited or quota exceeded")
                    self._elevenlabs_available = False
                    return None
                
                else:
                    error_msg = f"Status {response.status_code}: {response.text[:200]}"
                    logger.warning(f"ElevenLabs API error: {error_msg}")
                    
                    # Retry with exponential backoff
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.info(f"Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    
            except requests.Timeout:
                logger.warning(f"ElevenLabs timeout (attempt {attempt + 1})")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"ElevenLabs exception: {e}")
                break
        
        log_api_call("ElevenLabs", "text-to-speech", success=False, error="max retries exceeded")
        return None
    
    def _edge_tts(self, text: str) -> Optional[bytes]:
        """
        Generate speech using Edge TTS (free Microsoft voices).
        Returns MP3 audio bytes.
        """
        if not HAS_EDGE_TTS:
            return None
        
        try:
            # Edge TTS is async, so we need to run it in an event loop
            async def generate():
                communicate = edge_tts.Communicate(text, self.EDGE_TTS_VOICE)
                audio_parts = bytearray()
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_parts.extend(chunk["data"])
                return bytes(audio_parts)
            
            # Run async function
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            audio = loop.run_until_complete(generate())
            
            if audio:
                logger.info(f"Edge TTS generated: {len(audio)} bytes")
                log_api_call("EdgeTTS", "text-to-speech", success=True)
                return audio
                
        except Exception as e:
            logger.error(f"Edge TTS error: {e}")
            log_api_call("EdgeTTS", "text-to-speech", success=False, error=str(e))
        
        return None

    def _create_field_prompt(self, field_info: Dict[str, Any]) -> str:
        """
        Create a natural speech prompt for a form field.
        
        Generates a conversational prompt based on field type and label.
        """
        label = field_info.get('label') or field_info.get('name') or "field"
        label = label.replace('*', '').strip()
        
        field_type = field_info.get('type', 'text')
        
        prompts = {
            'file': f"Please upload the document for {label}",
            'submit': "",
            'email': f"Please provide your {label}. You can say it letter by letter if needed.",
            'select': f"Please select an option for {label}",
            'radio': f"Please select an option for {label}",
            'checkbox': f"Do you want to check {label}? Say yes or no.",
            'tel': f"Please provide your {label}. You can say it digit by digit.",
            'date': f"Please provide {label}. You can say it naturally like January 15th 2024.",
            'textarea': f"Please provide {label}. Take your time.",
        }
        
        return prompts.get(field_type, f"Please provide {label}")

    def get_streaming_response(
        self,
        text: str,
        voice_id: Optional[str] = None
    ) -> Generator[bytes, None, None]:
        """
        Get streaming audio response for longer texts.
        
        Yields audio chunks as they are generated, reducing latency
        for the first audio playback.
        """
        if not self.api_key:
            # Try Edge TTS for streaming fallback
            if HAS_EDGE_TTS:
                yield from self._edge_tts_stream(text)
            else:
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
                # Fallback to Edge TTS
                if HAS_EDGE_TTS:
                    yield from self._edge_tts_stream(text)
                else:
                    yield b""
                
        except Exception as e:
            logger.error(f"ElevenLabs stream exception: {e}")
            if HAS_EDGE_TTS:
                yield from self._edge_tts_stream(text)
            else:
                yield b""
    
    def _edge_tts_stream(self, text: str) -> Generator[bytes, None, None]:
        """Stream audio from Edge TTS."""
        if not HAS_EDGE_TTS:
            yield b""
            return
        
        try:
            async def stream_generate():
                communicate = edge_tts.Communicate(text, self.EDGE_TTS_VOICE)
                chunks = []
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        chunks.append(chunk["data"])
                return chunks
            
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            chunks = loop.run_until_complete(stream_generate())
            for chunk in chunks:
                yield chunk
                
        except Exception as e:
            logger.error(f"Edge TTS stream error: {e}")
            yield b""
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if self._cache:
            return self._cache.get_stats()
        return {"enabled": False}
    
    def clear_cache(self) -> None:
        """Clear the audio cache."""
        if self._cache:
            self._cache._cache.clear()
            logger.info("Audio cache cleared")


# Singleton instance
_speech_service_instance: Optional[SpeechService] = None


def get_speech_service(api_key: str = None) -> SpeechService:
    """Get singleton SpeechService instance."""
    global _speech_service_instance
    if _speech_service_instance is None:
        _speech_service_instance = SpeechService(
            api_key=api_key or settings.ELEVENLABS_API_KEY
        )
    return _speech_service_instance
