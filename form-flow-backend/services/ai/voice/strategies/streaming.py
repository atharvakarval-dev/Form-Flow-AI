"""
Streaming Handler

Real-time speech processing support.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class PartialUtterance:
    """Represents partial/streaming speech."""
    text: str
    is_final: bool
    timestamp: float
    confidence: float = 1.0


class StreamingSpeechHandler:
    """
    Handle streaming/partial speech input.
    
    Enables real-time hints and interrupts.
    """
    
    def __init__(self):
        """Initialize streaming handler."""
        self.partial_buffer: List[str] = []
        self.silence_threshold_ms = 800
    
    def process_partial(
        self,
        partial: PartialUtterance,
        expected_field_type: Optional[str] = None
    ) -> Optional[str]:
        """
        Process partial speech in real-time.
        
        Args:
            partial: Partial utterance from STT
            expected_field_type: Expected field type
            
        Returns:
            Interrupt message if problem detected, None otherwise.
            If final, returns the full text.
        """
        if partial.is_final:
            full_text = partial.text
            self.partial_buffer.clear()
            return full_text
        
        self.partial_buffer.append(partial.text)
        
        # Check for hesitation
        from services.ai.voice.quality import HesitationDetector
        if HesitationDetector.detect_hesitation(partial.text):
            return f"HINT: {HesitationDetector.get_support_message(expected_field_type or 'text')}"
        
        # Check for common issues
        if expected_field_type == 'email':
            if 'at' in partial.text.lower() and '@' not in partial.text:
                return None  # Still processing
        
        return None
    
    def reset(self):
        """Reset the buffer."""
        self.partial_buffer.clear()
    
    def get_accumulated_text(self) -> str:
        """Get all accumulated partial text."""
        return ' '.join(self.partial_buffer)
