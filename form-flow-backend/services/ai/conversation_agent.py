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
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import uuid

from utils.logging import get_logger, log_api_call
from utils.exceptions import AIServiceError

# Import TextRefiner for cleaning extracted values
try:
    from services.ai.text_refiner import get_text_refiner
    TEXT_REFINER_AVAILABLE = True
except ImportError:
    TEXT_REFINER_AVAILABLE = False

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
    """Represents an active conversation session."""
    id: str
    form_schema: List[Dict[str, Any]]
    form_url: str
    extracted_fields: Dict[str, str] = field(default_factory=dict)
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    current_question_batch: List[str] = field(default_factory=list)
    skipped_fields: List[str] = field(default_factory=list)  # Track skipped fields
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    def is_expired(self, ttl_minutes: int = 30) -> bool:
        """Check if session has expired."""
        return datetime.now() - self.last_activity > timedelta(minutes=ttl_minutes)
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.now()
    
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
            'last_activity': self.last_activity.isoformat()
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
            last_activity=datetime.fromisoformat(data['last_activity']) if isinstance(data.get('last_activity'), str) else data.get('last_activity', datetime.now())
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
        already_extracted: Dict[str, str]
    ) -> str:
        """
        Build comprehensive context that helps LLM understand:
        1. What fields we're currently asking about
        2. What values to look for
        3. Where to stop extraction
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
        
        # 3. Build smart context
        context = f"""EXTRACTION TASK:

USER INPUT: "{user_input}"

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
    
    # Max questions per batch based on field type
    MAX_QUESTIONS = {
        'simple': 4,      # text, email, phone
        'moderate': 2,    # select, radio
        'complex': 1      # textarea, file
    }
    
    SIMPLE_TYPES = {'text', 'email', 'tel', 'number', 'date'}
    MODERATE_TYPES = {'select', 'radio'}
    COMPLEX_TYPES = {'textarea', 'file', 'checkbox'}
    
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
        """
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
            # 3-4 fields
            all_but_last = ', '.join(labels[:-1])
            return f"Hello! I'll help you fill this out quickly. Can you tell me your {all_but_last}, and {labels[-1]}? You can say them all at once!"
    
    async def process_user_input(
        self, 
        session_id: str, 
        user_input: str
    ) -> AgentResponse:
        """
        Process user input and extract field values.
        
        Args:
            session_id: The session ID
            user_input: What the user said
            
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
        session.conversation_history.append({
            'role': 'user',
            'content': user_input
        })
        
        # Get context for LLM
        remaining_fields = self._get_remaining_fields(session)
        current_batch = [
            f for f in remaining_fields 
            if f.get('name') in session.current_question_batch
        ]
        
        # --- HANDLE SKIP/NEXT COMMANDS ---
        user_lower = user_input.lower().strip()
        skip_patterns = ['skip', 'skip it', 'skip this', 'next', 'pass', 'move on', 'next question', 'skip field', 'skip this field']
        is_skip_command = any(pattern in user_lower for pattern in skip_patterns)
        
        if is_skip_command and current_batch:
            # Skip current batch and move to next
            logger.info(f"Skip command detected for fields: {[f.get('name') for f in current_batch]}")
            
            # Add skipped fields to the session's skipped list
            skipped_names = [f.get('name') for f in current_batch if f.get('name')]
            session.skipped_fields.extend(skipped_names)
            
            # Get remaining fields (now excludes skipped ones due to _get_remaining_fields)
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
                message = "Okay, skipped! Looks like we've covered all the fields. Ready to fill the form?"
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
        
        # Process with LLM or fallback
        logger.info(f"Processing input: '{user_input[:100]}...'")
        logger.info(f"Current batch: {[f.get('name') for f in current_batch]}")
        logger.info(f"Remaining fields: {[f.get('name') for f in remaining_fields]}")
        logger.info(f"LLM available: {self.llm is not None}, LangChain: {LANGCHAIN_AVAILABLE}")
        
        if self.llm and LANGCHAIN_AVAILABLE:
            logger.info("Using LLM for extraction...")
            result = self._process_with_llm(session, user_input, current_batch, remaining_fields)
            logger.info(f"LLM result - extracted: {result.extracted_values}, message: {result.message[:50]}...")
        else:
            logger.info("Using fallback extraction...")
            result = self._process_with_fallback(session, user_input, current_batch, remaining_fields)
            logger.info(f"Fallback result - extracted: {result.extracted_values}")
        
        # Update session with extracted values (REFINED)
        refined_values = self._refine_extracted_values(result.extracted_values, current_batch)
        for field_name, value in refined_values.items():
            if field_name not in result.needs_confirmation:
                session.extracted_fields[field_name] = value
                session.confidence_scores[field_name] = result.confidence_scores.get(field_name, 1.0)
        
        # Update result with refined values
        result.extracted_values = refined_values
        
        session.conversation_history.append({
            'role': 'assistant', 
            'content': result.message
        })
        
        # Prepare next batch if needed
        if not result.is_complete:
            new_remaining = self._get_remaining_fields(session)
            batches = self.clusterer.create_batches(new_remaining)
            if batches:
                session.current_question_batch = [f.get('name') for f in batches[0]]
                result.next_questions = [{'name': f.get('name'), 'label': f.get('label'), 'type': f.get('type')} for f in batches[0]]
            result.remaining_fields = new_remaining
        
        # Persist session changes to Redis
        await self._save_session(session)
        
        logger.info(f"Session {session_id}: Extracted {len(result.extracted_values)} values, {len(result.remaining_fields)} remaining")
        
        return result
    
    def _process_with_llm(
        self,
        session: ConversationSession,
        user_input: str,
        current_batch: List[Dict[str, Any]],
        remaining_fields: List[Dict[str, Any]]
    ) -> AgentResponse:
        """Process input using LangChain LLM with Smart Context."""
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
            
            response = self.llm.invoke(messages)
            log_api_call("LangChain-Gemini", "invoke", success=True)
            
            return self._parse_llm_response(response.content, remaining_fields)
            
        except Exception as e:
            logger.error(f"LLM processing error: {e}")
            log_api_call("LangChain-Gemini", "invoke", success=False, error=str(e))
            return self._process_with_fallback(session, user_input, current_batch, remaining_fields)
    
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
    
    def _parse_llm_response(
        self, 
        response_text: str,
        remaining_fields: List[Dict[str, Any]]
    ) -> AgentResponse:
        """Parse LLM response JSON."""
        try:
            # Find JSON in response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
                
                return AgentResponse(
                    message=data.get('response', response_text),
                    extracted_values=data.get('extracted', {}),
                    confidence_scores=data.get('confidence', {}),
                    needs_confirmation=data.get('needs_confirmation', []),
                    remaining_fields=remaining_fields,
                    is_complete=len(remaining_fields) == len(data.get('extracted', {})),
                    next_questions=[]
                )
        except json.JSONDecodeError:
            pass
        
        # Fallback: use response as-is
        return AgentResponse(
            message=response_text,
            extracted_values={},
            confidence_scores={},
            needs_confirmation=[],
            remaining_fields=remaining_fields,
            is_complete=False,
            next_questions=[]
        )
    
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
