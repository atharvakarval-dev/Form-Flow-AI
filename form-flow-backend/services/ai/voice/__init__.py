"""
Voice Processing Module

Handles voice-specific processing including STT correction and clarification.
"""

from services.ai.voice.processor import VoiceInputProcessor, PhoneticMatcher
from services.ai.voice.clarification import ClarificationStrategy, ClarificationLevel
from services.ai.voice.quality import (
    NoiseHandler, 
    ConfidenceCalibrator, 
    MultiModalFallback,
    AudioQuality,
    FieldImportance,
)

__all__ = [
    'VoiceInputProcessor',
    'PhoneticMatcher',
    'ClarificationStrategy',
    'ClarificationLevel',
    'NoiseHandler',
    'ConfidenceCalibrator',
    'MultiModalFallback',
    'AudioQuality',
    'FieldImportance',
]
