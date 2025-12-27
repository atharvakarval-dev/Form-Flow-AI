"""
Voice Processor - Backward Compatibility Shim

This module re-exports from the new modular voice package
for backward compatibility with existing imports.

The actual implementation is in services.ai.voice/
"""

# Re-export everything from the new modular package
from services.ai.voice import (
    # Main classes
    VoiceProcessor,
    VoiceInputProcessor,
    get_voice_processor,
    
    # Normalizers
    EmailNormalizer,
    PhoneNormalizer,
    NameNormalizer,
    NumberNormalizer,
    NormalizationResult,
    
    # STT
    STTCorrector,
    SpelledTextHandler,
    LearningSystem,
    
    # Quality
    AudioQuality,
    AudioQualityAssessor,
    ConfidenceCalibrator,
    HesitationDetector,
    NoiseHandler,
    
    # Strategies
    ClarificationLevel,
    ClarificationStrategy,
    FallbackStrategy,
    MultiModalFallback,
    StreamingSpeechHandler,
    PartialUtterance,
    
    # Matching
    PhoneticMatcher,
    
    # Config
    FieldImportance,
)

__all__ = [
    'VoiceProcessor',
    'VoiceInputProcessor',
    'get_voice_processor',
    'EmailNormalizer',
    'PhoneNormalizer',
    'NameNormalizer',
    'NumberNormalizer',
    'NormalizationResult',
    'STTCorrector',
    'SpelledTextHandler',
    'LearningSystem',
    'AudioQuality',
    'AudioQualityAssessor',
    'ConfidenceCalibrator',
    'HesitationDetector',
    'NoiseHandler',
    'ClarificationLevel',
    'ClarificationStrategy',
    'FallbackStrategy',
    'MultiModalFallback',
    'StreamingSpeechHandler',
    'PartialUtterance',
    'PhoneticMatcher',
    'FieldImportance',
]
