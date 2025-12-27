"""
Voice Quality and Confidence Module

Handles audio quality assessment, confidence calibration, and fallback strategies.
"""

import re
from enum import Enum
from typing import Dict, Any, Optional, List

from utils.logging import get_logger

logger = get_logger(__name__)


class FieldImportance(Enum):
    """Importance levels for field accuracy."""
    CRITICAL = "critical"  # Email, phone - MUST be correct
    HIGH = "high"          # Name - important but minor typos ok
    MEDIUM = "medium"      # Company - can be corrected later
    LOW = "low"            # Notes, comments - very flexible


class AudioQuality(Enum):
    """Audio quality levels."""
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class ConfidenceCalibrator:
    """
    Adjust confidence thresholds dynamically based on:
    - Field importance
    - User frustration level
    - Past correction patterns
    """
    
    # Base thresholds by importance
    BASE_THRESHOLDS = {
        FieldImportance.CRITICAL: 0.90,
        FieldImportance.HIGH: 0.80,
        FieldImportance.MEDIUM: 0.65,
        FieldImportance.LOW: 0.50,
    }
    
    # Field importance classification
    FIELD_IMPORTANCE_MAP = {
        'email': FieldImportance.CRITICAL,
        'phone': FieldImportance.CRITICAL,
        'tel': FieldImportance.CRITICAL,
        'mobile': FieldImportance.CRITICAL,
        'name': FieldImportance.HIGH,
        'first_name': FieldImportance.HIGH,
        'last_name': FieldImportance.HIGH,
        'full_name': FieldImportance.HIGH,
        'company': FieldImportance.MEDIUM,
        'organization': FieldImportance.MEDIUM,
        'title': FieldImportance.MEDIUM,
        'message': FieldImportance.LOW,
        'notes': FieldImportance.LOW,
        'comments': FieldImportance.LOW,
    }
    
    @classmethod
    def get_field_importance(cls, field_name: str, field_type: str) -> FieldImportance:
        """Determine importance level for a field."""
        name_lower = field_name.lower()
        
        for key, importance in cls.FIELD_IMPORTANCE_MAP.items():
            if key in name_lower:
                return importance
        
        if field_type in ['email', 'tel']:
            return FieldImportance.CRITICAL
        elif field_type == 'textarea':
            return FieldImportance.LOW
        
        return FieldImportance.MEDIUM
    
    @classmethod
    def should_confirm(
        cls,
        field: Dict[str, Any],
        confidence: float,
        context: Optional[Any] = None,
        stt_confidence: float = 1.0,
        is_voice: bool = False
    ) -> bool:
        """Determine if we should confirm this extraction."""
        field_name = field.get('name', 'unknown')
        field_type = field.get('type', 'text')
        
        importance = cls.get_field_importance(field_name, field_type)
        threshold = cls.BASE_THRESHOLDS.get(importance, 0.75)
        
        is_frustrated = False
        correction_count = 0
        
        if context:
            if hasattr(context, 'is_frustrated'):
                is_frustrated = context.is_frustrated()
            if hasattr(context, 'repeated_corrections'):
                correction_count = context.repeated_corrections.get(field_name, 0)
        
        if is_frustrated:
            threshold -= 0.15
            
        if correction_count > 0:
            threshold += 0.10
            
        if is_voice and stt_confidence < 0.9:
            threshold += 0.1
            
        return confidence < threshold

    @classmethod
    def generate_confirmation_prompt(
        cls,
        field_name: str,
        extracted_value: str,
        confidence: float
    ) -> str:
        """Generate natural confirmation prompt based on confidence."""
        display_name = field_name.replace('_', ' ').title()
        
        if confidence > 0.85:
            return f"Got your {display_name} as '{extracted_value}' - correct?"
        elif confidence > 0.70:
            return f"Let me confirm - your {display_name} is '{extracted_value}'?"
        else:
            return (
                f"I want to make sure I got this right. "
                f"Did you say your {display_name} is '{extracted_value}'? "
                f"Say 'yes' to confirm or 'no' to correct."
            )
    
    @classmethod
    def calculate_confidence(
        cls,
        field_name: str,
        field_type: str,
        extracted_value: str,
        stt_confidence: float,
        context: Optional[Dict] = None
    ) -> float:
        """Multi-signal confidence calculation."""
        confidence = stt_confidence
        
        if field_type == 'email':
            if cls._is_valid_email(extracted_value):
                confidence += 0.10
            else:
                confidence -= 0.20
        
        elif field_type in ['phone', 'tel']:
            if cls._is_valid_phone(extracted_value):
                confidence += 0.10
            else:
                confidence -= 0.20
        
        return min(1.0, max(0.0, confidence))
    
    @classmethod
    def _is_valid_email(cls, email: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @classmethod
    def _is_valid_phone(cls, phone: str) -> bool:
        """Validate phone format."""
        digits = re.sub(r'[^\d]', '', phone)
        return 10 <= len(digits) <= 15


class MultiModalFallback:
    """
    Know when voice is not working and offer alternatives.
    
    After repeated failures, suggest:
    - Typing instead
    - Skipping for now
    - Breaking into steps
    """
    
    DIFFICULT_VOICE_FIELDS = {'email', 'url', 'password', 'website', 'address'}
    
    @classmethod
    def should_offer_fallback(
        cls,
        field_name: str,
        field_type: str,
        failure_count: int
    ) -> bool:
        """Determine if we should offer alternative input."""
        name_lower = field_name.lower()
        
        is_difficult = (
            field_type in cls.DIFFICULT_VOICE_FIELDS or
            any(df in name_lower for df in cls.DIFFICULT_VOICE_FIELDS)
        )
        
        if is_difficult and failure_count >= 2:
            return True
        
        if failure_count >= 3:
            return True
        
        return False
    
    @classmethod
    def generate_fallback_response(cls, field_name: str) -> Dict[str, Any]:
        """Generate response with fallback options."""
        display_name = field_name.replace('_', ' ')
        
        return {
            'message': (
                f"Having trouble with {display_name} over voice. "
                f"Would you like to type it instead, skip it for now, or try one more time?"
            ),
            'fallback_type': 'multi_option',
            'options': [
                {'action': 'keyboard', 'label': 'Type it', 'voice_trigger': 'type'},
                {'action': 'skip', 'label': 'Skip for now', 'voice_trigger': 'skip'},
                {'action': 'retry', 'label': 'Try again', 'voice_trigger': 'try again'},
            ]
        }


class NoiseHandler:
    """
    Adapt to real-world audio environments.
    Adjust strategies based on audio quality metrics from STT.
    """
    
    @classmethod
    def assess_audio_quality(
        cls,
        stt_confidence: float,
        signal_to_noise: Optional[float] = None
    ) -> AudioQuality:
        """Assess audio quality from STT metadata."""
        if stt_confidence >= 0.90:
            return AudioQuality.GOOD
        elif stt_confidence >= 0.75:
            return AudioQuality.FAIR
        else:
            return AudioQuality.POOR
    
    @classmethod
    def get_quality_adapted_response(
        cls,
        audio_quality: AudioQuality,
        field_type: str,
        is_critical: bool = False
    ) -> Optional[str]:
        """Generate response adapted to audio quality."""
        if audio_quality == AudioQuality.GOOD:
            return None
        
        if audio_quality == AudioQuality.POOR:
            if is_critical:
                return (
                    "I'm having trouble hearing clearly. "
                    "Can you move to a quieter spot, or would you prefer to type this field?"
                )
            else:
                return (
                    "Audio quality is low. "
                    "Would you like to skip this for now and come back to it?"
                )
        
        if field_type in ['email', 'tel']:
            return "I'm having a bit of trouble - could you speak a bit louder or slower?"
        
        return None
