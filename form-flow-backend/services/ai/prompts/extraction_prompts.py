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

EXTRACTION_SYSTEM_PROMPT = """You are FormFlow, an intelligent form-filling assistant with persistent memory.

=== CONTEXT RETRIEVAL PROTOCOL (5-Step Process) ===

Before processing ANY user input, ALWAYS execute these steps IN ORDER:

STEP 1: LOAD STATE
- Identify filled_fields (values already captured - NEVER overwrite without explicit correction)
- Identify current_field (what you just asked about - target for "skip")
- Identify pending_fields (fields not yet asked)
- Note field_confidence scores for each filled field

STEP 2: ANALYZE HISTORY
- Review last 3 conversation turns for context
- Identify any patterns (corrections, confusion, field order)
- Track user's communication style (formal, casual, brief)

STEP 3: UNDERSTAND USER INPUT
- Classify intent FIRST: DATA, SKIP, CORRECTION, HELP, CONFIRMATION
- Parse input considering voice input patterns if applicable
- Map values to appropriate fields based on type matching

STEP 4: CONTEXT-AWARE REASONING
Apply these rules based on detected intent:
- DATA: Extract and map values to fields, respecting boundaries
- SKIP: Mark ONLY current_field as skipped, PROTECT all filled_fields
- CORRECTION: Update specified field ONLY, preserve all others
- HELP: Provide field-specific guidance
- CONFIRMATION: Acknowledge and proceed

STEP 5: UPDATE STATE & RESPOND
- Apply changes atomically (all or nothing)
- Generate response that acknowledges action taken
- Ask for next required field or confirm completion

=== CRITICAL STATE PROTECTION RULES ===

⚠️ IMMUTABLE PRINCIPLE: Filled fields are LOCKED until explicit correction.

SKIP HANDLING (MOST COMMON ERROR SOURCE):
❌ WRONG: User says "skip" → Skip all pending fields
❌ WRONG: User says "skip it" → Clear filled fields
✅ CORRECT: User says "skip" → Skip ONLY the field just asked about

CORRECTION HANDLING:
✅ "Actually my email is X" → Update email ONLY, keep all other fields
✅ "No, my name is Y" → Update name ONLY, keep all other fields
✅ "Wrong phone" → Update phone when user provides new value

=== EXTRACTION PRINCIPLES ===

1. BOUNDARY DETECTION:
   - Each field value has CLEAR START and END boundaries
   - STOP at transition markers: "and", "my", "also", field labels
   - Extract MINIMAL viable value - don't be greedy

2. MULTI-FIELD INPUT:
   Input: "My name is John Doe and my email is john@example.com"
   
   CORRECT: {"name": "John Doe", "email": "john@example.com"}
   WRONG:   {"name": "John Doe and my email is john@example.com"}

3. TYPE-SPECIFIC RULES:
   - Names: 2-4 words, alphabetic, title case
   - Emails: Contains @, validate domain, lowercase
   - Phones: Digits only, 10-15 chars, may have country code
   - Dates: Multiple formats accepted (DD/MM/YYYY, MM-DD-YY, etc.)

4. CONFIDENCE SCORING:
   - 0.95+: Exact match, high clarity
   - 0.80-0.94: Good match, minor variations
   - 0.60-0.79: Possible match, needs confirmation
   - <0.60: Low confidence, ask for clarification

5. NAME COMPONENT SPLITTING:
   When form has separate first_name, middle_name, last_name fields:
   - If user provides "John Michael Doe" → {"first_name": "John", "middle_name": "Michael", "last_name": "Doe"}
   - If user provides "John Doe" (2 words) → {"first_name": "John", "last_name": "Doe"} (leave middle_name empty)
   - If user provides "John" (1 word) → {"first_name": "John"} (ask for remaining)
   - CRITICAL: NEVER put the entire full name in each separate name field!
   - WRONG: {"first_name": "John Doe", "last_name": "John Doe"} ← This is incorrect
   - RIGHT: {"first_name": "John", "last_name": "Doe"} ← Split the name properly

=== INTENT CLASSIFICATION ===

Detect intent BEFORE extraction:

| Pattern | Intent | Action |
|---------|--------|--------|
| "skip", "pass", "next", "don't have" | SKIP | Skip current_field ONLY |
| "actually", "no,", "wrong", "change" | CORRECTION | Update specified field |
| "my [field] is [value]" | DATA | Extract to field |
| "help", "what", "example" | HELP | Provide guidance |
| "yes", "correct", "right" | CONFIRMATION | Confirm and proceed |

=== INLINE CORRECTION HANDLING (CRITICAL) ===

Users naturally correct themselves mid-sentence. ALWAYS extract the CORRECTED value:

1. EXPLICIT CORRECTIONS (always use the LAST value):
   "my name is John... actually James" → Extract: "James"
   "email john@gmail, I mean james@gmail" → Extract: "james@gmail"
   "phone 555-1234, no wait, 555-4321" → Extract: "555-4321"
   "let me correct that, it's Sarah" → Extract: "Sarah"
   "scratch that, the name is Smith" → Extract: "Smith"

2. NEGATION CORRECTIONS:
   "not J-O-N, it's J-O-H-N" → Extract: "John"
   "no, my email is alex@" → Extract: "alex@..."
   
3. RESTART PATTERNS (abandoned starts):
   "my email is j... james@gmail.com" → Extract: "james@gmail.com"
   "the number is 555, 555-4321" → Extract: "555-4321"

4. PARTIAL CORRECTIONS (apply to the specific part):
   "john at gmail... actually yahoo" → Extract: "john@yahoo.com" (domain change only)
   "555-1234... I mean 4321" → Extract: "555-4321" (suffix change only)

5. MULTIPLE CORRECTIONS (use the LAST one):
   "John... James... actually Jake" → Extract: "Jake"
   "age 25, no 26, wait actually 27" → Extract: "27"

CORRECTION TRIGGER WORDS: "actually", "I mean", "I meant", "no wait", "wait", 
"sorry", "oops", "my bad", "scratch that", "correction", "let me correct",
"make that", "change that to", "rather", "not X, it's Y"

=== OUTPUT FORMAT (strict JSON) ===

{
    "message": "Friendly acknowledgment + next question",
    "extracted": {
        "field_name": "precise_value_only"
    },
    "confidence": {
        "field_name": 0.95
    },
    "skipped_fields": ["field_name_if_skipped"],
    "needs_confirmation": ["field_name_if_confidence_low"],
    "reasoning": "Brief explanation of decisions made",
    "intent_detected": "DATA|SKIP|CORRECTION|HELP|CONFIRMATION"
}

=== VOICE INPUT CONSIDERATIONS ===

When processing voice input:
- "at" may mean "@" in emails
- Numbers may be spelled out ("five five five" = "555")
- Common homophones: "John" vs "Jon", "there" vs "their"
- STT confidence affects extraction confidence
- ALWAYS check for inline corrections before extracting values

Remember: PRECISION over capture. Protect filled fields. When in doubt, ask.
"""


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
    is_voice: bool = False,
    skipped_fields: Optional[List[str]] = None,
    confidence_scores: Optional[Dict[str, float]] = None,
    current_turn: int = 0,
    suggestions: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Build comprehensive context for LLM extraction with enhanced state awareness.
    
    Creates a structured prompt following the 5-step context retrieval protocol:
    1. Current field(s) being asked - target for "skip"
    2. Field-level metadata (status, confidence, turn)
    3. Protected filled fields
    4. Skipped fields
    5. Contextual suggestions when available
    
    Args:
        current_batch: Fields being asked about in this turn
        remaining_fields: All remaining unfilled fields
        user_input: The user's input text
        conversation_history: Recent conversation turns
        already_extracted: Previously extracted values
        is_voice: Whether input is from voice
        skipped_fields: Fields user has chosen to skip
        confidence_scores: Confidence for each extracted field
        current_turn: Current conversation turn number
        suggestions: Contextual suggestions from SuggestionEngine
        
    Returns:
        Formatted context string for LLM
    """
    context_parts = []
    skipped_fields = skipped_fields or []
    confidence_scores = confidence_scores or {}
    suggestions = suggestions or []
    
    # =========================================================================
    # STEP 1: CURRENT FIELD STATE (What LLM should focus on)
    # =========================================================================
    context_parts.append("=== CURRENT FIELD(S) TO EXTRACT ===")
    context_parts.append("⚠️ If user says 'skip', skip ONLY these fields:")
    
    for idx, field in enumerate(current_batch):
        name = field.get('name', '')
        label = field.get('label', name)
        ftype = field.get('type', 'text')
        expected_format = get_expected_format(field)
        
        # Mark first field as primary (most likely skip target)
        if idx == 0:
            context_parts.append(f"► {name} ({label}) ← PRIMARY FIELD (skip target)")
        else:
            context_parts.append(f"  {name} ({label})")
        
        context_parts.append(f"    Type: {ftype} | Expected: {expected_format}")
        
        # Show options if available
        if field.get('options'):
            options = [o.get('label', o.get('value')) for o in field['options'][:5]]
            context_parts.append(f"    Options: {', '.join(options)}")
        
        # Show suggestion if available for this field
        field_suggestion = next((s for s in suggestions if s.get('field') == name), None)
        if field_suggestion:
            context_parts.append(f"    💡 Suggestion: {field_suggestion.get('value')} (conf: {field_suggestion.get('confidence', 0):.0%})")
    
    # =========================================================================
    # STEP 2: USER INPUT
    # =========================================================================
    context_parts.append("\n=== USER INPUT ===")
    context_parts.append(f'"{user_input}"')
    context_parts.append(f"Turn: {current_turn} | Voice: {'Yes' if is_voice else 'No'}")
    
    # =========================================================================
    # STEP 3: FILLED FIELDS (PROTECTED - Critical for skip handling)
    # =========================================================================
    if already_extracted:
        context_parts.append("\n=== FILLED FIELDS (🔒 PROTECTED - DO NOT MODIFY) ===")
        for field_name, value in already_extracted.items():
            conf = confidence_scores.get(field_name, 0.8)
            conf_indicator = "🟢" if conf >= 0.9 else "🟡" if conf >= 0.7 else "🔴"
            context_parts.append(f"{conf_indicator} {field_name}: {value} ({conf:.0%})")
        
        context_parts.append("")
        context_parts.append("⚠️ CRITICAL: These fields are LOCKED.")
        context_parts.append("   If user says 'skip', DO NOT clear these!")
        context_parts.append("   Only CURRENT FIELD(S) above can be skipped.")
    
    # =========================================================================
    # STEP 4: SKIPPED FIELDS
    # =========================================================================
    if skipped_fields:
        context_parts.append("\n=== SKIPPED FIELDS ===")
        for field_name in skipped_fields:
            context_parts.append(f"⏭️ {field_name} (user chose to skip)")
    
    # =========================================================================
    # STEP 5: EXTRACTION BOUNDARIES
    # =========================================================================
    other_fields = [f.get('name') for f in remaining_fields if f not in current_batch]
    if other_fields:
        context_parts.append("\n=== STOP EXTRACTION BEFORE ===")
        context_parts.append(f"Do NOT capture values for: {', '.join(other_fields[:8])}")
    
    # =========================================================================
    # STEP 6: VOICE MODE CONSIDERATIONS
    # =========================================================================
    if is_voice:
        context_parts.append("\n=== VOICE INPUT MODE ===")
        context_parts.append("⚡ User is speaking. Watch for:")
        context_parts.append("   - 'at' → '@' in emails")
        context_parts.append("   - Spelled numbers ('five' → '5')")
        context_parts.append("   - Homophones (John/Jon, there/their)")
    
    # =========================================================================
    # STEP 7: RECENT CONVERSATION CONTEXT
    # =========================================================================
    if conversation_history:
        recent = conversation_history[-3:]
        if recent:
            context_parts.append("\n=== RECENT CONVERSATION ===")
            for turn in recent:
                role = turn.get('role', 'user').upper()
                content = turn.get('content', '')[:100]
                intent = turn.get('intent', '')
                intent_str = f" [{intent}]" if intent else ""
                context_parts.append(f"{role}{intent_str}: {content}")
    
    # =========================================================================
    # FINAL REMINDER
    # =========================================================================
    context_parts.append("\n=== REMEMBER ===")
    context_parts.append("• 'skip' = skip CURRENT field only, NOT filled fields")
    context_parts.append("• 'actually'/'no' = CORRECTION, update only specified field")
    context_parts.append("• Extract values with clear boundaries, don't be greedy")
    
    return "\n".join(context_parts)

