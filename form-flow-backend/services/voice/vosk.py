"""
Vosk Offline Speech-to-Text Service (Enhanced)

Uses local Vosk models for privacy-preserving, offline transcription.

Features:
- Word-level confidence scores
- Streaming transcription support
- Multiple model support (small/large)
- Proper singleton pattern with lazy loading

Usage:
    from services.voice.vosk import get_vosk_service
    
    vosk = get_vosk_service()
    result = vosk.transcribe_audio(audio_bytes)
"""

import os
import json
from typing import Dict, Any, Optional, List, Generator
from dataclasses import dataclass

from utils.logging import get_logger
from config.settings import settings

logger = get_logger(__name__)

# Try to import Vosk
try:
    from vosk import Model, KaldiRecognizer, SetLogLevel
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False
    logger.warning("Vosk not installed (pip install vosk)")


@dataclass
class TranscriptionResult:
    """Structured transcription result with confidence."""
    success: bool
    transcript: str
    confidence: float
    words: List[Dict[str, Any]]
    provider: str = "vosk"
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "transcript": self.transcript,
            "confidence": self.confidence,
            "words": self.words,
            "provider": self.provider,
            "error": self.error
        }


class VoskService:
    """
    Enhanced Vosk speech-to-text service.
    
    Features:
    - Word-level confidence scores
    - Streaming transcription
    - Automatic model detection
    - Configurable sample rates
    """
    
    # Default model search paths
    MODEL_SEARCH_PATHS = [
        # Small models (faster, less accurate)
        "vosk-model-small-en-in-0.4",
        "vosk-model-small-en-us-0.15",
        # Large models (slower, more accurate)
        "vosk-model-en-in-0.5",
        "vosk-model-en-us-0.22",
    ]
    
    def __init__(self, model_path: str = None, sample_rate: int = 16000):
        """
        Initialize Vosk service.
        
        Args:
            model_path: Path to Vosk model directory
            sample_rate: Audio sample rate (default: 16000 Hz)
        """
        self.sample_rate = sample_rate
        self.model = None
        self.model_path = None
        
        if not VOSK_AVAILABLE:
            logger.warning("⚠️ Vosk not installed. Offline transcription unavailable.")
            return
        
        # Disable verbose Vosk logging
        SetLogLevel(-1)
        
        # Find and load model
        self.model_path = self._find_model(model_path)
        
        if self.model_path:
            self._load_model()
    
    def _find_model(self, custom_path: str = None) -> Optional[str]:
        """Find Vosk model in common locations."""
        
        # 1. Check custom path first
        if custom_path and os.path.exists(custom_path):
            return custom_path
        
        # 2. Check common locations
        search_dirs = [
            os.path.dirname(os.path.abspath(__file__)),  # Same dir as this file
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # Parent (services/)
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),  # form-flow-backend/
            r"d:\Form-Flow-AI",  # Project root
            os.path.expanduser("~"),  # Home directory
        ]
        
        for search_dir in search_dirs:
            for model_name in self.MODEL_SEARCH_PATHS:
                candidate = os.path.join(search_dir, model_name)
                if os.path.exists(candidate):
                    logger.info(f"Found Vosk model: {candidate}")
                    return candidate
        
        logger.warning(f"No Vosk model found in: {search_dirs}")
        return None
    
    def _load_model(self) -> bool:
        """Load the Vosk model."""
        if not self.model_path:
            return False
        
        try:
            logger.info(f"🎤 Loading Vosk model from: {self.model_path}")
            self.model = Model(self.model_path)
            logger.info("✅ Vosk model loaded successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load Vosk model: {e}")
            self.model = None
            return False
    
    def is_available(self) -> bool:
        """Check if Vosk is ready for transcription."""
        return self.model is not None
    
    def transcribe_audio(
        self,
        audio_data: bytes,
        sample_rate: int = None
    ) -> TranscriptionResult:
        """
        Transcribe raw audio data using Vosk.
        
        Args:
            audio_data: Raw PCM audio bytes (16-bit mono)
            sample_rate: Override sample rate (default: 16000)
        
        Returns:
            TranscriptionResult with transcript and word-level confidence
        """
        if not self.model:
            return TranscriptionResult(
                success=False,
                transcript="",
                confidence=0.0,
                words=[],
                error="Vosk model not loaded"
            )
        
        rate = sample_rate or self.sample_rate
        
        try:
            # Create recognizer with word timestamps
            rec = KaldiRecognizer(self.model, rate)
            rec.SetWords(True)
            rec.SetPartialWords(True)
            
            # Process audio
            if rec.AcceptWaveform(audio_data):
                result = json.loads(rec.Result())
            else:
                result = json.loads(rec.FinalResult())
            
            text = result.get("text", "").strip()
            words = result.get("result", [])
            
            # Calculate overall confidence from word confidences
            confidence = self._calculate_confidence(words)
            
            if text:
                return TranscriptionResult(
                    success=True,
                    transcript=text,
                    confidence=confidence,
                    words=words
                )
            else:
                return TranscriptionResult(
                    success=False,
                    transcript="",
                    confidence=0.0,
                    words=[],
                    error="No speech detected"
                )
                
        except Exception as e:
            logger.error(f"❌ Vosk transcription error: {e}")
            return TranscriptionResult(
                success=False,
                transcript="",
                confidence=0.0,
                words=[],
                error=str(e)
            )
    
    def transcribe_streaming(
        self,
        audio_chunks: Generator[bytes, None, None],
        sample_rate: int = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Stream transcription for real-time audio.
        
        Yields partial results as audio is processed.
        
        Args:
            audio_chunks: Generator yielding audio byte chunks
            sample_rate: Override sample rate
        
        Yields:
            Dict with 'partial' or 'final' transcript and metadata
        """
        if not self.model:
            yield {"error": "Vosk model not loaded", "partial": "", "final": ""}
            return
        
        rate = sample_rate or self.sample_rate
        rec = KaldiRecognizer(self.model, rate)
        rec.SetWords(True)
        rec.SetPartialWords(True)
        
        try:
            for chunk in audio_chunks:
                if rec.AcceptWaveform(chunk):
                    # Complete phrase detected
                    result = json.loads(rec.Result())
                    text = result.get("text", "")
                    words = result.get("result", [])
                    
                    if text:
                        yield {
                            "type": "final",
                            "transcript": text,
                            "confidence": self._calculate_confidence(words),
                            "words": words
                        }
                else:
                    # Partial result
                    partial = json.loads(rec.PartialResult())
                    partial_text = partial.get("partial", "")
                    
                    if partial_text:
                        yield {
                            "type": "partial",
                            "transcript": partial_text,
                            "confidence": 0.0,
                            "words": []
                        }
            
            # Get final result
            final = json.loads(rec.FinalResult())
            final_text = final.get("text", "")
            final_words = final.get("result", [])
            
            if final_text:
                yield {
                    "type": "final",
                    "transcript": final_text,
                    "confidence": self._calculate_confidence(final_words),
                    "words": final_words
                }
                
        except Exception as e:
            logger.error(f"Streaming transcription error: {e}")
            yield {"error": str(e), "partial": "", "final": ""}
    
    def _calculate_confidence(self, words: List[Dict]) -> float:
        """
        Calculate overall confidence from word-level scores.
        
        Vosk provides word confidence in the 'conf' field.
        """
        if not words:
            return 0.0
        
        confidences = [w.get("conf", 0.0) for w in words if "conf" in w]
        
        if not confidences:
            # Vosk sometimes doesn't provide confidence
            return 0.85  # Default reasonable confidence
        
        return sum(confidences) / len(confidences)
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status and configuration."""
        return {
            "available": self.is_available(),
            "vosk_installed": VOSK_AVAILABLE,
            "model_path": self.model_path,
            "sample_rate": self.sample_rate,
            "model_loaded": self.model is not None
        }


# Singleton instance
_vosk_service_instance: Optional[VoskService] = None


def get_vosk_service(model_path: str = None) -> VoskService:
    """
    Get singleton VoskService instance.
    
    Lazy-loads the model on first call to reduce startup time.
    """
    global _vosk_service_instance
    
    if _vosk_service_instance is None:
        _vosk_service_instance = VoskService(model_path=model_path)
    
    return _vosk_service_instance


def reset_vosk_service() -> None:
    """Reset singleton (useful for testing or model switching)."""
    global _vosk_service_instance
    _vosk_service_instance = None
