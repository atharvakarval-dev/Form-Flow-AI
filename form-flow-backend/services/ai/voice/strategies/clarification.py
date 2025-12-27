"""
Voice Strategies

Clarification strategies and fallback handling.
"""

from enum import Enum
from typing import Dict, Any, Optional, List

from services.ai.voice.config import is_difficult_voice_field


class ClarificationLevel(Enum):
    """Escalation levels for clarification."""
    REPHRASE = 1
    PROVIDE_FORMAT = 2
    BREAK_DOWN = 3
    OFFER_ALTERNATIVES = 4


class ClarificationStrategy:
    """
    Provide escalating clarification.
    
    Each attempt provides more specific help.
    """
    
    @classmethod
    def get_clarification(
        cls,
        field_info: Dict[str, Any],
        attempt_count: int,
        last_input: Optional[str] = None
    ) -> str:
        """
        Generate progressive clarification.
        
        Args:
            field_info: Field definition
            attempt_count: Number of failed attempts
            last_input: Previous user input
            
        Returns:
            Clarification message
        """
        field_type = field_info.get('type', 'text')
        label = field_info.get('label', 'this field')
        
        if attempt_count == 1:
            return cls._rephrase_question(label, field_type)
        elif attempt_count == 2:
            return cls._provide_format_example(label, field_type)
        elif attempt_count == 3:
            return cls._break_down_input(label, field_type)
        else:
            return cls._offer_alternatives(label, field_type)
    
    @classmethod
    def _rephrase_question(cls, label: str, field_type: str) -> str:
        """Simple rephrase."""
        return f"Sorry, I didn't catch your {label}. Could you say it again?"
    
    @classmethod
    def _provide_format_example(cls, label: str, field_type: str) -> str:
        """Provide format example."""
        examples = {
            'email': "For email, try saying 'john underscore doe at gmail dot com'",
            'tel': "For phone, say digits like 'five five five one two three four five six seven'",
            'name': "Just tell me your name naturally, like 'John Smith'",
        }
        return examples.get(field_type, f"Could you tell me your {label} again?")
    
    @classmethod
    def _break_down_input(cls, label: str, field_type: str) -> str:
        """Break down into steps."""
        if field_type == 'email':
            return "Let's do this step by step. First, what's the part before the @ sign?"
        return f"Let's try again slowly. What's your {label}?"
    
    @classmethod
    def _offer_alternatives(cls, label: str, field_type: str) -> str:
        """Offer alternatives."""
        return f"Having trouble with {label}? You can type it instead, or say 'skip' to fill it later."


class FallbackStrategy:
    """Offer alternatives when voice isn't working."""
    
    @classmethod
    def should_offer_fallback(
        cls,
        field_name: str,
        field_type: str,
        failure_count: int
    ) -> bool:
        """
        Determine if we should offer fallback options.
        
        Args:
            field_name: Field name
            field_type: Field type
            failure_count: Number of failed attempts
            
        Returns:
            True if fallback should be offered
        """
        # Difficult fields - offer sooner
        if is_difficult_voice_field(field_name, field_type):
            return failure_count >= 2
        
        # Regular fields - wait longer
        return failure_count >= 3
    
    @classmethod
    def generate_fallback_options(
        cls,
        field_name: str,
        label: str
    ) -> Dict[str, Any]:
        """
        Generate fallback response with options.
        
        Args:
            field_name: Field name
            label: User-friendly label
            
        Returns:
            Dict with message and frontend actions
        """
        return {
            'message': f"Having trouble with {label}? Here are some options:",
            'options': [
                {'action': 'keyboard', 'label': '⌨️ Type it instead'},
                {'action': 'skip', 'label': '⏭️ Skip for now'},
                {'action': 'retry', 'label': '🔄 Try again'},
            ],
            'field_name': field_name,
        }
    
    @classmethod
    def generate_fallback_response(cls, field_name: str) -> Dict[str, Any]:
        """Backward compatibility alias."""
        return cls.generate_fallback_options(field_name, field_name)
