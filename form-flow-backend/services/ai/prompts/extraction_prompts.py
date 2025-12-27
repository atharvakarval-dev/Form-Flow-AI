"""
Extraction Prompts

LLM prompt engineering for field extraction.
Contains system prompts and context builders.

Version: 2.0
"""

from typing import Dict, List, Any, Optional


# =============================================================================
# System Prompt - Version 2.0
# =============================================================================

EXTRACTION_SYSTEM_PROMPT = """You are FormFlow, an expert form-filling assistant.

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

OUTPUT FORMAT (strict JSON):
{
    "message": "Friendly acknowledgment + next question",
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
# Field Format Descriptions
# =============================================================================

FIELD_FORMAT_DESCRIPTIONS = {
    'email': "email@domain.com format",
    'tel': "10+ digits, may include country code",
    'phone': "10+ digits, may include country code",
    'first_name': "Single word name",
    'last_name': "Single word surname",
    'name': "Full name (2-4 words)",
    'date': "Date (various formats OK)",
    'number': "Numeric value",
    'textarea': "Text paragraph",
    'text': "Text value",
}


def get_expected_format(field: Dict[str, Any]) -> str:
    """
    Describe expected format for field type.
    
    Args:
        field: Field definition with name, type, label
        
    Returns:
        Human-readable format description
    """
    field_type = field.get('type', 'text')
    field_name = field.get('name', '').lower()
    field_label = field.get('label', '').lower()
    
    # Check field type first
    if field_type in FIELD_FORMAT_DESCRIPTIONS:
        return FIELD_FORMAT_DESCRIPTIONS[field_type]
    
    # Check name/label patterns
    if 'email' in field_name or 'email' in field_label:
        return FIELD_FORMAT_DESCRIPTIONS['email']
    if 'phone' in field_name or 'mobile' in field_name:
        return FIELD_FORMAT_DESCRIPTIONS['tel']
    if 'first' in field_name and 'name' in field_name:
        return FIELD_FORMAT_DESCRIPTIONS['first_name']
    if 'last' in field_name and 'name' in field_name:
        return FIELD_FORMAT_DESCRIPTIONS['last_name']
    if 'name' in field_name or 'name' in field_label:
        return FIELD_FORMAT_DESCRIPTIONS['name']
    
    # Check for options
    if field.get('options'):
        return "One of the listed options"
    
    return FIELD_FORMAT_DESCRIPTIONS['text']


# =============================================================================
# Context Builder
# =============================================================================

def build_extraction_context(
    current_batch: List[Dict[str, Any]],
    remaining_fields: List[Dict[str, Any]],
    user_input: str,
    conversation_history: List[Dict[str, str]],
    already_extracted: Dict[str, str],
    is_voice: bool = False
) -> str:
    """
    Build comprehensive context for LLM extraction.
    
    Creates a structured prompt that helps the LLM understand:
    1. What fields we're currently asking about
    2. What values to look for
    3. Where to stop extraction
    4. User context (voice mode, etc.)
    
    Args:
        current_batch: Fields being asked about in this turn
        remaining_fields: All remaining unfilled fields
        user_input: The user's input text
        conversation_history: Recent conversation turns
        already_extracted: Previously extracted values
        is_voice: Whether input is from voice
        
    Returns:
        Formatted context string for LLM
    """
    context_parts = []
    
    # 1. Current batch with extraction hints
    context_parts.append("=== CURRENT FIELDS TO EXTRACT ===")
    for field in current_batch:
        name = field.get('name', '')
        label = field.get('label', name)
        ftype = field.get('type', 'text')
        expected_format = get_expected_format(field)
        
        context_parts.append(f"• {name} ({label})")
        context_parts.append(f"  Type: {ftype}")
        context_parts.append(f"  Expected: {expected_format}")
        
        if field.get('options'):
            options = [o.get('label', o.get('value')) for o in field['options'][:5]]
            context_parts.append(f"  Options: {', '.join(options)}")
    
    # 2. User input
    context_parts.append("\n=== USER INPUT ===")
    context_parts.append(f'"{user_input}"')
    
    # 3. Already extracted (for context, limit to avoid token bloat)
    if already_extracted:
        context_parts.append("\n=== ALREADY EXTRACTED ===")
        for field, value in list(already_extracted.items())[:5]:
            context_parts.append(f"• {field}: {value}")
    
    # 4. STOP indicators (other field names to NOT capture)
    other_fields = [f.get('name') for f in remaining_fields if f not in current_batch]
    if other_fields:
        context_parts.append("\n=== STOP EXTRACTION BEFORE ===")
        context_parts.append(f"Do NOT include these field values: {', '.join(other_fields[:8])}")
    
    # 5. Voice mode indicator
    if is_voice:
        context_parts.append("\n=== VOICE INPUT MODE ===")
        context_parts.append("User is speaking. Common STT errors may be present.")
    
    # 6. Recent conversation (limit to 3 turns)
    if conversation_history:
        recent = conversation_history[-3:]
        if recent:
            context_parts.append("\n=== RECENT CONVERSATION ===")
            for turn in recent:
                role = turn.get('role', 'user')
                content = turn.get('content', '')[:100]
                context_parts.append(f"{role}: {content}")
    
    return "\n".join(context_parts)
