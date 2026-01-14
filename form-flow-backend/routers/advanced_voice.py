"""
Advanced Voice AI Router

Comprehensive voice-to-form intelligence with 20+ features:
- Confidence scoring with clarification
- Multi-field entity extraction
- Real-time AI validation
- Semantic date parsing
- Voice command processing
- Smart autocomplete
- Cross-field validation
- Abbreviation expansion
- Accent-aware processing

Endpoints:
    POST /voice/refine         - Enhanced refinement with confidence
    POST /voice/extract        - Multi-field entity extraction
    POST /voice/validate       - AI-powered validation
    POST /voice/parse-date     - Semantic date parsing
    POST /voice/command        - Voice command processing
    POST /voice/autocomplete   - Smart suggestions
    POST /voice/batch          - Process entire utterance
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import re
import os

from utils.logging import get_logger, log_api_call
from utils.cache import get_cached, set_cached

logger = get_logger(__name__)

router = APIRouter(prefix="/voice", tags=["Advanced Voice AI"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class AdvancedRefineRequest(BaseModel):
    """Enhanced refinement request with full context"""
    text: str = Field(..., description="Raw voice transcription")
    question: str = Field(default="", description="Current field question/label")
    field_type: str = Field(default="text", description="Field type: email, phone, name, date, address, number, url, text")
    qa_history: Optional[List[Dict[str, str]]] = Field(default=[], description="Previous Q&A for context")
    form_context: Optional[Dict[str, str]] = Field(default={}, description="Already filled form fields")
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "um my email is like john at g mail",
                "question": "Email Address",
                "field_type": "email",
                "qa_history": [{"question": "Name", "answer": "John Smith"}],
                "form_context": {"name": "John Smith"}
            }
        }


class AdvancedRefineResponse(BaseModel):
    """Response with confidence, clarification, and suggestions"""
    success: bool
    refined: str
    original: str
    confidence: float = Field(description="0.0-1.0 confidence score")
    needs_clarification: bool = Field(default=False)
    clarification_question: Optional[str] = None
    suggestions: Optional[List[str]] = None
    detected_issues: Optional[List[str]] = None
    field_type: str = ""
    changes_made: List[str] = []


class EntityExtractionRequest(BaseModel):
    """Request for multi-field entity extraction"""
    text: str = Field(..., description="Full utterance to extract entities from")
    expected_fields: Optional[List[str]] = Field(default=None, description="Fields to look for")
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "My name is John Smith, email john@gmail.com, phone 555-1234"
            }
        }


class EntityExtractionResponse(BaseModel):
    """Extracted entities with confidence"""
    success: bool
    entities: Dict[str, str]
    confidence_scores: Dict[str, float]
    sensitive_data_detected: List[str] = []
    fields_extracted: int


class ValidationRequest(BaseModel):
    """Field validation request"""
    value: str
    field_type: str
    context: Optional[Dict[str, Any]] = {}
    
    class Config:
        json_schema_extra = {
            "example": {
                "value": "john@gmail.con",
                "field_type": "email",
                "context": {"country": "US"}
            }
        }


class ValidationResponse(BaseModel):
    """Validation result with suggestions"""
    is_valid: bool
    issues: List[str]
    suggestions: List[str]
    confidence: float
    auto_corrected: Optional[str] = None


class DateParseRequest(BaseModel):
    """Semantic date parsing request"""
    text: str
    current_date: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {"text": "next Tuesday"}
        }


class DateParseResponse(BaseModel):
    """Parsed date result"""
    success: bool
    parsed_date: Optional[str] = None
    original: str
    needs_clarification: bool = False
    clarification: Optional[str] = None
    confidence: float


class VoiceCommandRequest(BaseModel):
    """Voice command processing request"""
    command: str
    current_field: str
    form_state: Dict[str, Any]


class VoiceCommandResponse(BaseModel):
    """Command action result"""
    success: bool
    action: str
    params: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class AutocompleteRequest(BaseModel):
    """Smart autocomplete request"""
    partial_text: str
    field_type: str
    context: Optional[Dict[str, Any]] = {}


class AutocompleteResponse(BaseModel):
    """Autocomplete suggestions"""
    suggestions: List[str]
    based_on: str


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _calculate_confidence(text: str, field_type: str, refined: str) -> float:
    """Calculate confidence score based on clarity of input"""
    confidence = 1.0
    
    # Penalize filler words
    filler_count = len(re.findall(r'\b(um|uh|like|you know|basically|literally|so)\b', text.lower()))
    confidence -= filler_count * 0.05
    
    # Field-specific confidence adjustments
    if field_type == "email":
        if "@" in text.lower() or "at" in text.lower():
            confidence += 0.1
        if not re.search(r'\.(com|org|net|edu|co|io)', text.lower()):
            confidence -= 0.2  # Incomplete domain
    elif field_type == "phone":
        digits = len(re.findall(r'\d', refined))
        if digits >= 10:
            confidence += 0.1
        elif digits < 7:
            confidence -= 0.2
    elif field_type == "name":
        if len(refined.split()) >= 2:
            confidence += 0.1  # Has first and last name
    
    return max(0.0, min(1.0, confidence))


def _detect_issues(text: str, field_type: str) -> List[str]:
    """Detect potential issues in the input"""
    issues = []
    
    if field_type == "email":
        if ".con" in text.lower():
            issues.append("Domain appears to be '.con' - did you mean '.com'?")
        if "at" in text.lower() and "@" not in text:
            issues.append("'at' detected - converting to '@'")
        if not re.search(r'\.(com|org|net|edu|co|io|gov)', text.lower()):
            issues.append("Domain extension may be incomplete")
    
    elif field_type == "phone":
        digits = len(re.findall(r'\d', text))
        if digits > 10 and digits <= 11:
            issues.append("11 digits detected - is the first '1' a country code?")
        elif digits < 10:
            issues.append(f"Only {digits} digits found - phone typically needs 10")
    
    return issues


def _generate_suggestions(text: str, field_type: str, refined: str) -> List[str]:
    """Generate alternative suggestions"""
    suggestions = []
    
    if field_type == "email":
        # Extract base from refined
        base = refined.replace("@", " at ").split("at")[0].strip() if "@" in refined else refined.split()[0]
        base = re.sub(r'[^a-zA-Z0-9.]', '', base.lower())
        
        if base and "." in refined or "@" in refined:
            suggestions = [
                f"{base}@gmail.com",
                f"{base}@yahoo.com",
                f"{base}@outlook.com"
            ]
    
    return suggestions[:3]


def _expand_abbreviations(text: str) -> str:
    """Expand common abbreviations"""
    expansions = {
        r'\bSt\b': 'Street',
        r'\bRd\b': 'Road',
        r'\bAve\b': 'Avenue',
        r'\bBlvd\b': 'Boulevard',
        r'\bApt\b': 'Apartment',
        r'\bDr\b(?!\.)': 'Doctor',
        r'\bMr\b': 'Mr.',
        r'\bMrs\b': 'Mrs.',
        r'\bMs\b': 'Ms.',
        r'\bJr\b': 'Junior',
        r'\bSr\b': 'Senior',
        r'\bPh\.?D\b': 'PhD',
    }
    
    result = text
    for pattern, replacement in expansions.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    return result


def _format_phone(digits: str, country: str = "US") -> str:
    """Format phone number based on country"""
    if len(digits) == 10:
        if country == "US":
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif country == "IN":
            return f"+91 {digits[:5]} {digits[5:]}"
    elif len(digits) == 11 and digits[0] == "1":
        return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    return digits


def _parse_relative_date(text: str, base_date: datetime) -> Optional[datetime]:
    """Parse relative date expressions"""
    text_lower = text.lower().strip()
    
    if text_lower == "today":
        return base_date
    elif text_lower == "tomorrow":
        return base_date + timedelta(days=1)
    elif text_lower == "yesterday":
        return base_date - timedelta(days=1)
    
    # "next Tuesday", "this Friday", etc.
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, day in enumerate(days):
        if day in text_lower:
            current_day = base_date.weekday()
            days_ahead = i - current_day
            if "next" in text_lower or days_ahead <= 0:
                days_ahead += 7
            return base_date + timedelta(days=days_ahead)
    
    # "in X days/weeks"
    match = re.search(r'in (\d+) (day|week|month)s?', text_lower)
    if match:
        num = int(match.group(1))
        unit = match.group(2)
        if unit == "day":
            return base_date + timedelta(days=num)
        elif unit == "week":
            return base_date + timedelta(weeks=num)
        elif unit == "month":
            return base_date + timedelta(days=num * 30)
    
    return None


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post(
    "/refine",
    response_model=AdvancedRefineResponse,
    summary="Advanced text refinement with confidence scoring"
)
async def advanced_refine(request: AdvancedRefineRequest):
    """
    Enhanced voice refinement with:
    - Confidence scoring (0-100%)
    - Clarification requests when uncertain
    - Multiple suggestions
    - Issue detection
    - Context-aware processing
    """
    try:
        from services.ai.text_refiner import get_text_refiner, RefineStyle
        
        refiner = get_text_refiner()
        
        # Build context from Q&A history
        context_str = ""
        if request.qa_history:
            context_str = "; ".join([
                f"{qa.get('question', '')}: {qa.get('answer', '')}" 
                for qa in request.qa_history[-3:]
            ])
        
        # Perform refinement
        result = await refiner.refine(
            raw_text=request.text,
            question=f"[Context: {context_str}] {request.question}" if context_str else request.question,
            style=RefineStyle.DEFAULT,
            field_type=request.field_type
        )
        
        refined = result.refined
        
        # Calculate confidence
        confidence = _calculate_confidence(request.text, request.field_type, refined)
        
        # Detect issues
        issues = _detect_issues(request.text, request.field_type)
        
        # Determine if clarification needed
        needs_clarification = confidence < 0.6 or len(issues) > 0
        
        # Generate clarification question
        clarification_question = None
        if needs_clarification:
            if request.field_type == "email" and "." not in refined.split("@")[-1]:
                clarification_question = f"I heard '{refined}' - which domain did you mean? (.com, .org, .co.uk?)"
            elif issues:
                clarification_question = issues[0]
        
        # Generate suggestions if medium confidence
        suggestions = None
        if 0.4 < confidence < 0.8:
            suggestions = _generate_suggestions(request.text, request.field_type, refined)
        
        return AdvancedRefineResponse(
            success=True,
            refined=refined,
            original=request.text,
            confidence=confidence,
            needs_clarification=needs_clarification,
            clarification_question=clarification_question,
            suggestions=suggestions,
            detected_issues=issues if issues else None,
            field_type=request.field_type,
            changes_made=result.changes_made
        )
        
    except Exception as e:
        logger.error(f"Advanced refinement failed: {e}")
        return AdvancedRefineResponse(
            success=False,
            refined=request.text,
            original=request.text,
            confidence=0.0,
            needs_clarification=True,
            clarification_question=f"Error processing input: {str(e)}",
            field_type=request.field_type
        )


@router.post(
    "/extract",
    response_model=EntityExtractionResponse,
    summary="Extract multiple fields from single utterance"
)
async def extract_entities(request: EntityExtractionRequest):
    """
    Multi-field entity extraction from natural speech.
    
    Example:
        Input: "My name is John Smith, email john@gmail.com, phone 555-1234"
        Output: {name: "John Smith", email: "john@gmail.com", phone: "555-1234"}
    """
    entities = {}
    confidence_scores = {}
    sensitive_detected = []
    
    text = request.text
    
    # Email extraction
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    if email_match:
        entities["email"] = email_match.group()
        confidence_scores["email"] = 0.95
    else:
        # Try "at ... dot com" pattern
        email_spoken = re.search(r'(\w+)\s*(?:at|@)\s*(\w+)\s*(?:dot|\.)\s*(\w+)', text, re.I)
        if email_spoken:
            entities["email"] = f"{email_spoken.group(1)}@{email_spoken.group(2)}.{email_spoken.group(3)}"
            confidence_scores["email"] = 0.80
    
    # Phone extraction
    phone_match = re.search(r'(?:phone|mobile|number|cell)?\s*[:\s]*(\d[\d\s\-\(\)]{9,})', text, re.I)
    if phone_match:
        digits = re.sub(r'\D', '', phone_match.group(1))
        if len(digits) >= 10:
            entities["phone"] = _format_phone(digits)
            confidence_scores["phone"] = 0.90
    else:
        # Extract spoken numbers
        spoken_nums = re.findall(r'\b(one|two|three|four|five|six|seven|eight|nine|zero|oh)\b', text, re.I)
        if len(spoken_nums) >= 7:
            num_map = {'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
                       'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'zero': '0', 'oh': '0'}
            digits = ''.join([num_map[n.lower()] for n in spoken_nums])
            entities["phone"] = _format_phone(digits)
            confidence_scores["phone"] = 0.75
    
    # Name extraction (look for patterns like "name is X" or "I am X" or titled names)
    name_patterns = [
        r'(?:my name is|i am|i\'m|this is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
        r'\b((?:Dr|Mr|Mrs|Ms|Miss)\.\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
        r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?:,|$)',
    ]
    for pattern in name_patterns:
        name_match = re.search(pattern, text, re.I)
        if name_match:
            entities["name"] = name_match.group(1).title()
            confidence_scores["name"] = 0.85
            break
    
    # Address extraction
    address_match = re.search(
        r'(\d+\s+[\w\s]+(?:street|st|road|rd|avenue|ave|boulevard|blvd|drive|dr|lane|ln|way)[\w\s,]*)',
        text, re.I
    )
    if address_match:
        entities["address"] = _expand_abbreviations(address_match.group(1).strip())
        confidence_scores["address"] = 0.80
    
    # Sensitive data detection
    ssn_match = re.search(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b', text)
    if ssn_match and "ssn" not in text.lower() and "id" not in text.lower():
        sensitive_detected.append("Possible SSN detected")
    
    cc_match = re.search(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', text)
    if cc_match:
        sensitive_detected.append("Possible credit card number detected")
    
    return EntityExtractionResponse(
        success=len(entities) > 0,
        entities=entities,
        confidence_scores=confidence_scores,
        sensitive_data_detected=sensitive_detected,
        fields_extracted=len(entities)
    )


@router.post(
    "/validate",
    response_model=ValidationResponse,
    summary="AI-powered field validation"
)
async def validate_field(request: ValidationRequest):
    """
    Intelligent validation with auto-correction suggestions.
    
    Catches:
    - Common typos (.con → .com)
    - Format errors (missing @)
    - Cross-field inconsistencies
    """
    issues = []
    suggestions = []
    auto_corrected = None
    confidence = 1.0
    
    value = request.value.strip()
    field_type = request.field_type.lower()
    context = request.context or {}
    
    if field_type == "email":
        # Check for common typos
        typo_fixes = {
            ".con": ".com",
            ".cim": ".com", 
            ".vom": ".com",
            ".xom": ".com",
            ".comm": ".com",
            "gmial": "gmail",
            "gmal": "gmail",
            "gmil": "gmail",
            "hotmal": "hotmail",
            "yaho": "yahoo",
            "outlok": "outlook",
        }
        
        corrected = value.lower()
        for typo, fix in typo_fixes.items():
            if typo in corrected:
                issues.append(f"'{typo}' appears to be a typo for '{fix}'")
                corrected = corrected.replace(typo, fix)
                auto_corrected = corrected
                confidence = 0.95
        
        # Check for missing @
        if "@" not in value:
            issues.append("Missing '@' symbol in email")
            confidence = 0.5
            if " at " in value.lower():
                from services.ai.normalizers import normalize_email_smart
                auto_corrected = normalize_email_smart(value)
                suggestions.append(auto_corrected)
        
        # Validate format
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w{2,}$', value):
            if "@" in value:
                issues.append("Email format appears invalid")
                confidence = 0.6
    
    elif field_type == "phone":
        digits = re.sub(r'\D', '', value)
        
        if len(digits) < 10:
            issues.append(f"Phone has only {len(digits)} digits (expected 10+)")
            confidence = 0.5
        elif len(digits) == 11 and digits[0] == "1":
            issues.append("11 digits with leading 1 - is this US country code?")
            suggestions.append(f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}")
            confidence = 0.85
        elif len(digits) > 11:
            issues.append(f"Phone has {len(digits)} digits - too many?")
            confidence = 0.7
        
        # Cross-field validation with country
        country = context.get("country", "").lower()
        if country == "india" and digits.startswith("1"):
            issues.append("US format (+1) detected but country is India")
            suggestions.append(f"+91 {digits[1:]}" if len(digits) > 10 else f"+91 {digits}")
    
    elif field_type == "date":
        # Basic date format validation
        if not re.match(r'\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|\w+\s+\d{1,2},?\s+\d{4}', value):
            issues.append("Date format not recognized")
            confidence = 0.6
    
    elif field_type == "name":
        if len(value.split()) < 2:
            issues.append("Only one name provided - is this first and last name?")
            confidence = 0.7
        if re.search(r'\d', value):
            issues.append("Name contains numbers")
            confidence = 0.5
    
    is_valid = len(issues) == 0
    
    return ValidationResponse(
        is_valid=is_valid,
        issues=issues,
        suggestions=suggestions,
        confidence=confidence,
        auto_corrected=auto_corrected
    )


@router.post(
    "/parse-date",
    response_model=DateParseResponse,
    summary="Parse semantic/relative dates"
)
async def parse_date(request: DateParseRequest):
    """
    Convert natural language dates to ISO format.
    
    Examples:
    - "next Tuesday" → "2025-12-30"
    - "in 2 weeks" → "2026-01-05"
    - "tomorrow" → next day
    """
    text = request.text.strip()
    
    # Parse base date
    if request.current_date:
        try:
            base_date = datetime.fromisoformat(request.current_date)
        except:
            base_date = datetime.now()
    else:
        base_date = datetime.now()
    
    # Try relative parsing first
    parsed = _parse_relative_date(text, base_date)
    
    if parsed:
        return DateParseResponse(
            success=True,
            parsed_date=parsed.strftime("%Y-%m-%d"),
            original=text,
            needs_clarification=False,
            confidence=0.95
        )
    
    # Try to parse "March 15th" style
    month_match = re.search(
        r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s+(\d{4}))?',
        text, re.I
    )
    
    if month_match:
        months = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }
        month = months[month_match.group(1).lower()]
        day = int(month_match.group(2))
        year = int(month_match.group(3)) if month_match.group(3) else None
        
        if year:
            parsed_date = datetime(year, month, day)
            return DateParseResponse(
                success=True,
                parsed_date=parsed_date.strftime("%Y-%m-%d"),
                original=text,
                confidence=0.98
            )
        else:
            # Infer year
            current_year = base_date.year
            try_date = datetime(current_year, month, day)
            if try_date < base_date:
                try_date = datetime(current_year + 1, month, day)
            
            return DateParseResponse(
                success=True,
                parsed_date=try_date.strftime("%Y-%m-%d"),
                original=text,
                needs_clarification=True,
                clarification=f"Assuming year {try_date.year} - is that correct?",
                confidence=0.75
            )
    
    # "the 15th" - needs month clarification
    day_only = re.search(r'the\s+(\d{1,2})(?:st|nd|rd|th)?', text, re.I)
    if day_only:
        day = int(day_only.group(1))
        return DateParseResponse(
            success=False,
            parsed_date=None,
            original=text,
            needs_clarification=True,
            clarification=f"The {day}th of which month?",
            confidence=0.3
        )
    
    return DateParseResponse(
        success=False,
        parsed_date=None,
        original=text,
        needs_clarification=True,
        clarification="Could not parse date. Please say something like 'March 15, 2025' or 'next Tuesday'",
        confidence=0.1
    )


@router.post(
    "/command",
    response_model=VoiceCommandResponse,
    summary="Process voice navigation commands"
)
async def process_command(request: VoiceCommandRequest):
    """
    Voice command processing for form navigation.
    
    Commands:
    - "go back" / "previous" → previous_field
    - "skip" / "next" → next_field
    - "clear" / "reset" → clear_form
    - "repeat" → repeat_question
    - "save for later" → save_pending
    """
    command = request.command.lower().strip()
    
    # Navigation commands
    if any(word in command for word in ["go back", "previous", "back"]):
        return VoiceCommandResponse(
            success=True,
            action="previous_field",
            message="Going to previous field"
        )
    
    if any(word in command for word in ["skip", "next", "move on", "continue"]):
        return VoiceCommandResponse(
            success=True,
            action="next_field",
            message="Moving to next field"
        )
    
    if any(word in command for word in ["clear", "reset", "start over", "clear form"]):
        return VoiceCommandResponse(
            success=True,
            action="clear_form",
            message="Clearing all form data"
        )
    
    if any(word in command for word in ["repeat", "say again", "what was", "pardon"]):
        return VoiceCommandResponse(
            success=True,
            action="repeat_question",
            message=f"Repeating: {request.current_field}"
        )
    
    if any(word in command for word in ["save for later", "skip for now", "pending"]):
        return VoiceCommandResponse(
            success=True,
            action="save_pending",
            params={"field": request.current_field},
            message=f"Marked {request.current_field} to fill later"
        )
    
    if any(word in command for word in ["help", "what can i say", "commands"]):
        return VoiceCommandResponse(
            success=True,
            action="show_help",
            message="Available commands: go back, skip, clear form, repeat, save for later"
        )
    
    # Copy commands
    if "same as" in command or "copy" in command:
        # Extract source field
        match = re.search(r'(?:same as|copy)\s+(\w+)', command)
        if match:
            source_field = match.group(1).lower()
            source_value = request.form_state.get(source_field)
            if source_value:
                return VoiceCommandResponse(
                    success=True,
                    action="fill_value",
                    params={"field": request.current_field, "value": source_value},
                    message=f"Copying from {source_field}"
                )
    
    return VoiceCommandResponse(
        success=False,
        action="unknown",
        message=f"Command '{command}' not recognized. Try: go back, skip, clear form, repeat"
    )


@router.post(
    "/autocomplete",
    response_model=AutocompleteResponse,
    summary="Smart autocomplete suggestions"
)
async def get_autocomplete(request: AutocompleteRequest):
    """
    Generate smart autocomplete suggestions based on partial input and context.
    """
    partial = request.partial_text.lower().strip()
    field_type = request.field_type.lower()
    context = request.context or {}
    
    suggestions = []
    based_on = "pattern matching"
    
    if field_type == "email":
        # Extract base from partial
        if "@" in partial:
            base, domain_start = partial.split("@", 1)
        elif " at " in partial:
            parts = partial.split(" at ", 1)
            base = parts[0].strip()
            domain_start = parts[1].strip() if len(parts) > 1 else ""
        else:
            base = partial.replace(" ", "")
            domain_start = ""
        
        # Clean base
        base = re.sub(r'[^a-z0-9.]', '', base)
        
        # Generate suggestions based on name context
        name = context.get("name", "").lower().replace(" ", "")
        if name:
            based_on = f"name context: {context.get('name')}"
            parts = context.get("name", "").split()
            if len(parts) >= 2:
                first, last = parts[0].lower(), parts[-1].lower()
                suggestions = [
                    f"{first}@gmail.com",
                    f"{first}{last}@gmail.com",
                    f"{first}.{last}@gmail.com",
                    f"{first[0]}{last}@gmail.com",
                ]
        else:
            # Generic suggestions
            domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"]
            suggestions = [f"{base}@{d}" for d in domains] if base else []
    
    elif field_type == "phone":
        if digits := re.sub(r'\D', '', partial):
            if len(digits) < 10:
                suggestions = [
                    digits + "0" * (10 - len(digits)),  # Pad with zeros
                ]
    
    elif field_type == "address":
        # Common street suffixes
        if any(word in partial.lower() for word in ["street", "st", "road", "rd"]):
            based_on = "common address patterns"
            suggestions = [
                partial + ", Apartment ",
                partial + ", Suite ",
            ]
    
    return AutocompleteResponse(
        suggestions=suggestions[:5],
        based_on=based_on
    )


@router.post(
    "/batch",
    summary="Process entire utterance and fill multiple fields"
)
async def batch_process(request: EntityExtractionRequest):
    """
    Process entire spoken utterance and return all extracted + refined fields.
    
    This is the main endpoint for "speak once, fill many fields" feature.
    """
    # First extract entities
    extraction = await extract_entities(request)
    
    # Validate each extracted entity
    validated_entities = {}
    validation_results = {}
    
    for field, value in extraction.entities.items():
        field_type = field  # email, phone, name, etc.
        validation = await validate_field(ValidationRequest(
            value=value,
            field_type=field_type
        ))
        
        # Use auto-corrected value if available
        final_value = validation.auto_corrected or value
        validated_entities[field] = final_value
        validation_results[field] = {
            "original": value,
            "final": final_value,
            "is_valid": validation.is_valid,
            "issues": validation.issues,
            "confidence": validation.confidence
        }
    
    return {
        "success": True,
        "entities": validated_entities,
        "confidence_scores": extraction.confidence_scores,
        "validation_results": validation_results,
        "sensitive_data_detected": extraction.sensitive_data_detected,
        "fields_extracted": len(validated_entities)
    }


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "features": [
            "advanced_refinement",
            "entity_extraction",
            "validation",
            "date_parsing",
            "voice_commands",
            "autocomplete",
            "batch_processing",
            "smart_autofill",
            "analytics",
            "multilingual"
        ],
        "timestamp": datetime.now().isoformat()
    }


# =============================================================================
# AUTOFILL ENDPOINTS
# =============================================================================

class AutofillSuggestionsRequest(BaseModel):
    """Request for autofill suggestions"""
    user_id: str
    field_name: str
    field_type: str = "text"
    current_value: str = ""


class AutofillLearnRequest(BaseModel):
    """Request to learn from form submission"""
    user_id: str
    form_data: Dict[str, str]
    form_id: Optional[str] = None


@router.post("/autofill/suggestions")
async def get_autofill_suggestions(request: AutofillSuggestionsRequest):
    """
    Get smart autofill suggestions based on user's history.
    Returns ranked suggestions with confidence scores.
    """
    try:
        from services.ai.smart_autofill import get_smart_autofill
        
        autofill = get_smart_autofill()
        suggestions = await autofill.get_suggestions(
            user_id=request.user_id,
            field_name=request.field_name,
            field_type=request.field_type,
            current_value=request.current_value
        )
        
        return {
            "success": True,
            "suggestions": suggestions,
            "has_history": len(suggestions) > 0
        }
    except Exception as e:
        logger.error(f"Autofill suggestions failed: {e}")
        return {"success": False, "suggestions": [], "error": str(e)}


@router.post("/autofill/learn")
async def learn_from_submission(request: AutofillLearnRequest):
    """
    Learn from a successful form submission for future suggestions.
    """
    try:
        from services.ai.smart_autofill import get_smart_autofill
        
        autofill = get_smart_autofill()
        await autofill.learn_from_submission(
            user_id=request.user_id,
            form_data=request.form_data,
            form_id=request.form_id
        )
        
        return {"success": True, "message": "Learned from submission"}
    except Exception as e:
        logger.error(f"Autofill learn failed: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# ANALYTICS ENDPOINTS
# =============================================================================

class AnalyticsEventRequest(BaseModel):
    """Analytics event to track"""
    type: str
    form_id: str
    session_id: str
    field_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}


@router.post("/analytics/track")
async def track_analytics_event(request: AnalyticsEventRequest):
    """
    Track form interaction events for analytics.
    
    Event types: form_start, form_submit, field_focus, field_blur, 
                 field_change, field_error, voice_start, voice_end
    """
    try:
        from services.ai.analytics import get_form_analytics
        
        analytics = get_form_analytics()
        await analytics.track_event({
            "type": request.type,
            "form_id": request.form_id,
            "session_id": request.session_id,
            "field_id": request.field_id,
            "user_id": request.user_id,
            "metadata": request.metadata
        })
        
        return {"success": True}
    except Exception as e:
        logger.error(f"Analytics tracking failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/analytics/insights/{form_id}")
async def get_analytics_insights(form_id: str, days: int = 30):
    """
    Get comprehensive analytics insights for a form.
    
    Returns: summary, bottlenecks, error hotspots, dropout points, recommendations
    """
    try:
        from services.ai.analytics import get_form_analytics
        
        analytics = get_form_analytics()
        insights = await analytics.get_form_insights(form_id, days)
        
        return {"success": True, **insights}
    except Exception as e:
        logger.error(f"Analytics insights failed: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# MULTILINGUAL ENDPOINTS
# =============================================================================

class MultilingualRequest(BaseModel):
    """Multilingual processing request"""
    text: str
    target_language: str = "auto"
    field_type: str = ""


@router.post("/multilingual/process")
async def process_multilingual(request: MultilingualRequest):
    """
    Process multilingual voice input.
    
    - Auto-detects language
    - Translates to English if needed
    - Applies accent-specific transformations
    """
    try:
        from services.ai.multilingual import get_multilingual_processor, Language
        
        processor = get_multilingual_processor()
        
        # Map string to enum
        try:
            target_lang = Language(request.target_language.lower())
        except ValueError:
            target_lang = Language.AUTO
        
        result = await processor.process_multilingual(
            text=request.text,
            target_language=target_lang,
            field_type=request.field_type
        )
        
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Multilingual processing failed: {e}")
        return {
            "success": False,
            "detected_language": "unknown",
            "original": request.text,
            "processed": request.text,
            "was_translated": False,
            "confidence": 0.0,
            "error": str(e)
        }


@router.post("/multilingual/detect")
async def detect_language(request: MultilingualRequest):
    """
    Detect the language of input text.
    """
    try:
        from services.ai.multilingual import get_multilingual_processor
        
        processor = get_multilingual_processor()
        detected = processor.detect_language(request.text)
        
        return {
            "success": True,
            "language": detected.value,
            "text": request.text
        }
    except Exception as e:
        logger.error(f"Language detection failed: {e}")
        return {"success": False, "language": "en-US", "error": str(e)}


# =============================================================================
# FLOW ENGINE ENDPOINT (WhisperFlow)
# =============================================================================

from core.schemas import FlowEngineRequest, FlowEngineResponse, ActionPayloadSchema


@router.post(
    "/flow",
    response_model=FlowEngineResponse,
    summary="WhisperFlow voice processing pipeline"
)
async def process_with_flow_engine(
    request: FlowEngineRequest,
    db = None,
    current_user = None
):
    """
    Process voice input through the Flow Engine pipeline.
    
    The "WhisperFlow" endpoint that:
    - Handles self-corrections ("wait, no", "actually")
    - Expands user-defined snippets
    - Applies smart formatting (lists, tech terms)
    - Detects action intents (Calendar, Jira, Slack, Email)
    
    Example:
        Input: "Set meeting for Tuesday, wait actually Wednesday"
        Output: {"display_text": "Set meeting for Wednesday", "intent": "command", ...}
    """
    from fastapi import Depends
    from core.database import get_db
    from auth import get_current_user_optional
    
    # Get dependencies (handle both authenticated and anonymous)
    if db is None:
        from core.database import SessionLocal
        db = SessionLocal()
    
    try:
        from services.ai.flow_engine import FlowEngine, FlowEngineResult
        from core.models import User
        
        # Create mock user for anonymous processing
        if current_user is None:
            # Anonymous mode - create minimal user context
            class AnonymousUser:
                id = 0
            current_user = AnonymousUser()
        
        engine = FlowEngine(db=db, user=current_user)
        
        result = await engine.process(
            raw_text=request.audio_text,
            app_context=request.app_context,
            vocabulary=request.vocabulary
        )
        
        return FlowEngineResponse(
            display_text=result.display_text,
            intent=result.intent,
            detected_apps=result.detected_apps,
            actions=[
                ActionPayloadSchema(
                    tool=a.tool,
                    action_type=a.action_type,
                    payload=a.payload
                ) for a in result.actions
            ],
            corrections_applied=result.corrections_applied,
            snippets_expanded=result.snippets_expanded,
            confidence=result.confidence
        )
        
    except Exception as e:
        logger.error(f"Flow Engine failed: {e}")
        return FlowEngineResponse(
            display_text=request.audio_text,
            intent="typing",
            detected_apps=[],
            actions=[],
            corrections_applied=[],
            snippets_expanded=[],
            confidence=0.0
        )


