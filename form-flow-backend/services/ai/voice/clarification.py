"""
Clarification Strategy Module

Provides smart, escalating clarification for voice users.
When extraction fails, provides progressively more helpful guidance.
"""

from enum import Enum
from typing import Dict, Any, Optional


class ClarificationLevel(Enum):
    """Levels of clarification, escalating in helpfulness."""
    REPHRASE = 1
    PROVIDE_FORMAT = 2
    BREAK_DOWN = 3
    OFFER_ALTERNATIVES = 4


class ClarificationStrategy:
    """
    Provide smart, escalating clarification for voice users.
    
    When extraction fails, don't just repeat the same question.
    Each attempt provides MORE specific, DIFFERENT help.
    """
    
    @classmethod
    def get_clarification(
        cls,
        field_info: Dict[str, Any],
        attempt_count: int,
        last_input: Optional[str] = None
    ) -> str:
        """
        Generate progressive clarification based on attempt count.
        
        Args:
            field_info: Field metadata (name, label, type)
            attempt_count: How many times we've tried
            last_input: What the user said last (for context)
            
        Returns:
            Clarification prompt
        """
        field_type = field_info.get('type', 'text').lower()
        label = field_info.get('label', field_info.get('name', 'this field'))
        
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
        """First attempt: Gentle rephrasing."""
        phrases = {
            'email': f"Let me try that again. What's your email address?",
            'tel': f"Sorry, I didn't catch your phone number. Could you say it again?",
            'text': f"I missed that. What's your {label}?",
        }
        
        if 'name' in label.lower():
            return "I didn't catch your name. Could you say it again clearly?"
        
        return phrases.get(field_type, f"Could you repeat your {label}?")
    
    @classmethod
    def _provide_format_example(cls, label: str, field_type: str) -> str:
        """Second attempt: Provide concrete format example."""
        examples = {
            'email': (
                "For your email, try saying it like: "
                "'john underscore doe at gmail dot com' or spell it out like "
                "'j-o-h-n at g-m-a-i-l dot com'"
            ),
            'tel': (
                "For your phone number, try saying it with pauses: "
                "'five five five... pause... one two three four'"
            ),
            'text': f"For {label}, just say it slowly and clearly."
        }
        
        if 'name' in label.lower():
            return "Try saying your name like: 'First name is John. Last name is Smith.'"
        
        return examples.get(field_type, f"Can you tell me your {label} slowly and clearly?")
    
    @classmethod
    def _break_down_input(cls, label: str, field_type: str) -> str:
        """Third attempt: Break into smaller pieces."""
        breakdowns = {
            'email': "Let's break it down. First, what comes before the @ sign in your email?",
            'tel': "Let's go step by step. What's your area code - the first 3 digits?",
            'text': f"Let's try one piece at a time. What's the first part of your {label}?"
        }
        
        if 'name' in label.lower():
            return "Let's start simple - what's just your first name?"
        
        return breakdowns.get(field_type, f"Can you spell out your {label} letter by letter?")
    
    @classmethod
    def _offer_alternatives(cls, label: str, field_type: str) -> str:
        """Final attempt: Offer to skip or switch input mode."""
        return (
            f"Having trouble with {label} over voice. You can say 'skip' to skip this field, "
            f"or try typing it instead if that's easier."
        )
