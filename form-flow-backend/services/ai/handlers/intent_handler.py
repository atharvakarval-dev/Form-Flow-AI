"""
Intent Handler

Handles special user intents: undo, skip, help, correction, status.
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from services.ai.models import AgentResponse
from utils.logging import get_logger

logger = get_logger(__name__)


class IntentHandler:
    """
    Handle special intents before extraction.
    
    Routes to specific handlers based on detected intent:
    - UNDO: Undo last action(s)
    - SKIP: Skip current fields
    - HELP: Provide contextual help
    - CORRECTION: Correct a field value
    - STATUS: Show progress
    """
    
    # Number words for undo parsing
    NUMBER_WORDS = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'last': 1, 'previous': 1
    }
    
    @classmethod
    async def handle_undo(
        cls, 
        session, 
        user_input: str,
        remaining_fields: List[Dict[str, Any]]
    ) -> AgentResponse:
        """
        Undo last action(s).
        
        Supports:
        - "undo" / "go back" - undo last action
        - "undo email" / "undo my name" - undo specific field
        - "undo last 3" / "undo two" - undo multiple actions
        """
        undo_type, target = cls._parse_undo_command(user_input, session)
        
        if not session.undo_stack:
            return AgentResponse(
                message="Nothing to undo yet! Let's continue where we left off.",
                extracted_values={},
                confidence_scores={},
                needs_confirmation=[],
                remaining_fields=remaining_fields,
                is_complete=False,
                next_questions=[]
            )
        
        undone_fields = []
        
        if undo_type == 'field':
            # Undo specific field
            field_name = target
            if field_name in session.extracted_fields:
                del session.extracted_fields[field_name]
                if field_name in session.confidence_scores:
                    del session.confidence_scores[field_name]
                undone_fields.append(field_name)
                
                # Remove from undo stack
                session.undo_stack = [
                    u for u in session.undo_stack 
                    if u.get('field_name') != field_name
                ]
        else:
            # Undo last N items
            count = target if isinstance(target, int) else 1
            for _ in range(min(count, len(session.undo_stack))):
                last = session.undo_stack.pop()
                field_name = last.get('field_name')
                if field_name and field_name in session.extracted_fields:
                    del session.extracted_fields[field_name]
                    if field_name in session.confidence_scores:
                        del session.confidence_scores[field_name]
                    undone_fields.append(field_name)
        
        if undone_fields:
            if len(undone_fields) == 1:
                message = f"Done! I've cleared your {undone_fields[0]}. What would you like it to be?"
            else:
                message = f"Done! I've cleared: {', '.join(undone_fields)}. Let's fill those again."
        else:
            message = "I couldn't find that field to undo. What would you like to change?"
        
        return AgentResponse(
            message=message,
            extracted_values={},
            confidence_scores={},
            needs_confirmation=[],
            remaining_fields=remaining_fields,
            is_complete=False,
            next_questions=[]
        )
    
    @classmethod
    def _parse_undo_command(
        cls, 
        user_input: str, 
        session
    ) -> Tuple[str, Any]:
        """
        Parse undo command to determine target.
        
        Returns:
            Tuple of (undo_type, target):
            - ('last', 1) - default undo last
            - ('last', N) - undo last N items
            - ('field', field_name) - undo specific field
        """
        user_input = user_input.lower()
        
        # Check for field name
        for field_name in session.extracted_fields.keys():
            if field_name.lower() in user_input:
                return ('field', field_name)
        
        # Check for number
        for word, num in cls.NUMBER_WORDS.items():
            if word in user_input:
                return ('last', num)
        
        # Check for digits
        match = re.search(r'\d+', user_input)
        if match:
            return ('last', int(match.group()))
        
        return ('last', 1)
    
    @classmethod
    async def handle_skip(
        cls,
        session,
        current_batch: List[Dict[str, Any]],
        remaining_fields: List[Dict[str, Any]]
    ) -> AgentResponse:
        """Skip current batch of fields."""
        skipped_names = []
        
        for field in current_batch:
            field_name = field.get('name')
            if field_name and field_name not in session.skipped_fields:
                session.skipped_fields.append(field_name)
                skipped_names.append(field.get('label', field_name))
        
        if skipped_names:
            message = f"Okay, skipping {', '.join(skipped_names)}. You can fill these later."
        else:
            message = "Nothing to skip right now."
        
        return AgentResponse(
            message=message,
            extracted_values={},
            confidence_scores={},
            needs_confirmation=[],
            remaining_fields=remaining_fields,
            is_complete=False,
            next_questions=[]
        )
    
    @classmethod
    def handle_status(
        cls, 
        session,
        remaining_fields: List[Dict[str, Any]]
    ) -> AgentResponse:
        """Show progress status."""
        total = session.get_total_field_count()
        filled = len(session.extracted_fields)
        skipped = len(session.skipped_fields)
        remaining = len(remaining_fields)
        
        progress = int((filled / total) * 100) if total > 0 else 0
        
        message = (
            f"📊 Progress: {progress}% complete\n"
            f"✅ Filled: {filled} fields\n"
            f"⏭️ Skipped: {skipped} fields\n"
            f"📝 Remaining: {remaining} fields"
        )
        
        return AgentResponse(
            message=message,
            extracted_values={},
            confidence_scores={},
            needs_confirmation=[],
            remaining_fields=remaining_fields,
            is_complete=remaining == 0,
            next_questions=[]
        )
    
    @classmethod
    def handle_help(
        cls, 
        current_batch: List[Dict[str, Any]],
        remaining_fields: List[Dict[str, Any]]
    ) -> AgentResponse:
        """Provide contextual help."""
        if current_batch:
            field = current_batch[0]
            label = field.get('label', field.get('name', 'this field'))
            field_type = field.get('type', 'text')
            
            help_tips = {
                'email': f"For {label}, say something like 'john underscore doe at gmail dot com'",
                'tel': f"For {label}, say your phone number with pauses between groups",
                'name': f"For {label}, just say your name naturally",
                'text': f"For {label}, just tell me the value",
            }
            
            tip = help_tips.get(field_type, help_tips['text'])
            message = f"💡 {tip}\n\nYou can also say 'skip' to skip this field, or 'undo' to go back."
        else:
            message = (
                "💡 Tips:\n"
                "• Say 'skip' to skip a field\n"
                "• Say 'undo' or 'go back' to correct\n"
                "• Say 'status' to see your progress\n"
                "• Speak naturally - I'll figure out the values!"
            )
        
        return AgentResponse(
            message=message,
            extracted_values={},
            confidence_scores={},
            needs_confirmation=[],
            remaining_fields=remaining_fields,
            is_complete=False,
            next_questions=[{'name': f.get('name'), 'label': f.get('label'), 'type': f.get('type')} for f in current_batch]
        )
    
    @classmethod
    async def handle_correction(
        cls,
        session,
        user_input: str,
        remaining_fields: List[Dict[str, Any]]
    ) -> AgentResponse:
        """Handle field correction request."""
        # Try to identify which field to correct
        user_input_lower = user_input.lower()
        
        for field_name, value in session.extracted_fields.items():
            if field_name.lower() in user_input_lower:
                # Found a field to correct - clear it
                del session.extracted_fields[field_name]
                if field_name in session.confidence_scores:
                    del session.confidence_scores[field_name]
                
                return AgentResponse(
                    message=f"Sure, let's update your {field_name}. What should it be?",
                    extracted_values={},
                    confidence_scores={},
                    needs_confirmation=[],
                    remaining_fields=remaining_fields,
                    is_complete=False,
                    next_questions=[]
                )
        
        # Check skipped or remaining fields (User might say "correct country" even if skipped)
        all_other_fields = session.get_remaining_fields() + \
                          [f for f in session.get_all_fields() if f['name'] in session.skipped_fields]
        
        for field in all_other_fields:
            field_name = field.get('name', '')
            field_label = field.get('label', field_name)
            
            if field_name.lower() in user_input_lower or field_label.lower() in user_input_lower:
                # Found a field they want to fill/correct
                # If it was skipped, remove from skipped
                if field_name in session.skipped_fields:
                    session.skipped_fields.remove(field_name)
                    
                return AgentResponse(
                    message=f"Sure, let's fill {field_label}. What is the value?",
                    extracted_values={},
                    confidence_scores={},
                    needs_confirmation=[],
                    remaining_fields=remaining_fields,
                    is_complete=False,
                    next_questions=[field] # Ask about this field specifically
                )
        
        # No specific field mentioned - ask which one
        filled_fields = list(session.extracted_fields.keys())
        if filled_fields:
            message = f"Which field would you like to correct? You've filled: {', '.join(filled_fields)}"
        else:
            message = "No fields filled yet. Let's start fresh!"
        
        return AgentResponse(
            message=message,
            extracted_values={},
            confidence_scores={},
            needs_confirmation=[],
            remaining_fields=remaining_fields,
            is_complete=False,
            next_questions=[]
        )
