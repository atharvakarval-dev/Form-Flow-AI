"""
Voice Package

Voice input processing, normalization, and quality assessment.
"""

# Main processor
from services.ai.voice.processor import (
    VoiceProcessor,
    VoiceInputProcessor,
    get_voice_processor,
)

# Normalizers
from services.ai.voice.normalization import (
    EmailNormalizer,
    PhoneNormalizer,
    NameNormalizer,
    NumberNormalizer,
    NormalizationResult,
)

# STT
from services.ai.voice.stt import (
    STTCorrector,
    SpelledTextHandler,
    LearningSystem,
)

# Quality
from services.ai.voice.quality import (
    AudioQuality,
    AudioQualityAssessor,
    ConfidenceCalibrator,
    HesitationDetector,
)

# Strategies
from services.ai.voice.strategies import (
    ClarificationLevel,
    ClarificationStrategy,
    FallbackStrategy,
    StreamingSpeechHandler,
    PartialUtterance,
)

# Matching
from services.ai.voice.matching import PhoneticMatcher

# Config
from services.ai.voice.config import FieldImportance

# Backward compatibility - also expose NoiseHandler and MultiModalFallback as aliases
NoiseHandler = AudioQualityAssessor
MultiModalFallback = FallbackStrategy

__all__ = [
    # Main
    'VoiceProcessor',
    'VoiceInputProcessor',
    'get_voice_processor',
    # Normalizers
    'EmailNormalizer',
    'PhoneNormalizer',
    'NameNormalizer',
    'NumberNormalizer',
    'NormalizationResult',
    # STT
    'STTCorrector',
    'SpelledTextHandler',
    'LearningSystem',
    # Quality
    'AudioQuality',
    'AudioQualityAssessor',
    'ConfidenceCalibrator',
    'HesitationDetector',
    'NoiseHandler',  # Alias
    # Strategies
    'ClarificationLevel',
    'ClarificationStrategy',
    'FallbackStrategy',
    'MultiModalFallback',  # Alias
    'StreamingSpeechHandler',
    'PartialUtterance',
    # Matching
    'PhoneticMatcher',
    # Config
    'FieldImportance',
]
