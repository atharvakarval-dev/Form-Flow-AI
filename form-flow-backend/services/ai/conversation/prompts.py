"""
LLM Prompts and Context Building

Contains system prompts and context builders for the conversation agent.
"""

from typing import Dict, List, Any, Optional
import re


# =============================================================================
# System Prompt
# =============================================================================

SYSTEM_PROMPT = """You are FormFlow, an expert form-filling assistant.

YOUR CORE TASK:
Extract field values from user's natural speech with SURGICAL PRECISION.

CRITICAL EXTRACTION PRINCIPLES:

1. BOUNDARY DETECTION:
   - Each field value has CLEAR START and END boundaries
   - STOP extraction at transition markers: "and", "my", "also", "plus"
   - STOP at mentions of OTHER field names/types
   - Extract MINIMAL viable value - don't be greedy

2. FIELD-AWARE EXTRACTION:
   When extracting for a field named "name" or "email":
   - Know what you're looking for (name = 2-3 words, email = has @, etc.)
   - Stop when you've captured enough for THAT field type
   - Don't continue into next field's territory

3. MULTI-FIELD INPUT HANDLING:
   Input: "My name is John Doe and my email is john@example.com"
   
   For field "name": Extract "John Doe" (STOP before "and my email")
   For field "email": Extract "john@example.com" (isolated extraction)
   
   NEVER include transition words in values!

4. CONFIDENCE SCORING:
   - 0.95-1.0: Perfect extraction with clear boundaries
   - 0.80-0.94: Good extraction, minor ambiguity
   - 0.60-0.79: Uncertain, needs confirmation
   - <0.60: Very uncertain or missing

5. TYPE-SPECIFIC RULES:
   - Names: 2-4 words, alphabetic, title case
   - Emails: Contains @, lowercase
   - Phones: Digits only, 10-15 chars
   - Dates: Recognize formats (DD/MM/YYYY, etc.)
   - Numbers: Pure numeric

CONTEXT-AWARE EXTRACTION:
You'll receive:
- Current fields being asked about
- User's complete input
- Previously extracted values

Your job: Extract ONLY for current fields, respecting boundaries.

OUTPUT FORMAT (strict JSON):
{
    "response": "Friendly acknowledgment + next question",
    "extracted": {
        "field_name": "precise_value_only"
    },
    "confidence": {
        "field_name": 0.95
    },
    "needs_confirmation": ["field_name_if_confidence_low"],
    "reasoning": "Brief explanation of extraction decisions"
}

Remember: PRECISION over capture. When in doubt, extract less, ask more."""


# =============================================================================
# Context Builder
# =============================================================================

class SmartContextBuilder:
    """Builds rich context for LLM to make intelligent extraction decisions."""
    
    @staticmethod
    def build_extraction_context(
        current_batch: List[Dict[str, Any]],
        remaining_fields: List[Dict[str, Any]],
        user_input: str,
        conversation_history: List[Dict[str, str]],
        already_extracted: Dict[str, str],
        session_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build comprehensive context that helps LLM understand:
        1. What fields we're currently asking about
        2. What values to look for
        3. Where to stop extraction
        4. User context (voice mode, sentiment, etc.)
        """
        context_parts = []
        
        # 1. Current batch with extraction hints
        context_parts.append("=== CURRENT FIELDS TO EXTRACT ===")
        for field in current_batch:
            name = field.get('name', '')
            label = field.get('label', name)
            ftype = field.get('type', 'text')
            expected_format = SmartContextBuilder._get_expected_format(field)
            
            context_parts.append(f"• {name} ({label})")
            context_parts.append(f"  Type: {ftype}")
            context_parts.append(f"  Expected: {expected_format}")
            
            if field.get('options'):
                options = [o.get('label', o.get('value')) for o in field['options'][:5]]
                context_parts.append(f"  Options: {', '.join(options)}")
        
        # 2. User input
        context_parts.append("\n=== USER INPUT ===")
        context_parts.append(f'"{user_input}"')
        
        # 3. Already extracted (for context)
        if already_extracted:
            context_parts.append("\n=== ALREADY EXTRACTED ===")
            for field, value in list(already_extracted.items())[:5]:
                context_parts.append(f"• {field}: {value}")
        
        # 4. STOP indicators (other field names to NOT capture)
        other_fields = [f.get('name') for f in remaining_fields if f not in current_batch]
        if other_fields:
            context_parts.append("\n=== STOP EXTRACTION BEFORE ===")
            context_parts.append(f"Do NOT include these field values: {', '.join(other_fields[:8])}")
        
        # 5. Session context if available
        if session_context:
            if session_context.get('is_voice'):
                context_parts.append("\n=== VOICE INPUT MODE ===")
                context_parts.append("User is speaking. Common STT errors may be present.")
        
        # 6. Recent conversation for context
        if conversation_history:
            recent = conversation_history[-3:]
            if recent:
                context_parts.append("\n=== RECENT CONVERSATION ===")
                for turn in recent:
                    role = turn.get('role', 'user')
                    content = turn.get('content', '')[:100]
                    context_parts.append(f"{role}: {content}")
        
        return "\n".join(context_parts)
    
    @staticmethod
    def _get_expected_format(field: Dict[str, Any]) -> str:
        """Describe expected format for field type."""
        ftype = field.get('type', 'text')
        name = field.get('name', '').lower()
        label = field.get('label', '').lower()
        
        if ftype == 'email' or 'email' in name or 'email' in label:
            return "email@domain.com format"
        elif ftype == 'tel' or 'phone' in name or 'mobile' in name:
            return "10+ digits, may include country code"
        elif 'name' in name or 'name' in label:
            if 'first' in name or 'first' in label:
                return "Single word name"
            elif 'last' in name or 'last' in label:
                return "Single word surname"
            else:
                return "Full name (2-4 words)"
        elif ftype == 'date':
            return "Date (various formats OK)"
        elif ftype == 'number':
            return "Numeric value"
        elif field.get('options'):
            return "One of the listed options"
        else:
            return "Text value"
