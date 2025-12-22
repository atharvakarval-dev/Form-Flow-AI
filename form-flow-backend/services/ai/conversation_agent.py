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
# Field Clustering for Smart Batching
# =============================================================================

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
    
    SYSTEM_PROMPT = """You are a friendly, professional form-filling assistant named FormFlow.
Your job is to help users complete forms through natural conversation.

RULES:
1. Be conversational and friendly, not robotic
2. Group related questions together (2-4 max per turn)
3. Acknowledge information the user provides
4. Ask for clarification if something is unclear
5. For low-confidence extractions, ask for confirmation
6. Keep responses concise - users are busy

EXTRACTION RULES:
- Extract values from user speech accurately
- Handle common speech patterns (e.g., "john at gmail dot com" → "john@gmail.com")
- Return confidence score 0.0-1.0 for each extraction
- Mark values needing confirmation if confidence < 0.7

OUTPUT FORMAT (JSON):
{
    "response": "Your natural language response to the user",
    "extracted": {"field_name": "value", ...},
    "confidence": {"field_name": 0.95, ...},
    "needs_confirmation": ["field_name", ...]
}"""

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
        """Get fields that haven't been filled yet."""
        all_fields = self._get_all_fields(session.form_schema)
        
        remaining = []
        for field in all_fields:
            field_name = field.get('name', '')
            if (field_name and 
                field_name not in session.extracted_fields and
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
        
        # Process with LLM or fallback
        if self.llm and LANGCHAIN_AVAILABLE:
            result = self._process_with_llm(session, user_input, current_batch, remaining_fields)
        else:
            result = self._process_with_fallback(session, user_input, current_batch, remaining_fields)
        
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
        """Process input using LangChain LLM."""
        try:
            # Build context message
            context = self._build_context(session, current_batch, remaining_fields)
            
            messages = [
                SystemMessage(content=self.SYSTEM_PROMPT),
                HumanMessage(content=f"{context}\n\nUser says: \"{user_input}\"")
            ]
            
            response = self.llm.invoke(messages)
            log_api_call("LangChain-Gemini", "invoke", success=True)
            
            # Parse LLM response
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
        """Fallback processing without LLM."""
        # Simple extraction based on patterns
        extracted = {}
        confidence = {}
        
        user_lower = user_input.lower()
        
        for field in current_batch:
            field_name = field.get('name', '')
            field_type = field.get('type', 'text')
            
            # Email pattern
            if field_type == 'email' or 'email' in field_name.lower():
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', user_input)
                if email_match:
                    extracted[field_name] = email_match.group()
                    confidence[field_name] = 0.95
            
            # Phone pattern
            elif field_type == 'tel' or 'phone' in field_name.lower():
                phone_match = re.search(r'[\d\s\-\+\(\)]{10,}', user_input)
                if phone_match:
                    extracted[field_name] = re.sub(r'\s+', '', phone_match.group())
                    confidence[field_name] = 0.9
            
            # Name fields - extract quoted or capitalized words
            elif 'name' in field_name.lower():
                # Look for capitalized sequences
                name_match = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', user_input)
                if name_match:
                    extracted[field_name] = name_match[0]
                    confidence[field_name] = 0.85
        
        # Generate response
        if extracted:
            filled_str = ', '.join(f"{k}={v}" for k, v in extracted.items())
            remaining_count = len(remaining_fields) - len(extracted)
            
            if remaining_count > 0:
                batches = self.clusterer.create_batches(
                    [f for f in remaining_fields if f.get('name') not in extracted]
                )
                if batches:
                    next_labels = [f.get('label', f.get('name', '')) for f in batches[0][:3]]
                    next_q = ', '.join(next_labels[:-1]) + f" and {next_labels[-1]}" if len(next_labels) > 1 else next_labels[0] if next_labels else ""
                    message = f"Got it! Now, what's your {next_q}?"
                else:
                    message = "Thanks! Let me check what else we need."
            else:
                message = "Perfect! I've got all the information needed. Ready to submit?"
        else:
            message = "I didn't quite catch that. Could you please repeat?"
        
        return AgentResponse(
            message=message,
            extracted_values=extracted,
            confidence_scores=confidence,
            needs_confirmation=[k for k, v in confidence.items() if v < 0.7],
            remaining_fields=[f for f in remaining_fields if f.get('name') not in extracted],
            is_complete=len(remaining_fields) == len(extracted),
            next_questions=[]
        )
    
    def _refine_extracted_values(
        self, 
        extracted_values: Dict[str, str], 
        current_batch: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        Refine extracted values using TextRefiner for cleaner form data.
        
        Applies type-specific formatting (email normalization, phone digits, etc.)
        """
        if not TEXT_REFINER_AVAILABLE or not extracted_values:
            return extracted_values
        
        try:
            import asyncio
            refiner = get_text_refiner()
            
            # Build field type lookup
            field_types = {}
            for field in current_batch:
                name = field.get('name', '')
                label = field.get('label', '').lower()
                ftype = field.get('type', 'text').lower()
                
                # Infer field type from label/name if type is generic
                if 'email' in label or 'email' in name.lower():
                    field_types[name] = 'email'
                elif 'phone' in label or 'tel' in ftype or 'mobile' in label:
                    field_types[name] = 'phone'
                elif 'name' in label:
                    field_types[name] = 'name'
                elif 'experience' in label or 'years' in label:
                    field_types[name] = 'number'
                elif 'date' in ftype:
                    field_types[name] = 'date'
                else:
                    field_types[name] = ftype
            
            # Refine each extracted value
            refined = {}
            for field_name, raw_value in extracted_values.items():
                if not raw_value or not raw_value.strip():
                    refined[field_name] = raw_value
                    continue
                
                field_type = field_types.get(field_name, 'text')
                
                # Use quick synchronous clean for simple refinement
                cleaned = refiner.quick_clean(raw_value)
                
                # Apply type-specific rules
                if field_type == 'email':
                    # Convert "john at gmail dot com" to "john@gmail.com"
                    cleaned = re.sub(r'\s*at\s*', '@', cleaned, flags=re.IGNORECASE)
                    cleaned = re.sub(r'\s*dot\s*', '.', cleaned, flags=re.IGNORECASE)
                    cleaned = cleaned.replace(' ', '').lower()
                elif field_type == 'phone':
                    # Extract only digits
                    digits = re.sub(r'[^\d+]', '', cleaned)
                    if len(digits) >= 10:
                        cleaned = digits
                elif field_type == 'name':
                    # Title case for names
                    cleaned = cleaned.title()
                
                refined[field_name] = cleaned.strip()
                
                if cleaned != raw_value:
                    logger.debug(f"Refined {field_name}: '{raw_value}' -> '{cleaned}'")
            
            return refined
            
        except Exception as e:
            logger.warning(f"Value refinement failed, using raw values: {e}")
            return extracted_values
    
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
