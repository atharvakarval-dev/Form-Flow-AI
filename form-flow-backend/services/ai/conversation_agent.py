"""
Conversation Agent Service

LangChain-powered conversational agent for intelligent form filling.
Maintains conversation memory across turns and asks batched, natural questions.

Features:
    - Multi-turn conversation memory
    - Semantic field clustering for intelligent batching
    - Confidence scoring with confirmation prompts
    - Natural language question generation
    - Partial answer extraction

Usage:
    from services.ai.conversation_agent import ConversationAgent
    
    agent = ConversationAgent()
    session = agent.create_session(form_schema)
    response = agent.process_user_input(session.id, "My name is John Smith")
"""

import os
import json
import re
import asyncio
from difflib import SequenceMatcher
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import uuid

from utils.logging import get_logger, log_api_call
from utils.exceptions import AIServiceError
from utils.validators import validate_form_schema, validate_user_input, InputValidationError
from utils.pii_sanitizer import sanitize_for_log
from config.constants import (
    CONFIDENCE_THRESHOLD_MEDIUM,
    SESSION_TTL_MINUTES,
    MAX_CONVERSATION_CONTEXT_TURNS,
    MAX_UPCOMING_FIELDS_CONTEXT,
    LLM_MAX_RETRIES,
    LLM_RETRY_BASE_DELAY,
    LLM_RETRY_MAX_DELAY,
    LLM_TEMPERATURE,
    DEFAULT_LLM_MODEL,
    BATCH_SIZE_SIMPLE,
    BATCH_SIZE_MODERATE,
    BATCH_SIZE_COMPLEX,
    SIMPLE_FIELD_TYPES,
    MODERATE_FIELD_TYPES,
    COMPLEX_FIELD_TYPES,
    PHONE_MIN_DIGITS,
    PHONE_MAX_DIGITS,
    TEXT_MIN_LENGTH,
    TEXT_MAX_LENGTH,
)

# Import TextRefiner for cleaning extracted values
try:
    from services.ai.text_refiner import get_text_refiner
    TEXT_REFINER_AVAILABLE = True
except ImportError:
    TEXT_REFINER_AVAILABLE = False

# Import Conversational Intelligence components
from services.ai.conversation_intelligence import (
    ConversationContext,
    IntentRecognizer,
    AdaptiveResponseGenerator,
    ProgressTracker,
    CorrectionRecord,
    UndoRecord,
    PersonalityConfig,
    UserIntent,
    UserSentiment,
)

# Import Voice Processing components
from services.ai.voice_processor import (
    VoiceInputProcessor,
    ClarificationStrategy,
    ConfidenceCalibrator,
    MultiModalFallback,
    NoiseHandler,
    PhoneticMatcher,
)

logger = get_logger(__name__)

# Try to import LangChain - graceful fallback if not available
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    logger.warning("LangChain not installed. Using fallback mode.")
    LANGCHAIN_AVAILABLE = False


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ConversationSession:
    """Represents an active conversation session with enhanced conversational context."""
    id: str
    form_schema: List[Dict[str, Any]]
    form_url: str
    extracted_fields: Dict[str, str] = field(default_factory=dict)
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    current_question_batch: List[str] = field(default_factory=list)
    skipped_fields: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    # Enhanced conversational intelligence fields
    conversation_context: ConversationContext = field(default_factory=ConversationContext)
    undo_stack: List[Dict[str, Any]] = field(default_factory=list)
    correction_history: List[Dict[str, Any]] = field(default_factory=list)
    field_attempt_counts: Dict[str, int] = field(default_factory=dict)  # Track extraction failures per field
    shown_milestones: set = field(default_factory=set)  # Track shown progress milestones
    turns_per_field: Dict[str, int] = field(default_factory=dict)  # Turns taken per field for metrics
    
    def is_expired(self, ttl_minutes: int = 30) -> bool:
        """Check if session has expired."""
        return datetime.now() - self.last_activity > timedelta(minutes=ttl_minutes)
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.now()
    
    def get_total_field_count(self) -> int:
        """Get total number of fillable fields."""
        count = 0
        for form in self.form_schema:
            for f in form.get('fields', []):
                if f.get('type') not in ['submit', 'button', 'hidden'] and not f.get('hidden'):
                    count += 1
        return count
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to dictionary for Redis storage."""
        return {
            'id': self.id,
            'form_schema': self.form_schema,
            'form_url': self.form_url,
            'extracted_fields': self.extracted_fields,
            'confidence_scores': self.confidence_scores,
            'conversation_history': self.conversation_history,
            'current_question_batch': self.current_question_batch,
            'skipped_fields': self.skipped_fields,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'conversation_context': self.conversation_context.to_dict(),
            'undo_stack': self.undo_stack,
            'correction_history': self.correction_history,
            'field_attempt_counts': self.field_attempt_counts,
            'shown_milestones': list(self.shown_milestones),
            'turns_per_field': self.turns_per_field,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationSession':
        """Deserialize session from dictionary."""
        return cls(
            id=data['id'],
            form_schema=data['form_schema'],
            form_url=data['form_url'],
            extracted_fields=data.get('extracted_fields', {}),
            confidence_scores=data.get('confidence_scores', {}),
            conversation_history=data.get('conversation_history', []),
            current_question_batch=data.get('current_question_batch', []),
            skipped_fields=data.get('skipped_fields', []),
            created_at=datetime.fromisoformat(data['created_at']) if isinstance(data.get('created_at'), str) else data.get('created_at', datetime.now()),
            last_activity=datetime.fromisoformat(data['last_activity']) if isinstance(data.get('last_activity'), str) else data.get('last_activity', datetime.now()),
            conversation_context=ConversationContext.from_dict(data.get('conversation_context', {})),
            undo_stack=data.get('undo_stack', []),
            correction_history=data.get('correction_history', []),
            field_attempt_counts=data.get('field_attempt_counts', {}),
            shown_milestones=set(data.get('shown_milestones', [])),
            turns_per_field=data.get('turns_per_field', {}),
        )


@dataclass  
class AgentResponse:
    """Response from the conversation agent."""
    message: str
    extracted_values: Dict[str, str]
    confidence_scores: Dict[str, float]
    needs_confirmation: List[str]
    remaining_fields: List[Dict[str, Any]]
    is_complete: bool
    next_questions: List[Dict[str, Any]]
    fallback_options: List[Dict[str, Any]] = field(default_factory=list)  # Multi-modal fallback options


# =============================================================================
# Enhanced LLM Prompt Engineering
# =============================================================================

IMPROVED_SYSTEM_PROMPT = """You are FormFlow, an expert form-filling assistant.

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

EXAMPLE:
User: "hi my name is Sarah Chen and my email is sarah.chen@company.com and phone is 9876543210"

Current fields: ["full_name", "email_address", "phone_number"]

Correct output:
{
    "response": "Perfect! I've got your name, email, and phone number. What's your company name?",
    "extracted": {
        "full_name": "Sarah Chen",
        "email_address": "sarah.chen@company.com", 
        "phone_number": "9876543210"
    },
    "confidence": {
        "full_name": 0.98,
        "email_address": 0.99,
        "phone_number": 0.97
    },
    "needs_confirmation": [],
    "reasoning": "Clear boundaries detected. Name stopped before 'and my email', email isolated between 'is' and 'and phone', phone number at end."
}

WRONG output (what NOT to do):
{
    "extracted": {
        "full_name": "Sarah Chen and my email"  // ❌ Crossed boundary!
    }
}

Remember: PRECISION over capture. When in doubt, extract less, ask more."""


# =============================================================================
# Intelligent Context Builder
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
        
        # 1. Current fields context (what we're asking about NOW)
        current_fields_info = []
        for field in current_batch:
            field_info = {
                'name': field.get('name'),
                'label': field.get('label', field.get('name')),
                'type': field.get('type', 'text'),
                'expected_format': SmartContextBuilder._get_expected_format(field)
            }
            current_fields_info.append(field_info)
        
        # 2. Remaining fields context (what's coming next - for boundary detection)
        upcoming_field_names = [
            f.get('label', f.get('name', '')) 
            for f in remaining_fields 
            if f not in current_batch
        ][:5]  # Next 5 fields
        
        # 3. Build session context additions
        context_notes = []
        if session_context:
            if session_context.get('is_voice'):
                context_notes.append("INPUT MODE: Voice (may have transcription errors)")
            if session_context.get('is_frustrated'):
                context_notes.append("USER STATE: Frustrated - be extra careful and helpful")
            if session_context.get('needs_clarity'):
                context_notes.append("USER STATE: Confused - extraction may need verification")
            if session_context.get('style') == 'concise':
                context_notes.append("USER STYLE: Prefers brief responses")
        
        context_note_str = "\n".join(context_notes) if context_notes else "Standard mode"
        
        # 4. Build smart context
        context = f"""EXTRACTION TASK:

USER INPUT: "{user_input}"

CONTEXT NOTES:
{context_note_str}

FIELDS TO EXTRACT (focus on these ONLY):
{json.dumps(current_fields_info, indent=2)}

ALREADY COLLECTED:
{json.dumps(already_extracted, indent=2) if already_extracted else "None yet"}

UPCOMING FIELDS (for boundary detection):
{json.dumps(upcoming_field_names, indent=2)}

EXTRACTION GUIDELINES FOR THIS INPUT:
1. Identify where each current field's value starts and ends
2. Stop extraction when you encounter:
   - Transition words: "and", "my", "also", "plus"
   - Mentions of upcoming field names: {', '.join(upcoming_field_names[:3])}
   - Natural sentence boundaries
3. Extract with surgical precision - less is more
4. Assign confidence based on boundary clarity

RECENT CONVERSATION:
{json.dumps(conversation_history[-4:], indent=2)}"""
        
        return context
    
    @staticmethod
    def _get_expected_format(field: Dict[str, Any]) -> str:
        """Describe expected format for field type."""
        field_type = field.get('type', 'text').lower()
        field_name = field.get('name', '').lower()
        field_label = field.get('label', '').lower()
        
        # Type-based expectations
        if field_type == 'email' or 'email' in field_name or 'email' in field_label:
            return "email format (user@domain.com), lowercase"
        elif field_type == 'tel' or 'phone' in field_name or 'mobile' in field_label:
            return "phone number (digits only, 10-15 characters)"
        elif 'name' in field_name or 'name' in field_label:
            return "person's name (2-4 words, alphabetic, title case)"
        elif field_type == 'number':
            return "numeric value"
        elif field_type == 'date':
            return "date (DD/MM/YYYY or similar)"
        elif field_type == 'url':
            return "website URL"
        else:
            return "text value"


# =============================================================================
# Enhanced Fallback with Smart Tokenization
# =============================================================================

class IntelligentFallbackExtractor:
    """
    Fallback extractor that uses NLP-inspired techniques without hardcoded patterns.
    Works by understanding sentence structure and field types dynamically.
    """
    
    @staticmethod
    def extract_with_intelligence(
        user_input: str,
        current_batch: List[Dict[str, Any]],
        remaining_fields: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, str], Dict[str, float]]:
        """
        Intelligent extraction using sentence segmentation and field type matching.
        
        Strategy:
        1. Split input into segments (by "and", "also", commas, etc.)
        2. For each segment, identify what field it's describing
        3. Extract the value portion from that segment
        4. Validate against field type expectations
        """
        
        extracted = {}
        confidence = {}
        
        # Step 1: Segment the input
        segments = IntelligentFallbackExtractor._segment_input(user_input)
        
        # Step 2: Create field matchers
        field_matchers = IntelligentFallbackExtractor._create_field_matchers(current_batch)
        
        # Step 3: Match segments to fields
        for segment in segments:
            segment_lower = segment.lower().strip()
            
            for field_info in field_matchers:
                if field_info['name'] in extracted:
                    continue  # Already extracted
                
                # Check if segment mentions this field
                if IntelligentFallbackExtractor._segment_mentions_field(segment_lower, field_info):
                    # Extract value from segment
                    value, conf = IntelligentFallbackExtractor._extract_value_from_segment(
                        segment, 
                        field_info
                    )
                    
                    if value:
                        extracted[field_info['name']] = value
                        confidence[field_info['name']] = conf
        
        return extracted, confidence
    
    @staticmethod
    def _segment_input(text: str) -> List[str]:
        """
        Split input into logical segments.
        Splits on: "and", "also", "plus", commas (smart comma detection)
        """
        # Replace common separators with a delimiter
        text = re.sub(r'\s+and\s+', ' |AND| ', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+also\s+', ' |AND| ', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+plus\s+', ' |AND| ', text, flags=re.IGNORECASE)
        
        # Smart comma handling (don't split within email addresses or names)
        # Only split on commas followed by field indicators
        text = re.sub(r',\s+(?=(?:my|the|and)\s)', ' |AND| ', text, flags=re.IGNORECASE)
        
        # Split and clean
        segments = [s.strip() for s in text.split('|AND|') if s.strip()]
        
        return segments
    
    @staticmethod
    def _create_field_matchers(fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create matcher objects for each field with metadata."""
        matchers = []
        
        for field in fields:
            field_name = field.get('name', '')
            field_label = field.get('label', field_name)
            field_type = field.get('type', 'text')
            
            # Extract keywords from label/name
            keywords = set()
            for word in (field_name + ' ' + field_label).lower().split():
                if len(word) > 2:  # Skip short words
                    keywords.add(word)
            
            matchers.append({
                'name': field_name,
                'label': field_label,
                'type': field_type,
                'keywords': keywords,
                'extractor': IntelligentFallbackExtractor._get_extractor_for_type(field_type, field_name, field_label)
            })
        
        return matchers
    
    @staticmethod
    def _get_extractor_for_type(field_type: str, field_name: str, field_label: str) -> Dict[str, Any]:
        """Get appropriate extractor configuration for field type."""
        field_type = field_type.lower()
        field_name_lower = field_name.lower()
        field_label_lower = field_label.lower()
        
        # Email detector
        if field_type == 'email' or 'email' in field_name_lower or 'email' in field_label_lower:
            return {
                'type': 'email',
                'pattern': r'[\w\.-]+@[\w\.-]+\.\w+',
                'normalizer': lambda x: x.lower().replace(' at ', '@').replace(' dot ', '.')
            }
        
        # Phone detector
        if field_type == 'tel' or any(k in field_name_lower for k in ['phone', 'mobile', 'tel']):
            return {
                'type': 'phone',
                'pattern': r'[\d\s\-\+\(\)]{10,}',
                'normalizer': lambda x: re.sub(r'[^\d+]', '', x)
            }
        
        # Name detector
        if 'name' in field_name_lower or 'name' in field_label_lower:
            return {
                'type': 'name',
                'pattern': r'\b[A-Z][a-z]+(?:\s+[A-Z]?[a-z]+){1,3}\b',
                'normalizer': lambda x: x.strip().title()
            }
        
        # Number detector
        if field_type == 'number':
            return {
                'type': 'number',
                'pattern': r'\d+(?:\.\d+)?',
                'normalizer': lambda x: x.strip()
            }
        
        # Generic text
        return {
            'type': 'text',
            'pattern': None,
            'normalizer': lambda x: x.strip()
        }
    
    @staticmethod
    def _segment_mentions_field(segment: str, field_info: Dict[str, Any]) -> bool:
        """Check if segment is talking about this field."""
        # Check if any field keyword appears in segment
        for keyword in field_info['keywords']:
            if keyword in segment:
                return True
        
        # Special patterns like "my X is", "the X is"
        label_pattern = rf'(?:my|the)\s+{re.escape(field_info["label"][:20])}'
        if re.search(label_pattern, segment, re.IGNORECASE):
            return True
        
        return False
    
    @staticmethod
    def _extract_value_from_segment(
        segment: str, 
        field_info: Dict[str, Any]
    ) -> Tuple[Optional[str], float]:
        """
        Extract actual value from a segment that mentions a field.
        
        Uses field-specific extractors and validates the result.
        """
        extractor = field_info['extractor']
        
        # 1. Try to extract using contextual patterns ("my X is Y")
        # This is prioritized because it handles "My Name Is..." boundaries better
        value_patterns = [
            rf'(?:my\s+)?{re.escape(field_info["label"][:20])}\s+(?:is|:)\s+(.+?)(?:\s+(?:and|my|the|also)|\s*$)',
            rf'{re.escape(field_info["label"][:20])}\s*[:=]\s*(.+?)(?:\s+(?:and|my|the)|\s*$)',
            rf'(?:my\s+)?{re.escape(field_info["name"][:20])}\s+(?:is|:)\s+(.+?)(?:\s+(?:and|my|the|also)|\s*$)',
        ]
        
        for pattern in value_patterns:
            match = re.search(pattern, segment, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                # Apply normalizer to just the value part
                value = extractor['normalizer'](value)
                
                is_valid, confidence = IntelligentFallbackExtractor._validate_extraction(
                    value,
                    extractor['type']
                )
                
                if is_valid:
                    # Higher confidence for explicit patterns
                    return value, confidence * 0.95

        # 2. Apply normalizer to handle speech-to-text quirks on whole segment
        normalized_segment = extractor['normalizer'](segment)
        
        # 3. Extract using generic pattern if available
        if extractor['pattern']:
            match = re.search(extractor['pattern'], normalized_segment)
            if match:
                value = match.group().strip()
                
                # For names, avoid "My Name Is" being captured if pattern matched early
                if extractor['type'] == 'name':
                     if value.lower().startswith('my name') or value.lower().startswith('my email'):
                         return None, 0.0

                # Validate extracted value
                is_valid, confidence = IntelligentFallbackExtractor._validate_extraction(
                    value, 
                    extractor['type']
                )
                
                if is_valid:
                    return value, confidence
        
        return None, 0.0
    
    @staticmethod
    def _validate_extraction(value: str, field_type: str) -> Tuple[bool, float]:
        """Validate extracted value against field type expectations."""
        if not value or len(value) < 2:
            return False, 0.0
        
        if field_type == 'email':
            # Must contain @, and have valid structure
            if '@' in value and '.' in value.split('@')[1]:
                return True, 0.95
            return False, 0.0
        
        elif field_type == 'phone':
            # Must be 10-15 digits
            digits = re.sub(r'[^\d]', '', value)
            if 10 <= len(digits) <= 15:
                return True, 0.92
            return False, 0.0
        
        elif field_type == 'name':
            # Must be 2-4 words, mostly alphabetic
            words = value.split()
            if 2 <= len(words) <= 4 and all(w.isalpha() for w in words):
                return True, 0.88
            elif len(words) >= 2:
                return True, 0.75
            return False, 0.0
        
        elif field_type == 'number':
            # Must be numeric
            try:
                float(value)
                return True, 0.95
            except ValueError:
                return False, 0.0
        
        else:  # text
            # Basic validation - has content, reasonable length
            if 2 <= len(value) <= 500:
                return True, 0.80
            return False, 0.0



class FieldClusterer:
    """Semantic field clustering for natural question batching."""
    
    # Field name patterns for clustering
    CLUSTERS = {
        'identity': [
            r'name', r'first.*name', r'last.*name', r'full.*name',
            r'email', r'mail', r'phone', r'mobile', r'tel'
        ],
        'professional': [
            r'experience', r'years', r'company', r'employer', r'organization',
            r'role', r'position', r'title', r'designation', r'job'
        ],
        'education': [
            r'degree', r'university', r'college', r'school', r'education',
            r'qualification', r'major', r'gpa', r'graduation'
        ],
        'location': [
            r'address', r'city', r'state', r'country', r'zip', r'postal',
            r'location', r'region'
        ],
        'preferences': [
            r'salary', r'expectation', r'start.*date', r'availability',
            r'notice.*period', r'remote', r'relocate'
        ],
        'documents': [
            r'resume', r'cv', r'cover.*letter', r'portfolio', r'attachment',
            r'upload', r'file'
        ]
    }
    
    # Max questions per batch based on field type (from constants)
    MAX_QUESTIONS = {
        'simple': BATCH_SIZE_SIMPLE,
        'moderate': BATCH_SIZE_MODERATE,
        'complex': BATCH_SIZE_COMPLEX,
    }
    
    SIMPLE_TYPES = SIMPLE_FIELD_TYPES
    MODERATE_TYPES = MODERATE_FIELD_TYPES
    COMPLEX_TYPES = COMPLEX_FIELD_TYPES
    
    def __init__(self):
        # Compile patterns for efficiency
        self._compiled_patterns = {
            cluster: [re.compile(p, re.IGNORECASE) for p in patterns]
            for cluster, patterns in self.CLUSTERS.items()
        }
    
    def get_field_cluster(self, field: Dict[str, Any]) -> str:
        """Determine which cluster a field belongs to."""
        field_name = (field.get('name', '') + ' ' + field.get('label', '')).lower()
        
        for cluster, patterns in self._compiled_patterns.items():
            if any(p.search(field_name) for p in patterns):
                return cluster
        
        return 'other'
    
    def get_field_complexity(self, field: Dict[str, Any]) -> str:
        """Determine field complexity for batching."""
        field_type = field.get('type', 'text').lower()
        
        if field_type in self.SIMPLE_TYPES:
            return 'simple'
        elif field_type in self.MODERATE_TYPES:
            return 'moderate'
        elif field_type in self.COMPLEX_TYPES:
            return 'complex'
        return 'simple'
    
    def create_batches(self, fields: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Create intelligent question batches from remaining fields.
        
        Groups fields by cluster and respects complexity limits.
        """
        if not fields:
            return []
        
        # Group by cluster
        clusters: Dict[str, List[Dict[str, Any]]] = {}
        for field in fields:
            cluster = self.get_field_cluster(field)
            if cluster not in clusters:
                clusters[cluster] = []
            clusters[cluster].append(field)
        
        # Create batches respecting complexity
        batches = []
        
        # Priority order for clusters
        priority = ['identity', 'professional', 'education', 'location', 'preferences', 'documents', 'other']
        
        for cluster in priority:
            if cluster not in clusters:
                continue
            
            cluster_fields = clusters[cluster]
            current_batch = []
            current_complexity = 'simple'
            
            for field in cluster_fields:
                complexity = self.get_field_complexity(field)
                max_size = self.MAX_QUESTIONS[complexity]
                
                # Complex fields go alone
                if complexity == 'complex':
                    if current_batch:
                        batches.append(current_batch)
                        current_batch = []
                    batches.append([field])
                    continue
                
                # Check if batch is full
                if len(current_batch) >= self.MAX_QUESTIONS[current_complexity]:
                    batches.append(current_batch)
                    current_batch = []
                
                current_batch.append(field)
                current_complexity = complexity
            
            if current_batch:
                batches.append(current_batch)
        
        return batches


# =============================================================================
# Conversation Agent
# =============================================================================

class ConversationAgent:
    """
    LangChain-powered conversational agent for form filling.
    
    Maintains conversation memory across turns and generates natural,
    batched questions for efficient form completion.
    """
    
    SYSTEM_PROMPT = IMPROVED_SYSTEM_PROMPT

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-flash", session_manager=None):
        """
        Initialize the conversation agent.
        
        Args:
            api_key: Google API key (falls back to env var)
            model: Gemini model to use
            session_manager: Optional SessionManager for Redis-backed persistence
        """
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        self.model_name = model
        self.session_manager = session_manager  # Redis-backed session storage
        self._local_sessions: Dict[str, ConversationSession] = {}  # Fallback cache
        self.input_mode_by_session: Dict[str, str] = {}  # Track input mode (voice/text)
        self.clusterer = FieldClusterer()
        
        if not self.api_key:
            logger.warning("Google API key not found - agent will use fallback mode")
            self.llm = None
        elif LANGCHAIN_AVAILABLE:
            self.llm = ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=self.api_key,
                temperature=0.3,  # Lower for more consistent outputs
                convert_system_message_to_human=True
            )
            logger.info(f"ConversationAgent initialized with {self.model_name}")
        else:
            self.llm = None
            logger.warning("LangChain not available - using fallback mode")
    
    async def create_session(
        self, 
        form_schema: List[Dict[str, Any]], 
        form_url: str = "",
        initial_data: Dict[str, str] = None
    ) -> ConversationSession:
        """
        Create a new conversation session.
        
        Args:
            form_schema: Parsed form schema from form parser
            form_url: URL of the form being filled
            initial_data: Any pre-filled data
            
        Returns:
            ConversationSession: New session object
            
        Raises:
            InputValidationError: If form_schema is invalid
        """
        # Validate form schema
        validate_form_schema(form_schema)
        
        session_id = str(uuid.uuid4())
        
        session = ConversationSession(
            id=session_id,
            form_schema=form_schema,
            form_url=form_url,
            extracted_fields=initial_data or {}
        )
        
        # Persist to Redis via SessionManager
        await self._save_session(session)
        logger.info(f"Created conversation session: {session_id}")
        
        return session
    
    async def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Retrieve an existing session from Redis or local cache."""
        # Try SessionManager first (Redis)
        if self.session_manager:
            try:
                data = await self.session_manager.get_session(session_id)
                if data:
                    session = ConversationSession.from_dict(data)
                    if session.is_expired():
                        await self.session_manager.delete_session(session_id)
                        return None
                    return session
            except Exception as e:
                logger.warning(f"SessionManager get failed: {e}")
        
        # Fallback to local cache
        session = self._local_sessions.get(session_id)
        if session and session.is_expired():
            logger.info(f"Session {session_id} expired, removing")
            del self._local_sessions[session_id]
            return None
        
        return session
    
    async def _save_session(self, session: ConversationSession) -> bool:
        """Save session to Redis via SessionManager, with local fallback."""
        if self.session_manager:
            try:
                await self.session_manager.save_session(session.to_dict())
                return True
            except Exception as e:
                logger.warning(f"SessionManager save failed, using local cache: {e}")
        
        # Fallback to local cache
        self._local_sessions[session.id] = session
        return True
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete session from storage."""
        if self.session_manager:
            try:
                await self.session_manager.delete_session(session_id)
            except Exception as e:
                logger.warning(f"SessionManager delete failed: {e}")
        
        self._local_sessions.pop(session_id, None)
        return True
    
    def _get_all_fields(self, form_schema: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract all fields from form schema."""
        all_fields = []
        for form in form_schema:
            all_fields.extend(form.get('fields', []))
        return all_fields
    
    def _detect_input_mode(self, metadata: Optional[Dict[str, Any]], session_id: str) -> bool:
        """
        Determine if the current input is voice-based.
        Updates and relies on session history.
        """
        # Check metadata first
        if metadata and metadata.get('input_mode'):
            mode = metadata.get('input_mode').lower()
            self.input_mode_by_session[session_id] = mode
            return mode == 'voice'
            
        # Check for specific voice indicators in metadata
        if metadata and (metadata.get('speech_confidence') or metadata.get('stt_provider')):
            self.input_mode_by_session[session_id] = 'voice'
            return True
            
        # Fallback to session history (default to text if unknown)
        last_mode = self.input_mode_by_session.get(session_id, 'text')
        return last_mode == 'voice'

    def _get_remaining_fields(self, session: ConversationSession) -> List[Dict[str, Any]]:
        """Get fields that haven't been filled or skipped yet."""
        all_fields = self._get_all_fields(session.form_schema)
        
        remaining = []
        for field in all_fields:
            field_name = field.get('name', '')
            if (field_name and 
                field_name not in session.extracted_fields and
                field_name not in session.skipped_fields and  # Exclude skipped fields
                not field.get('hidden', False) and
                field.get('type') not in ['submit', 'button', 'hidden']):
                remaining.append(field)
        
        return remaining
    
    def generate_initial_greeting(self, session: ConversationSession) -> AgentResponse:
        """
        Generate the initial greeting and first questions.
        
        Args:
            session: The conversation session
            
        Returns:
            AgentResponse with greeting and first batch of questions
        """
        remaining_fields = self._get_remaining_fields(session)
        
        if not remaining_fields:
            return AgentResponse(
                message="It looks like all the required information is already filled in! Would you like to review before submitting?",
                extracted_values={},
                confidence_scores={},
                needs_confirmation=[],
                remaining_fields=[],
                is_complete=True,
                next_questions=[]
            )
        
        # Get first batch of questions
        batches = self.clusterer.create_batches(remaining_fields)
        first_batch = batches[0] if batches else []
        
        # Generate natural greeting
        greeting = self._create_greeting(first_batch)
        
        session.current_question_batch = [f.get('name') for f in first_batch]
        session.conversation_history.append({
            'role': 'assistant',
            'content': greeting
        })
        
        return AgentResponse(
            message=greeting,
            extracted_values={},
            confidence_scores={},
            needs_confirmation=[],
            remaining_fields=remaining_fields,
            is_complete=False,
            next_questions=[{'name': f.get('name'), 'label': f.get('label'), 'type': f.get('type')} for f in first_batch]
        )
    
    def _create_greeting(self, first_batch: List[Dict[str, Any]]) -> str:
        """Create a natural greeting with first questions."""
        if not first_batch:
            return "Hello! I'm here to help you fill out this form. Let's get started!"
        
        if len(first_batch) == 1:
            field = first_batch[0]
            label = field.get('label', field.get('name', 'this field'))
            return f"Hi there! I'll help you fill out this form quickly. Let's start with your {label}."
        
        # Multiple fields - create natural batched question
        labels = [f.get('label', f.get('name', '')) for f in first_batch]
        
        if len(labels) == 2:
            return f"Hi! Let's get you started. What's your {labels[0]} and {labels[1]}?"
        else:
            all_but_last = ', '.join(labels[:-1])
            return f"Hello! I'll help you fill this out quickly. Can you tell me your {all_but_last}, and {labels[-1]}? You can say them all at once!"
    
    def _check_and_offer_fallback(
        self,
        session: ConversationSession,
        field: Dict[str, Any],
        is_voice: bool,
        remaining_fields: List[Dict[str, Any]]
    ) -> Optional[AgentResponse]:
        """
        Check if we should offer a fallback for voice input difficulties.
        
        Called when extraction fails for a voice input.
        Returns fallback response if threshold reached, None otherwise.
        """
        if not is_voice:
            return None
        
        field_name = field.get('name', '')
        field_type = field.get('type', 'text')
        
        # Increment attempt count
        session.field_attempt_counts[field_name] = session.field_attempt_counts.get(field_name, 0) + 1
        failure_count = session.field_attempt_counts[field_name]
        
        # For attempts 1-3, use ClarificationStrategy for escalating help
        if failure_count <= 3:
            clarification = ClarificationStrategy.get_clarification(
                field, failure_count, None  # last_input not needed for now
            )
            return AgentResponse(
                message=clarification,
                extracted_values={},
                confidence_scores={},
                needs_confirmation=[],
                remaining_fields=remaining_fields,
                is_complete=False,
                next_questions=[{'name': field.get('name'), 'label': field.get('label'), 'type': field.get('type')}],
                fallback_options=[]
            )
        
        # After 3 failed clarifications, offer multi-modal fallback
        if MultiModalFallback.should_offer_fallback(field_name, field_type, failure_count):
            fallback = MultiModalFallback.generate_fallback_response(field_name)
            
            return AgentResponse(
                message=fallback['message'],
                extracted_values={},
                confidence_scores={},
                needs_confirmation=[],
                remaining_fields=remaining_fields,
                is_complete=False,
                next_questions=[{'name': field.get('name'), 'label': field.get('label'), 'type': field.get('type')}],
                fallback_options=fallback.get('options', [])
            )
        
        return None
    
    def _detect_user_style(self, user_input: str, session: ConversationSession) -> None:
        """
        Detect and update user preference style from input patterns.
        
        Called early in process_user_input to learn user preferences.
        """
        words = user_input.split()
        lower = user_input.lower()
        
        # Very short, direct answers suggest concise preference
        if len(words) <= 3 and not any(w in lower for w in ['please', 'could', 'would']):
            if session.conversation_context.user_preference_style == 'balanced':
                session.conversation_context.user_preference_style = 'concise'
        
        # Polite language suggests formal preference
        elif any(w in lower for w in ['please', 'thank you', 'would you', 'could you']):
            session.conversation_context.user_preference_style = 'formal'
        
        # Casual markers
        elif any(w in lower for w in ['hey', 'yo', 'cool', 'sure', 'yep', 'nope', 'yeah']):
            session.conversation_context.user_preference_style = 'casual'
        
        # Long, detailed responses suggest detailed preference
        elif len(words) > 15:
            session.conversation_context.user_preference_style = 'detailed'
    
    def _adapt_response(self, message: str, session: ConversationSession) -> str:
        """
        Adapt response message based on user preference style.
        
        Args:
            message: Original response message
            session: Session with conversation context
            
        Returns:
            Style-adapted message
        """
        style = session.conversation_context.user_preference_style
        
        if style == 'concise':
            return self._make_concise(message)
        elif style == 'casual':
            return self._make_casual(message)
        elif style == 'formal':
            return self._make_formal(message)
        # 'detailed' or 'balanced' - keep original
        return message
    
    def _make_concise(self, message: str) -> str:
        """Shorten message for concise preference users."""
        # Remove filler phrases
        fillers = [
            "I'd be happy to help with that. ",
            "Let me help you with that. ",
            "Perfect! ",
            "Great! ",
            "Awesome! ",
            "Wonderful! ",
            "That's great. ",
            "Thank you for that. ",
        ]
        result = message
        for filler in fillers:
            result = result.replace(filler, "")
        
        # Shorten common phrases
        replacements = [
            ("Could you please provide", "What's"),
            ("Would you mind telling me", "What's"),
            ("Can you tell me", "What's"),
            ("I've recorded your", "Got"),
            ("I've saved your", "Got"),
            ("What would you like to enter instead?", "New value?"),
        ]
        for old, new in replacements:
            result = result.replace(old, new)
        
        return result.strip()
    
    def _make_casual(self, message: str) -> str:
        """Add casual tone for casual preference users."""
        replacements = [
            ("Thank you", "Thanks"),
            ("I have recorded", "Got"),
            ("Could you please", "Can you"),
            ("Would you mind", "Could you"),
            ("What is your", "What's your"),
            ("I would", "I'd"),
        ]
        result = message
        for old, new in replacements:
            result = result.replace(old, new)
        return result
    
    def _make_formal(self, message: str) -> str:
        """Add formal tone for formal preference users."""
        replacements = [
            ("Got it", "Thank you"),
            ("Thanks", "Thank you"),
            ("What's", "What is"),
            ("I'd", "I would"),
            ("don't", "do not"),
            ("can't", "cannot"),
        ]
        result = message
        for old, new in replacements:
            result = result.replace(old, new)
        return result
    
    async def process_user_input(
        self, 
        session_id: str, 
        user_input: str,
        input_metadata: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Process user input with enhanced conversational intelligence.
        
        Handles:
        - Voice normalization and context
        - Intent recognition (corrections, help, status, skip, undo)
        - Context tracking (sentiment, confusion)
        - Adaptive response generation
        - Progress updates
        
        Args:
            session_id: The session ID
            user_input: What the user said
            input_metadata: Optional metadata (input_mode, stt_confidence, etc.)
            
        Returns:
            AgentResponse with extracted values and next questions
        """
        session = await self.get_session(session_id)
        if not session:
            raise AIServiceError(
                message="Session not found or expired",
                status_code=404,
                details={"session_id": session_id}
            )
        
        session.update_activity()
        
        # --- VOICE PROCESSING INTEGRATION ---
        
        # Detect input mode
        is_voice = self._detect_input_mode(input_metadata, session_id)
        stt_confidence = input_metadata.get('stt_confidence', 1.0) if input_metadata else 1.0
        
        # Get context for processing
        remaining_fields = self._get_remaining_fields(session)
        current_batch = [
            f for f in remaining_fields 
            if f.get('name') in session.current_question_batch
        ]
        
        # CRITICAL FIX: If current_batch is empty but we have remaining fields,
        # populate the batch so extraction can work
        if not current_batch and remaining_fields:
            batches = self.clusterer.create_batches(remaining_fields)
            if batches:
                current_batch = batches[0]
                session.current_question_batch = [f.get('name') for f in current_batch]
                logger.debug(f"Auto-populated empty batch with: {session.current_question_batch}")
        
        # Apply voice normalization if voice input
        if is_voice and current_batch:
            expected_type = current_batch[0].get('type')
            
            # Build simple context for normalization
            norm_context = {
                'country': session.extracted_fields.get('country'),
                'company': session.extracted_fields.get('company'),
            }
            
            original_input = user_input
            user_input = VoiceInputProcessor.normalize_voice_input(
                user_input,
                expected_field_type=expected_type,
                context=norm_context
            )
            
            if original_input != user_input:
                logger.info(f"Voice normalized: '{original_input}' -> '{user_input}'")
        
        # Audio quality assessment for voice input
        audio_quality_hint = None
        if is_voice and stt_confidence < 0.9 and current_batch:
            audio_quality = NoiseHandler.assess_audio_quality(stt_confidence)
            field = current_batch[0]
            is_critical = field.get('type') in ['email', 'tel']
            
            audio_quality_hint = NoiseHandler.get_quality_adapted_response(
                audio_quality, field.get('type', 'text'), is_critical
            )
            if audio_quality_hint:
                logger.info(f"Audio quality: {audio_quality.value}, adding hint")
        
        # --- INTENT RECOGNITION ---
        
        # Detect user style from input patterns
        self._detect_user_style(user_input, session)
        
        # Detect user intent
        intent_recognizer = IntentRecognizer()
        intent, intent_confidence = intent_recognizer.detect_intent(user_input)
        
        # CRITICAL FIX: Confidence threshold check
        if intent and intent_confidence < 0.70:
            logger.debug(f"Low intent confidence ({intent_confidence:.2f}), treating as DATA")
            intent = UserIntent.DATA
        
        logger.info(f"Detected intent: {intent} (confidence: {intent_confidence:.2f})")
        
        # Update conversation context with sentiment analysis
        session.conversation_context.update_from_input(user_input)
        session.conversation_context.last_intent = intent
        
        total_fields = session.get_total_field_count()
        extracted_count = len(session.extracted_fields)
        
        # --- HANDLE SPECIAL INTENTS BEFORE EXTRACTION ---
        
        # Handle UNDO intent
        if intent == UserIntent.UNDO or intent == UserIntent.BACK:
            return await self._handle_undo(session)
        
        # Handle CORRECTION intent
        if intent == UserIntent.CORRECTION:
            correction_result = await self._handle_correction(session, user_input)
            if correction_result:
                return correction_result
        
        # Handle STATUS intent
        if intent == UserIntent.STATUS:
            status_msg = ProgressTracker.get_status_message(extracted_count, total_fields)
            return AgentResponse(
                message=status_msg,
                extracted_values={},
                confidence_scores={},
                needs_confirmation=[],
                remaining_fields=remaining_fields,
                is_complete=len(remaining_fields) == 0,
                next_questions=[]
            )
        
        # Handle HELP intent
        if intent == UserIntent.HELP:
            help_msg = self._generate_help_message(current_batch)
            return AgentResponse(
                message=help_msg,
                extracted_values={},
                confidence_scores={},
                needs_confirmation=[],
                remaining_fields=remaining_fields,
                is_complete=False,
                next_questions=[{'name': f.get('name'), 'label': f.get('label'), 'type': f.get('type')} for f in current_batch]
            )
        
        # Handle SKIP intent
        if intent == UserIntent.SKIP and current_batch:
            return await self._handle_skip(session, current_batch)
        
        # Handle SMALL_TALK intent
        if intent == UserIntent.SMALL_TALK:
            small_talk_msg = AdaptiveResponseGenerator._handle_small_talk(extracted_count, len(remaining_fields))
            return AgentResponse(
                message=small_talk_msg,
                extracted_values={},
                confidence_scores={},
                needs_confirmation=[],
                remaining_fields=remaining_fields,
                is_complete=len(remaining_fields) == 0,
                next_questions=[{'name': f.get('name'), 'label': f.get('label'), 'type': f.get('type')} for f in current_batch]
            )
        
        # --- REGULAR EXTRACTION PROCESSING ---
        
        # Add to conversation history with intent metadata
        session.conversation_history.append({
            'role': 'user',
            'content': user_input,
            'intent': intent.value if intent else None,
            'sentiment': session.conversation_context.user_sentiment.value
        })
        
        # Process with LLM or fallback
        logger.info(f"Processing input: '{sanitize_for_log(user_input[:100])}...'")
        logger.info(f"Current batch fields: {[f.get('name') for f in current_batch]}")
        logger.info(f"Remaining fields: {[f.get('name') for f in remaining_fields]}")
        logger.info(f"LLM available: {self.llm is not None}, LangChain: {LANGCHAIN_AVAILABLE}")
        
        if self.llm and LANGCHAIN_AVAILABLE:
            logger.info("Using LLM for extraction...")
            result = await self._process_with_llm(session, user_input, current_batch, remaining_fields)
            logger.info(f"LLM extraction result: {len(result.extracted_values)} values extracted")
            logger.info(f"Extracted values: {result.extracted_values}")
        else:
            logger.info("Using FALLBACK extraction (LLM not available)...")
            result = self._process_with_fallback(session, user_input, current_batch, remaining_fields)
            logger.info(f"Fallback extraction result: {len(result.extracted_values)} values extracted")
            logger.info(f"Extracted values: {result.extracted_values}")
        
        # Update session with extracted values (REFINED)
        refined_values = self._refine_extracted_values(result.extracted_values, current_batch)
        for field_name, value in refined_values.items():
            if field_name not in result.needs_confirmation:
                # Add to undo stack before updating
                session.undo_stack.append({
                    'field_name': field_name,
                    'value': value,
                    'timestamp': datetime.now().isoformat()
                })
                session.extracted_fields[field_name] = value
                session.confidence_scores[field_name] = result.confidence_scores.get(field_name, 1.0)
        
        result.extracted_values = refined_values
        
        # --- METRICS LOGGING ---
        # Log extraction metrics for data-driven tuning
        for field_name in refined_values.keys():
            correction_count = session.conversation_context.repeated_corrections.get(field_name, 0)
            logger.info(f"METRICS: field={field_name}, corrections={correction_count}, confusion={session.conversation_context.confusion_count}")
        
        # Generate adaptive response
        new_remaining = self._get_remaining_fields(session)
        new_extracted_count = len(session.extracted_fields)
        
        adaptive_message = AdaptiveResponseGenerator.generate_response(
            extracted_values=result.extracted_values,
            remaining_fields=new_remaining,
            context=session.conversation_context,
            current_batch=current_batch,
            user_intent=intent,
            extracted_count=new_extracted_count,
            total_count=total_fields
        )
        
        # Add progress milestone if appropriate
        if ProgressTracker.should_show_progress(new_extracted_count):
            milestone = ProgressTracker.get_milestone_message(new_extracted_count, total_fields, include_count=False)
            if milestone:
                adaptive_message = f"{milestone} {adaptive_message}"
        
        # Apply style adaptation based on user preference
        adaptive_message = self._adapt_response(adaptive_message, session)
        
        result.message = adaptive_message
        
        # Add to history
        session.conversation_history.append({
            'role': 'assistant', 
            'content': result.message
        })
        
        # Prepare next batch if needed
        if not result.is_complete:
            batches = self.clusterer.create_batches(new_remaining)
            if batches:
                session.current_question_batch = [f.get('name') for f in batches[0]]
                result.next_questions = [{'name': f.get('name'), 'label': f.get('label'), 'type': f.get('type')} for f in batches[0]]
            result.remaining_fields = new_remaining
            result.is_complete = len(new_remaining) == 0
        
        # Persist session changes
        await self._save_session(session)
        
        logger.info(f"Session {session_id}: Extracted {len(result.extracted_values)} values, {len(result.remaining_fields)} remaining")
        
        return result
    
    # Maximum undo stack size to prevent memory issues
    MAX_UNDO_STACK_SIZE = 20
    
    def _parse_undo_command(
        self, 
        user_input: str, 
        session: ConversationSession
    ) -> Tuple[str, Any]:
        """
        Parse undo command to determine target.
        
        Returns:
            Tuple of (undo_type, target):
            - ('last', 1) - default undo last
            - ('last', N) - undo last N items
            - ('field', field_name) - undo specific field
        """
        lower = user_input.lower().strip()
        
        # Check for count: "undo last 3", "undo 2", "undo the last two"
        count_match = re.search(r'undo\s+(?:the\s+)?(?:last\s+)?(\d+)', lower)
        if count_match:
            return ('last', min(int(count_match.group(1)), len(session.undo_stack)))
        
        # Word numbers
        word_numbers = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5}
        for word, num in word_numbers.items():
            if f'undo {word}' in lower or f'undo last {word}' in lower:
                return ('last', min(num, len(session.undo_stack)))
        
        # Check for field name: "undo email", "undo my name", "undo the phone"
        field_words = lower.replace('undo', '').replace('the', '').replace('my', '').strip()
        if field_words:
            matched = self._fuzzy_match_field(
                field_words, 
                list(session.extracted_fields.keys()), 
                session
            )
            if matched:
                return ('field', matched)
        
        # Default: undo last 1
        return ('last', 1)
    
    async def _handle_undo(
        self, 
        session: ConversationSession,
        user_input: str = ""
    ) -> AgentResponse:
        """
        Handle undo/back request with smart parsing.
        
        Supports:
        - "undo" / "go back" - undo last action
        - "undo email" / "undo my name" - undo specific field
        - "undo last 3" / "undo two" - undo multiple actions
        """
        if not session.undo_stack:
            return AgentResponse(
                message="There's nothing to undo right now. Let's continue!",
                extracted_values={},
                confidence_scores={},
                needs_confirmation=[],
                remaining_fields=self._get_remaining_fields(session),
                is_complete=False,
                next_questions=[]
            )
        
        # Parse undo command
        undo_type, target = self._parse_undo_command(user_input, session)
        
        undone_fields = []
        
        if undo_type == 'field':
            # Undo specific field
            field_name = target
            
            # Find and remove from undo stack
            for i, action in enumerate(session.undo_stack):
                if action.get('field_name') == field_name:
                    session.undo_stack.pop(i)
                    break
            
            # Remove from extracted fields
            if field_name in session.extracted_fields:
                del session.extracted_fields[field_name]
                undone_fields.append(field_name)
            if field_name in session.confidence_scores:
                del session.confidence_scores[field_name]
                
        else:
            # Undo last N actions
            count = target
            for _ in range(count):
                if not session.undo_stack:
                    break
                    
                last_action = session.undo_stack.pop()
                field_name = last_action.get('field_name')
                
                if field_name in session.extracted_fields:
                    del session.extracted_fields[field_name]
                    undone_fields.append(field_name)
                if field_name in session.confidence_scores:
                    del session.confidence_scores[field_name]
        
        await self._save_session(session)
        
        # Build friendly message
        remaining = self._get_remaining_fields(session)
        
        if len(undone_fields) == 1:
            field_label = self._get_field_label(session, undone_fields[0])
            message = f"Okay, I've removed your {field_label}. What would you like to enter instead?"
        elif len(undone_fields) > 1:
            labels = [self._get_field_label(session, f) for f in undone_fields]
            message = f"Done! I've removed {', '.join(labels)}. Let's re-enter those."
        else:
            message = "I couldn't find that to undo. What would you like to do?"
        
        return AgentResponse(
            message=message,
            extracted_values={},
            confidence_scores={},
            needs_confirmation=[],
            remaining_fields=remaining,
            is_complete=False,
            next_questions=[{'name': f.get('name'), 'label': f.get('label'), 'type': f.get('type')} for f in remaining[:1]]
        )
    
    async def _handle_correction(
        self, 
        session: ConversationSession, 
        user_input: str
    ) -> Optional[AgentResponse]:
        """Handle correction request."""
        intent_recognizer = IntentRecognizer()
        correction_info = intent_recognizer.extract_correction_info(user_input)
        
        is_voice = self.input_mode_by_session.get(session.id, 'text') == 'voice'
        field_identifier = None
        new_value_raw = user_input
        
        if correction_info:
            field_identifier, new_value_raw = correction_info
            
        # Fallback manual extraction if intent recognizer failed
        user_lower = user_input.lower()
        if not field_identifier:
            if 'correction for' in user_lower or 'correction to' in user_lower:
                parts = re.split(r'correction (?:for|to)', user_lower)
                if len(parts) > 1:
                    potential_field = parts[1].split()[0] # Take first word as field identifier
                    field_identifier = potential_field.strip()
        
        # Identify field using improved fuzzy matcher
        extracted_fields = list(session.extracted_fields.keys())
        matched_field = self._fuzzy_match_field(field_identifier, extracted_fields, session)
            
        if not matched_field:
            # Try matching remaining fields too, maybe they want to correct logic flow
            remaining = [f.get('name') for f in self._get_remaining_fields(session)]
            matched_field = self._fuzzy_match_field(field_identifier, remaining, session)
            
        if not matched_field:
            logger.warning(f"Could not identify field for correction: {user_input}")
            return AgentResponse(
                message="I'm not sure which field you want to correct. Could you say corrections like 'Change email to...'?",
                extracted_values={},
                confidence_scores={},
                needs_confirmation=[],
                remaining_fields=self._get_remaining_fields(session),
                is_complete=False,
                next_questions=[]
            )
            
        # Extract new value - simple heuristic for now (everything after field name/indicator)
        # TODO: Use intelligent extractor here for better value isolation
        new_value_raw = user_input
        # Remove "correction to/for [field]" part to get value
        indicators = [f"correction for {field_identifier}", f"correction to {field_identifier}", 
                      f"change {field_identifier} to", f"correct {field_identifier} to",
                      f"{field_identifier} is", f"{field_identifier} should be"]
                      
        for ind in indicators:
            if ind in user_lower:
                idx = user_lower.find(ind)
                if idx != -1:
                    new_value_raw = user_input[idx + len(ind):].strip()
                    break
        
        # Clean value
        new_value = new_value_raw.strip(' :.')
        
        # Normalize if voice
        if is_voice:
             # Find field type
             field_type = 'text'
             for f in session.form_schema:
                 if f.get('name') == matched_field:
                     field_type = f.get('type', 'text')
                     break
                     
             new_value = VoiceInputProcessor.normalize_voice_input(new_value, field_type)
             
             # Learn from this correction
             original_value = session.extracted_fields.get(matched_field)
             if original_value:
                 VoiceInputProcessor.learn_from_correction(original_value, new_value, matched_field)
        
        # Record correction
        old_value = session.extracted_fields.get(matched_field) # Use .get to avoid KeyError if field was not previously extracted
        session.correction_history.append({
            'field_name': matched_field,
            'original_value': old_value,
            'corrected_value': new_value,
            'timestamp': datetime.now().isoformat(),
        })
        session.conversation_context.record_correction(matched_field)  # Track correction context
        logger.info(f"Corrected field {matched_field}: '{new_value}'")
        
        # Refine updated value
        refined = self._refine_extracted_values({matched_field: new_value}, [{'name': matched_field, 'type': 'text'}])
        new_value = refined.get(matched_field, new_value)
        session.extracted_fields[matched_field] = new_value
        
        await self._save_session(session)
        
        return AgentResponse(
            message=f"Got it! I've updated your {matched_field} to '{new_value}'. Let's continue.",
            extracted_values={matched_field: new_value},
            confidence_scores={matched_field: 1.0},
            needs_confirmation=[],
            remaining_fields=self._get_remaining_fields(session),
            is_complete=False,
            next_questions=[]
        )
    
    async def _handle_skip(
        self, 
        session: ConversationSession, 
        current_batch: List[Dict[str, Any]]
    ) -> AgentResponse:
        """Handle skip request for current batch."""
        logger.info(f"Skip command for fields: {[f.get('name') for f in current_batch]}")
        
        # Add skipped fields
        skipped_names = [f.get('name') for f in current_batch if f.get('name')]
        session.skipped_fields.extend(skipped_names)
        
        # Get new remaining
        new_remaining = self._get_remaining_fields(session)
        
        # Prepare next batch
        batches = self.clusterer.create_batches(new_remaining)
        if batches:
            next_batch = batches[0]
            session.current_question_batch = [f.get('name') for f in next_batch]
            next_labels = [f.get('label', f.get('name', '')) for f in next_batch[:3]]
            if len(next_labels) > 1:
                next_q = ', '.join(next_labels[:-1]) + f" and {next_labels[-1]}"
            else:
                next_q = next_labels[0] if next_labels else ""
            message = f"No problem, I'll skip that. What's your {next_q}?"
            next_questions = [{'name': f.get('name'), 'label': f.get('label'), 'type': f.get('type')} for f in next_batch]
        else:
            message = PersonalityConfig.get_completion_message()
            next_questions = []
        
        await self._save_session(session)
        
        return AgentResponse(
            message=message,
            extracted_values={},
            confidence_scores={},
            needs_confirmation=[],
            remaining_fields=new_remaining,
            is_complete=len(new_remaining) == 0,
            next_questions=next_questions
        )
    
    def _generate_help_message(self, current_batch: List[Dict[str, Any]]) -> str:
        """Generate contextual help message."""
        if not current_batch:
            return "Just answer naturally! For example, you can say 'My name is John' or give multiple answers at once like 'My name is John and my email is john@example.com'"
        
        field = current_batch[0]
        label = field.get('label', field.get('name', 'information'))
        field_type = field.get('type', 'text').lower()
        
        examples = {
            'email': f"For {label}, say something like 'My email is sarah@example.com' or just 'sarah@example.com'",
            'tel': f"For {label}, just say your number like '555-123-4567' or 'My phone is 555-123-4567'",
            'text': f"For {label}, you can say '{label}: your value' or just tell me directly",
        }
        
        if 'name' in label.lower():
            return f"For {label}, you can say 'John Smith' or 'My name is John Smith'"
        
        return examples.get(field_type, 
            f"For {label}, just tell me naturally. You can say 'My {label} is ...' or provide multiple answers at once!"
        )
    
    async def _process_with_llm(
        self,
        session: ConversationSession,
        user_input: str,
        current_batch: List[Dict[str, Any]],
        remaining_fields: List[Dict[str, Any]]
    ) -> AgentResponse:
        """
        Process input using LangChain LLM with Smart Context.
        
        Uses async invocation with exponential backoff retry for resilience.
        """
        try:
            # Build intelligent context
            context = SmartContextBuilder.build_extraction_context(
                current_batch=current_batch,
                remaining_fields=remaining_fields,
                user_input=user_input,
                conversation_history=session.conversation_history,
                already_extracted=session.extracted_fields
            )
            
            messages = [
                SystemMessage(content=IMPROVED_SYSTEM_PROMPT),
                HumanMessage(content=context)
            ]
            
            # Use async invoke with retry
            response = await self._invoke_with_retry(messages)
            log_api_call("LangChain-Gemini", "ainvoke", success=True)
            
            return self._parse_llm_response(response.content, remaining_fields, session)
            
        except Exception as e:
            logger.error(f"LLM processing error: {e}")
            log_api_call("LangChain-Gemini", "ainvoke", success=False, error=str(e))
            return self._process_with_fallback(session, user_input, current_batch, remaining_fields)
    
    async def _invoke_with_retry(self, messages: List[Any]) -> Any:
        """
        Invoke LLM with exponential backoff retry.
        
        Args:
            messages: List of LangChain messages
            
        Returns:
            LLM response
            
        Raises:
            Exception: If all retries fail
        """
        last_error = None
        delay = LLM_RETRY_BASE_DELAY
        
        for attempt in range(LLM_MAX_RETRIES):
            try:
                # Use async invoke if available, otherwise fallback to sync
                if hasattr(self.llm, 'ainvoke'):
                    response = await self.llm.ainvoke(messages)
                else:
                    # Fallback to sync in thread pool
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None, 
                        lambda: self.llm.invoke(messages)
                    )
                return response
                
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # Check if error is retryable
                retryable = any(keyword in error_str for keyword in [
                    'rate limit', 'quota', 'timeout', 'connection',
                    'temporary', '429', '503', '502', 'overloaded'
                ])
                
                if not retryable or attempt == LLM_MAX_RETRIES - 1:
                    raise
                
                logger.warning(
                    f"LLM call failed (attempt {attempt + 1}/{LLM_MAX_RETRIES}), "
                    f"retrying in {delay:.1f}s: {e}"
                )
                
                await asyncio.sleep(delay)
                delay = min(delay * 2, LLM_RETRY_MAX_DELAY)
        
        raise last_error
    
    def _build_context(
        self,
        session: ConversationSession,
        current_batch: List[Dict[str, Any]],
        remaining_fields: List[Dict[str, Any]]
    ) -> str:
        """Build context message for LLM."""
        context = f"""FORM CONTEXT:
Already collected: {json.dumps(session.extracted_fields, indent=2)}

CURRENT QUESTIONS (extract values for these):
{json.dumps([{'name': f.get('name'), 'label': f.get('label'), 'type': f.get('type')} for f in current_batch], indent=2)}

ALL REMAINING FIELDS:
{json.dumps([{'name': f.get('name'), 'label': f.get('label'), 'type': f.get('type')} for f in remaining_fields[:10]], indent=2)}

CONVERSATION HISTORY (last 4 turns):
{json.dumps(session.conversation_history[-8:], indent=2)}"""
        
        return context
    
    def _should_confirm(
        self,
        field_name: str,
        value: str,
        confidence: float,
        session: Optional[ConversationSession] = None
    ) -> bool:
        """
        Determine if a value needs confirmation using the ConfidenceCalibrator.
        """
        if not value:
            return False
            
        # Get field definition
        field_def = None
        if session:
            for f in session.form_schema:
                if f.get('name') == field_name:
                    field_def = f
                    break
        
        if not field_def:
            field_def = {'name': field_name, 'type': 'text'}
            
        # Use simple threshold if no session/calibrator
        if not session:
            return confidence < CONFIDENCE_THRESHOLD_MEDIUM
            
        # Get additional context for calibration
        stt_conf = 1.0  # Default if not available
        is_voice = self.input_mode_by_session.get(session.id, 'text') == 'voice'
        
        return ConfidenceCalibrator.should_confirm(
            field=field_def,
            confidence=confidence,
            context=session.conversation_context,
            stt_confidence=stt_conf,
            is_voice=is_voice
        )

    def _parse_llm_response(
        self, 
        response_text: str,
        remaining_fields: List[Dict[str, Any]],
        session: Optional[ConversationSession] = None
    ) -> AgentResponse:
        """Parse LLM response JSON."""
        try:
            # Clean up response text (remove markdown code blocks if present)
            clean_text = response_text.replace('```json', '').replace('```', '').strip()
            data = json.loads(clean_text)
            
            # Extract basic fields
            extracted = data.get('extracted', {})
            confidence_scores = data.get('confidence', {})
            
            # Determine confirmation needs
            needs_confirmation = []
            final_extracted = {}
            final_confidence = {}
            
            for field, value in extracted.items():
                score = float(confidence_scores.get(field, 1.0))
                
                # Check if we should confirm this value
                if self._should_confirm(field, value, score, session):
                    needs_confirmation.append(field)
                    logger.info(f"Field {field} needs confirmation (conf: {score:.2f})")
                else:
                    final_extracted[field] = value
                    final_confidence[field] = score
            
            return AgentResponse(
                message=data.get('message', "I understood that."),
                extracted_values=final_extracted,
                confidence_scores=final_confidence,
                needs_confirmation=needs_confirmation,
                remaining_fields=remaining_fields,
                is_complete=len(remaining_fields) == len(final_extracted),
                next_questions=[]
            )
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse LLM response: {response_text[:100]}...")
            raise
    
    def _process_with_fallback(
        self,
        session: ConversationSession,
        user_input: str,
        current_batch: List[Dict[str, Any]],
        remaining_fields: List[Dict[str, Any]]
    ) -> AgentResponse:
        """Fallback processing without LLM - uses intelligent extraction."""
        
        # Use intelligent fallback extractor
        extracted, confidence = IntelligentFallbackExtractor.extract_with_intelligence(
            user_input=user_input,
            current_batch=current_batch,
            remaining_fields=remaining_fields
        )
        
        logger.info(f"Intelligent fallback extraction: {extracted}")
        
        # Generate response
        if extracted:
            remaining_count = len(remaining_fields) - len(extracted)
            
            if remaining_count > 0:
                batches = self.clusterer.create_batches(
                    [f for f in remaining_fields if f.get('name') not in extracted]
                )
                if batches:
                    next_labels = [f.get('label', f.get('name', '')) for f in batches[0][:3]]
                    if len(next_labels) > 1:
                        next_q = ', '.join(next_labels[:-1]) + f" and {next_labels[-1]}"
                    else:
                        next_q = next_labels[0] if next_labels else ""
                    
                    got_fields = [f.get('label', f.get('name', '')) for f in current_batch if f.get('name') in extracted]
                    ack = f"Got your {', '.join(got_fields[:2])}!" if got_fields else "Thanks!"
                    message = f"{ack} What's your {next_q}?"
                    next_questions = [{'name': f.get('name'), 'label': f.get('label'), 'type': f.get('type')} for f in batches[0]]
                else:
                    message = "Perfect! Let me check what else we need."
                    next_questions = []
            else:
                message = "Excellent! I have everything needed. Ready to fill the form?"
                next_questions = []
        else:
            # Provide helpful example based on current fields
            field_examples = []
            for field in current_batch[:2]:
                label = field.get('label', field.get('name', 'field'))
                if 'name' in label.lower():
                    field_examples.append(f"my name is John Doe")
                elif 'email' in label.lower():
                    field_examples.append(f"my email is john@example.com")
                else:
                    field_examples.append(f"my {label.lower()} is ...")
            
            example = ' and '.join(field_examples) if field_examples else "your name and email"
            message = f"I didn't catch that. Could you say something like: '{example}'?"
            next_questions = []
        
        return AgentResponse(
            message=message,
            extracted_values=extracted,
            confidence_scores=confidence,
            needs_confirmation=[k for k, v in confidence.items() if v < 0.7],
            remaining_fields=[f for f in remaining_fields if f.get('name') not in extracted],
            is_complete=len(remaining_fields) == len(extracted) and len(extracted) > 0,
            next_questions=next_questions
        )
    
    def _clean_name_value(self, raw_name: str) -> str:
        """
        Clean extracted name value by removing transition phrases and stop words.
        This is critical for fixing cases like "John Doe And My Email" -> "John Doe"
        """
        if not raw_name or not raw_name.strip():
            return raw_name
        
        cleaned = raw_name.strip()
        
        # 1. Remove common transition phrases
        transition_patterns = [
            r'\s+and\s+my\s+.*$',  # "and my email...", "and my phone..."
            r'\s+and\s+(?:the|this|that)\s+.*$',  # "and the...", "and this..."
            r'\s+my\s+(?:email|phone|mobile|address|number)\s*.*$',  # "my email..."
            r'\s+@\s*.*$',  # starting an email
            r'\s+\d{3,}.*$',  # starting a phone number
            r'\s+(?:email|phone|mobile|address)\s*(?:is|:)?\s*.*$',  # "email is..."
        ]
        for pattern in transition_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # 2. Remove trailing common words that aren't part of names
        stop_words = {'and', 'or', 'the', 'my', 'is', 'are', 'at', 'to', 'for', 
                      'email', 'phone', 'mobile', 'number', 'address', 'name'}
        words = cleaned.split()
        while words and words[-1].lower() in stop_words:
            words.pop()
        
        # 3. Also remove leading stop words like "my name is"
        while words and words[0].lower() in stop_words:
            words.pop(0)
        
        cleaned = ' '.join(words)
        
        # 4. Title case for names
        return cleaned.strip().title() if cleaned else raw_name
        return cleaned.strip().title() if cleaned else raw_name
    
    def _get_field_label(self, session: ConversationSession, field_name: str) -> str:
        """Get human-readable label for a field."""
        for field in session.form_schema:
            if field.get('name') == field_name:
                return field.get('label', field_name)
        return field_name
        
    def _fuzzy_match_field(
        self, 
        user_input: str, 
        fields: List[str], 
        session: Optional[ConversationSession] = None
    ) -> Optional[str]:
        """
        Match user input to a field name using fuzzy and phonetic matching.
        """
        # 1. Direct substring match (legacy behavior, but case-insensitive)
        user_lower = user_input.lower()
        for field in fields:
            if field.lower() in user_lower:
                return field
                
        # 2. Match against labels if session available
        if session:
            for field in session.form_schema:
                name = field.get('name', '')
                if not name or name not in fields:
                    continue
                    
                label = field.get('label', '').lower()
                if label and label in user_lower:
                    logger.debug(f"Matched field by label: '{label}' -> {name}")
                    return name
        
        # 3. Fuzzy match using SequenceMatcher
        best_match = None
        best_ratio = 0.0
        
        for field in fields:
            # Check against name
            ratio = SequenceMatcher(None, user_lower, field.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = field
            
            # Check against label if available
            if session:
                label = self._get_field_label(session, field).lower()
                label_ratio = SequenceMatcher(None, user_lower, label).ratio()
                if label_ratio > best_ratio:
                    best_ratio = label_ratio
                    best_match = field
        
        # Threshold for fuzzy match
        if best_ratio > 0.7:
            logger.debug(f"Fuzzy matched field: '{user_input}' -> {best_match} (score: {best_ratio:.2f})")
            return best_match
            
        # 4. Phonetic match (Soundex/Metaphone) via PhoneticMatcher
        phonetic_match = PhoneticMatcher.find_best_match(user_input, fields)
        if phonetic_match:
            logger.debug(f"Phonetic matched field: '{user_input}' -> {phonetic_match}")
            return phonetic_match
            
        return None

    def _refine_extracted_values(
        self, 
        extracted_values: Dict[str, str], 
        current_batch: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        Refine extracted values using TextRefiner for cleaner form data.
        
        ALWAYS cleans name fields first, then applies type-specific formatting.
        """
        if not extracted_values:
            return extracted_values
        
        # Build field type lookup from current batch
        field_types = {}
        for field in current_batch:
            name = field.get('name', '')
            label = field.get('label', '').lower()
            ftype = field.get('type', 'text').lower()
            
            if 'name' in label or 'name' in name.lower():
                field_types[name] = 'name'
            elif 'email' in label or 'email' in name.lower():
                field_types[name] = 'email'
            elif 'phone' in label or 'tel' in ftype or 'mobile' in label:
                field_types[name] = 'phone'
            else:
                field_types[name] = ftype
        
        # ALWAYS clean name fields first - this runs regardless of TEXT_REFINER
        cleaned_values = {}
        for field_name, value in extracted_values.items():
            if field_types.get(field_name) == 'name':
                cleaned_values[field_name] = self._clean_name_value(value)
                logger.info(f"Name cleanup: '{value}' -> '{cleaned_values[field_name]}'")
            else:
                cleaned_values[field_name] = value
        
        # Now apply TEXT_REFINER if available for additional processing
        if not TEXT_REFINER_AVAILABLE:
            return cleaned_values
        
        try:
            refiner = get_text_refiner()
            
            # Refine each value (names already cleaned above)
            refined = {}
            for field_name, value in cleaned_values.items():
                if not value or not value.strip():
                    refined[field_name] = value
                    continue
                
                field_type = field_types.get(field_name, 'text')
                
                # Use quick synchronous clean for simple refinement
                cleaned = refiner.quick_clean(value)
                
                # Apply type-specific rules (names already handled above)
                if field_type == 'email':
                    cleaned = re.sub(r'\s*at\s*', '@', cleaned, flags=re.IGNORECASE)
                    cleaned = re.sub(r'\s*dot\s*', '.', cleaned, flags=re.IGNORECASE)
                    cleaned = cleaned.replace(' ', '').lower()
                elif field_type == 'phone':
                    digits = re.sub(r'[^\d+]', '', cleaned)
                    if len(digits) >= 10:
                        cleaned = digits
                
                refined[field_name] = cleaned.strip()
                
                if cleaned != value:
                    logger.debug(f"Refined {field_name}: '{value}' -> '{cleaned}'")
            
            return refined
            
        except Exception as e:
            logger.warning(f"Value refinement failed, using cleaned values: {e}")
            return cleaned_values
    
    async def confirm_value(
        self, 
        session_id: str, 
        field_name: str, 
        confirmed_value: str
    ) -> None:
        """Confirm a value that needed verification."""
        session = await self.get_session(session_id)
        if session:
            session.extracted_fields[field_name] = confirmed_value
            session.confidence_scores[field_name] = 1.0
            await self._save_session(session)
            logger.info(f"Confirmed {field_name} = {confirmed_value}")
    
    async def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get a summary of the session state."""
        session = await self.get_session(session_id)
        if not session:
            return {"error": "Session not found"}
        
        remaining = self._get_remaining_fields(session)
        
        return {
            "session_id": session_id,
            "form_url": session.form_url,
            "extracted_fields": session.extracted_fields,
            "confidence_scores": session.confidence_scores,
            "remaining_count": len(remaining),
            "remaining_fields": [f.get('name') for f in remaining],
            "is_complete": len(remaining) == 0,
            "conversation_turns": len(session.conversation_history) // 2,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat()
        }
    
    async def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions from local cache. Redis handles TTL automatically."""
        expired = [
            sid for sid, session in self._local_sessions.items() 
            if session.is_expired()
        ]
        
        for sid in expired:
            del self._local_sessions[sid]
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired local sessions")
        
        return len(expired)
