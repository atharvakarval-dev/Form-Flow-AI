"""
Voice Processor

Main orchestrator for voice input processing.
Coordinates normalization, STT correction, and quality assessment.
"""

from typing import Dict, Any, Optional

from utils.logging import get_logger

# Import normalizers
from services.ai.voice.normalization import (
    EmailNormalizer,
    PhoneNormalizer,
    NameNormalizer,
    NumberNormalizer,
    DateNormalizer,
    AddressNormalizer,
)

# Import STT modules
from services.ai.voice.stt import (
    STTCorrector,
    SpelledTextHandler,
    LearningSystem,
)

# Import quality modules
from services.ai.voice.quality import (
    HesitationDetector,
    ConfidenceCalibrator,
)

# Import strategies
from services.ai.voice.strategies import (
    ClarificationStrategy,
    FallbackStrategy,
)

logger = get_logger(__name__)


class VoiceProcessor:
    """
    Main voice processing orchestrator.
    
    Coordinates:
    - STT corrections
    - Field-specific normalization
    - Learning from corrections
    - Hesitation detection
    """
    
    def __init__(self):
        """Initialize with all components."""
        # Normalizers by field type
        self.normalizers = {
            'email': EmailNormalizer(),
            'tel': PhoneNormalizer(),
            'phone': PhoneNormalizer(),
            'mobile': PhoneNormalizer(),
            'name': NameNormalizer(),
            'first_name': NameNormalizer(),
            'last_name': NameNormalizer(),
            'number': NumberNormalizer(),
            'date': DateNormalizer(),
            'dob': DateNormalizer(),
            'address': AddressNormalizer(),
            'street': AddressNormalizer(),
        }
        
        # Other components
        self.stt_corrector = STTCorrector()
        self.learning_system = LearningSystem()
        self.hesitation_detector = HesitationDetector
    
    def normalize_input(
        self,
        text: str,
        field_type: Optional[str] = None,
        field_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Main entry point for voice normalization.
        
        Pipeline:
        1. Apply learned corrections
        2. Apply general STT corrections
        3. Handle spelled-out text
        4. Route to specific normalizer
        
        Args:
            text: Raw voice input
            field_type: Type of field (email, phone, etc.)
            field_name: Name of field
            context: Additional context
            
        Returns:
            Normalized text
        """
        if not text:
            return ""
        
        result = text.strip()
        
        # 1. Apply learned corrections first
        result = self.learning_system.apply_learned_corrections(result)
        
        # 2. Apply general STT corrections
        result = self.stt_corrector.apply_corrections(result, field_type)
        
        # 3. Handle spelled-out text
        if SpelledTextHandler.is_spelled_out(result):
            result = SpelledTextHandler.join_spelled_letters(result)
        
        # 4. Route        # Select normalizer
        normalizer = self._get_normalizer(field_type, field_name)
        
        if normalizer:
            result = normalizer.normalize(result, context)
        
        logger.debug(f"Normalized: '{text}' → '{result}'")
        return result
    
    def _get_normalizer(self, field_type: Optional[str], field_name: Optional[str]):
        """Get appropriate normalizer for field."""
        # Try by type first
        if field_type and field_type in self.normalizers:
            return self.normalizers[field_type]
        
        # Try by name
        if field_name:
            name_lower = field_name.lower()
            for key, normalizer in self.normalizers.items():
                if key in name_lower:
                    return normalizer
        
        return None
    
    def learn_from_correction(self, heard: str, actual: str, context: Optional[Dict] = None):
        """
        Learn from user correction.
        
        Args:
            heard: What STT heard
            actual: What user corrected to
            context: Additional context
        """
        self.learning_system.record_correction(heard, actual, context)
    
    def detect_hesitation(self, text: str) -> bool:
        """Check if user is hesitating."""
        return self.hesitation_detector.detect_hesitation(text)
    
    def get_clarification(
        self,
        field_info: Dict[str, Any],
        attempt_count: int
    ) -> str:
        """Get progressive clarification message."""
        return ClarificationStrategy.get_clarification(field_info, attempt_count)
    
    def should_offer_fallback(
        self,
        field_name: str,
        field_type: str,
        failure_count: int
    ) -> bool:
        """Check if fallback options should be offered."""
        return FallbackStrategy.should_offer_fallback(field_name, field_type, failure_count)
    
    def get_fallback_options(self, field_name: str, label: str) -> Dict[str, Any]:
        """Get fallback options for UI."""
        return FallbackStrategy.generate_fallback_options(field_name, label)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return {
            'learning': self.learning_system.get_statistics(),
        }


# Singleton instance for backward compatibility
_processor_instance = None


def get_voice_processor() -> VoiceProcessor:
    """Get singleton voice processor instance."""
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = VoiceProcessor()
    return _processor_instance


# Backward compatibility class wrapper
class VoiceInputProcessor:
    """
    Backward compatibility wrapper.
    
    Provides static methods that delegate to VoiceProcessor instance.
    """
    
    @staticmethod
    def normalize_voice_input(
        text: str,
        expected_field_type: Optional[str] = None,
        context: Optional[Dict] = None,
        **kwargs
    ) -> str:
        """Normalize voice input (backward compatible)."""
        processor = get_voice_processor()
        
        # Determine actual context
        # If context passed explicitly, use it. Merge kwargs if any.
        actual_context = context or {}
        if kwargs:
            actual_context.update(kwargs)
            
        return processor.normalize_input(
            text,
            field_type=expected_field_type,
            context=actual_context
        )
    
    @staticmethod
    def learn_from_correction(heard: str, actual: str):
        """Learn from correction (backward compatible)."""
        processor = get_voice_processor()
        processor.learn_from_correction(heard, actual)
    
    @staticmethod
    def detect_hesitation(text: str) -> bool:
        """Detect hesitation (backward compatible)."""
        processor = get_voice_processor()
        return processor.detect_hesitation(text)
    
    @staticmethod
    def _is_spelled_out(text: str) -> bool:
        """Check if text is spelled out (backward compatible)."""
        return SpelledTextHandler.is_spelled_out(text)
    
    @staticmethod
    def _join_spelled_letters(text: str) -> str:
        """Join spelled letters (backward compatible)."""
        return SpelledTextHandler.join_spelled_letters(text)
    
    @staticmethod
    def extract_partial_email(text: str) -> Dict[str, Any]:
        """
        Extract partial email for step-by-step entry.
        
        Args:
            text: Input that may contain partial email
            
        Returns:
            Dict with local_part, domain, is_complete
        """
        result = {
            'local_part': '',
            'domain': '',
            'is_complete': False
        }
        
        if not text:
            return result
        
        text = text.strip()
        
        if '@' in text:
            parts = text.split('@', 1)
            result['local_part'] = parts[0]
            result['domain'] = parts[1] if len(parts) > 1 and parts[1] else None
            result['is_complete'] = '.' in (result['domain'] or '')
        else:
            result['local_part'] = text
            result['domain'] = None
        
        return result


# Initialize backward compatibility state
# Bind the corrections dict so tests can access/clear it
VoiceInputProcessor._user_corrections = get_voice_processor().learning_system.corrections

