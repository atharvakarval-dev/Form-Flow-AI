"""
Audio Quality Assessment

Audio quality detection and confidence calibration.
"""

from enum import Enum
from typing import Dict, Any, Optional, Tuple, Union

from services.ai.voice.config import (
    FieldImportance,
    get_field_importance,
    get_threshold,
)


class AudioQuality(Enum):
    """Audio quality levels."""
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class AudioQualityAssessor:
    """Assess audio quality from STT metadata."""
    
    @staticmethod
    def assess(
        stt_confidence: float,
        signal_to_noise: Optional[float] = None
    ) -> AudioQuality:
        """
        Assess audio quality.
        
        Args:
            stt_confidence: STT confidence score (0-1)
            signal_to_noise: Optional SNR in dB
            
        Returns:
            AudioQuality level
        """
        if stt_confidence >= 0.90:
            return AudioQuality.GOOD
        elif stt_confidence >= 0.75:
            return AudioQuality.FAIR
        else:
            return AudioQuality.POOR
    
    @staticmethod
    def get_quality_message(
        quality: AudioQuality,
        field_type: str,
        is_critical: bool
    ) -> Optional[str]:
        """
        Generate user-facing message based on quality.
        
        Args:
            quality: Audio quality level
            field_type: Type of field being filled
            is_critical: Is the field critical (email, phone)
            
        Returns:
            Helpful message or None
        """
        if quality == AudioQuality.GOOD:
            return None
        
        if quality == AudioQuality.POOR and is_critical:
            return "I'm having trouble hearing you clearly. Could you speak a bit louder or move to a quieter spot?"
        
        if quality == AudioQuality.FAIR:
            return None  # Acceptable
        
        return None

    # Legacy aliases
    @staticmethod
    def assess_audio_quality(stt_confidence: float) -> AudioQuality:
        """Legacy alias for assess."""
        return AudioQualityAssessor.assess(stt_confidence)

    @staticmethod
    def get_quality_adapted_response(
        audio_quality: AudioQuality,
        field_type: str,
        is_critical: bool
    ) -> Optional[str]:
        """Legacy alias for get_quality_message."""
        return AudioQualityAssessor.get_quality_message(audio_quality, field_type, is_critical)


class ConfidenceCalibrator:
    """
    Calculate dynamic confidence thresholds.
    
    Adjusts based on field importance, audio quality, and context.
    """
    
    @staticmethod
    def get_field_importance(field_name: str, field_type: str) -> FieldImportance:
        return get_field_importance(field_name, field_type)
        
    @staticmethod
    def get_threshold(importance: FieldImportance) -> float:
        return get_threshold(importance)
    
    @classmethod
    def should_confirm(
        cls,
        field_name: Union[str, Dict, None] = None,
        field_type: str = None,
        confidence: float = None,
        stt_confidence: float = 1.0,
        is_voice: bool = False,
        context: Any = None,
        **kwargs
    ) -> bool:
        """
        Determine if extraction needs confirmation.
        
        Supports legacy signature: should_confirm(field_dict, confidence, context)
        Supports 'field' kwarg: should_confirm(field={...}, confidence=...)
        """
        # Handle 'field' kwarg alias
        if field_name is None and 'field' in kwargs:
            field_name = kwargs['field']
            
        # Handle legacy signature: should_confirm({"name": "x", "type": "y"}, 0.9, context)
        if isinstance(field_name, dict):
            field_dict = field_name
            # If the second arg is float, it's confidence
            if isinstance(field_type, (int, float)):
                confidence = float(field_type)
            # If the third arg (confidence param) is actually context
            if context is None and not isinstance(confidence, (int, float)) and confidence is not None:
                 # Check if confidence arg holds context object
                 if hasattr(confidence, 'is_frustrated') or hasattr(confidence, 'repeated_corrections'):
                     context = confidence
            
            real_name = field_dict.get('name', 'unknown')
            real_type = field_dict.get('type', 'text')
            
            # Use original confidence if passed correctly
            real_conf = confidence if isinstance(confidence, (int, float)) else 0.0
            # If confidence was passed as kwarg, it might be in kwargs or properly assigned
            
            return cls._should_confirm_internal(
                real_name, real_type, real_conf, stt_confidence, is_voice, context
            )
        
        return cls._should_confirm_internal(
            field_name, field_type, confidence or 0.0, stt_confidence, is_voice, context
        )

    @classmethod
    def _should_confirm_internal(
        cls,
        field_name: str,
        field_type: str,
        confidence: float,
        stt_confidence: float,
        is_voice: bool,
        context: Any = None
    ) -> bool:
        """Internal logic for should_confirm."""
        importance = get_field_importance(field_name, field_type)
        threshold = get_threshold(importance)
        
        # Adjust for frustration (Legacy context support)
        if context and hasattr(context, 'is_frustrated') and context.is_frustrated():
            threshold -= 0.10
        
        # Adjust for voice input
        if is_voice:
            threshold = max(threshold - 0.05, 0.5)
        
        # Adjust for poor STT confidence
        if stt_confidence < 0.8:
            threshold = min(threshold + 0.1, 0.95)
        
        return confidence < threshold
    
    @classmethod
    def calculate_confidence(
        cls,
        field_name: str,
        field_type: str,
        extracted_value: str,
        stt_confidence: float,
        is_valid: Optional[bool] = None
    ) -> float:
        """
        Calculate overall extraction confidence.
        
        Args:
            field_name: Field name
            field_type: Field type
            extracted_value: The extracted value
            stt_confidence: STT confidence
            is_valid: Whether value passes validation (optional)
            
        Returns:
            Combined confidence score
        """
        # If is_valid not provided, do basic check
        if is_valid is None:
            is_valid = cls._basic_validation(field_type, extracted_value)
            
        # Start with STT confidence
        base = stt_confidence
        
        # Adjust for validation
        if is_valid:
            base = min(base + 0.1, 0.99)
        else:
            base = max(base - 0.2, 0.3)
        
        return base
    
    @staticmethod
    def _basic_validation(field_type: str, value: str) -> bool:
        """Basic validation for backward compatibility."""
        if not value:
            return False
        
        if field_type == 'email':
            return '@' in value and '.' in value.split('@')[1]
        elif field_type in ['tel', 'phone', 'mobile']:
             # Check for at least some digits
             return any(c.isdigit() for c in value)
        
        return True
    
    @classmethod
    def generate_confirmation_prompt(
        cls,
        field_name: str,
        value: str,
        confidence: float
    ) -> str:
        """
        Generate natural confirmation prompt.
        
        Args:
            field_name: Field name
            value: Extracted value
            confidence: Extraction confidence
            
        Returns:
            Confirmation prompt string
        """
        if confidence > 0.8:
            return f"I heard {value} for {field_name}. Is that correct?"
        elif confidence > 0.6:
            return f"I think you said {value} for {field_name}, but I'm not sure. Did I get that right?"
        else:
            return f"Sorry, I had trouble hearing. Did you say {value} for {field_name}? Please answer yes or no."


class HesitationDetector:
    """Detect if user is hesitating or confused."""
    
    HESITATION_MARKERS = [
        'uh', 'um', 'hmm', 'uhh', 'umm', 'err', 'ah',
        'let me think', 'wait', 'hold on',
        "i'm not sure", 'what was it', 'i forget',
        "i don't know", "i can't remember",
    ]
    
    @classmethod
    def detect_hesitation(cls, text: str) -> bool:
        """
        Detect if user is hesitating.
        
        Args:
            text: User input
            
        Returns:
            True if hesitation detected
        """
        text_lower = text.lower()
        
        # Check markers
        has_markers = any(m in text_lower for m in cls.HESITATION_MARKERS)
        
        # Check repeated words
        words = text_lower.split()
        has_repeats = len(words) != len(set(words)) and len(words) > 3
        
        return has_markers or has_repeats
    
    @classmethod
    def get_support_message(cls, field_type: str) -> str:
        """Generate supportive message for hesitant user."""
        messages = {
            'email': "No worries! Take your time. Just say it letter by letter if that helps.",
            'phone': "It's okay! Just say the digits slowly, I'll wait.",
            'name': "No rush! Just tell me when you're ready.",
        }
        return messages.get(field_type, "Take your time, there's no rush!")
