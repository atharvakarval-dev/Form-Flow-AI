"""
Conversation Agent

Main orchestrator for form-filling conversations.
Delegates to specialized modules for extraction, intent handling, etc.

This is a slim orchestration layer that coordinates:
- LLM and fallback extraction
- Intent recognition and handling
- Response generation and adaptation
- Session management
"""

import uuid
import asyncio
import re
from typing import Dict, List, Any, Optional
from datetime import datetime

from utils.logging import get_logger
from utils.validators import InputValidationError
from config.settings import settings

# Models - import from modular files
from services.ai.models import (
    ConversationSession, 
    AgentResponse,
    FieldStatus,
    UserIntent as StateUserIntent,  # Avoid conflict with conversation_intelligence.UserIntent
)

# Extraction - import from modular files
from services.ai.extraction import (
    LLMExtractor,
    FallbackExtractor,
    FieldClusterer,
    ValueRefiner,
)

# Handlers - import from modular files
from services.ai.handlers import (
    IntentHandler,
    GreetingHandler,
    ResponseAdapter,
)

# Prompts - import from modular files
from services.ai.prompts import EXTRACTION_SYSTEM_PROMPT, build_extraction_context

# Voice processing - import from modular files
from services.ai.voice import (
    VoiceInputProcessor,
    NoiseHandler,
    ClarificationStrategy,
    ConfidenceCalibrator,
    MultiModalFallback,
    PhoneticMatcher,
    AudioQuality,
)

# Intent recognition - keep using existing
from services.ai.conversation_intelligence import (
    ConversationContext,
    IntentRecognizer,
    AdaptiveResponseGenerator,
    ProgressTracker,
    UserIntent,
    UserSentiment,
)

# Normalizers
from services.ai.normalizers import (
    normalize_email_smart,
    normalize_phone_smart,
    normalize_name_smart,
    normalize_text_smart,
)

# Suggestion engine for contextual suggestions
from services.ai.suggestion_engine import SuggestionEngine, PatternType

logger = get_logger(__name__)

# Try to import LangChain
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    logger.warning("LangChain not installed. Using fallback mode.")
    LANGCHAIN_AVAILABLE = False

# Try to import TextRefiner
try:
    from services.ai.text_refiner import get_text_refiner
    TEXT_REFINER_AVAILABLE = True
except ImportError:
    TEXT_REFINER_AVAILABLE = False

# Try to import Local LLM
try:
    from services.ai.local_llm import get_local_llm_service, is_local_llm_available
    LOCAL_LLM_AVAILABLE = True
except ImportError:
    LOCAL_LLM_AVAILABLE = False

# Constants
LLM_MAX_RETRIES = 3
LLM_RETRY_BASE_DELAY = 1.0
LLM_RETRY_MAX_DELAY = 10.0
CONFIDENCE_THRESHOLD = 0.70


def validate_form_schema(schema: List[Dict[str, Any]]) -> None:
    """Validate form schema structure."""
    if not schema:
        raise InputValidationError("Form schema cannot be empty")
    if not isinstance(schema, list):
        raise InputValidationError("Form schema must be a list")


class ConversationAgent:
    """
    Main orchestrator for form-filling conversations.
    
    Coordinates specialized modules:
    - LLMExtractor: LLM-based extraction
    - FallbackExtractor: Rule-based fallback
    - IntentHandler: Special intent processing
    - GreetingHandler: Initial greetings
    - ResponseAdapter: Style adaptation
    - ValueRefiner: Post-extraction cleanup
    """
    
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        model: str = "gemma-3-27b-it",
        session_manager = None
    ):
        """
        Initialize the conversation agent.
        
        Args:
            api_key: Google API key (falls back to settings)
            model: Gemini model to use
            session_manager: Optional SessionManager for persistence
        """
        self.api_key = api_key or settings.GOOGLE_API_KEY
        self.model_name = model
        self.session_manager = session_manager
        
        # Initialize LLM
        self.llm = None
        self.llm_extractor = None
        self.local_llm = None
        
        if LANGCHAIN_AVAILABLE and self.api_key:
            try:
                self.llm = ChatGoogleGenerativeAI(
                    model=model,
                    google_api_key=self.api_key,
                    temperature=0.3,
                    convert_system_message_to_human=True
                )
                self.llm_extractor = LLMExtractor(self.llm, model)
                logger.info(f"ConversationAgent initialized with {model}")
            except Exception as e:
                logger.error(f"Failed to initialize LLM: {e}")
                self.llm = None
        else:
            logger.warning("LangChain not available - using fallback mode")
        
        # Initialize local LLM as primary (with Gemini fallback)
        # Only if USE_LOCAL_LLM is enabled in settings
        if LOCAL_LLM_AVAILABLE and getattr(settings, 'USE_LOCAL_LLM', True):
            try:
                self.local_llm = get_local_llm_service(gemini_api_key=self.api_key)
                if self.local_llm:
                    logger.info("✅ Local LLM initialized as PRIMARY (Gemini as fallback)")
            except Exception as e:
                logger.warning(f"Local LLM initialization failed: {e}")
        
        # Initialize components
        self.fallback_extractor = FallbackExtractor
        self.clusterer = FieldClusterer()
        self.value_refiner = ValueRefiner()
        self.intent_recognizer = IntentRecognizer()
        self.suggestion_engine = SuggestionEngine()
        
        # Session cache
        self._sessions: Dict[str, ConversationSession] = {}
    
    # =========================================================================
    # Session Management
    # =========================================================================
    
    async def create_session(
        self, 
        form_schema: List[Dict[str, Any]], 
        form_url: str = "",
        initial_data: Dict[str, str] = None,
        client_type: str = "extension"
    ) -> ConversationSession:
        """
        Create a new conversation session.
        
        Args:
            form_schema: Parsed form schema from form parser
            form_url: URL of the form being filled
            initial_data: Any pre-filled data
            client_type: 'web' or 'extension'
            
        Returns:
            ConversationSession: New session object
        """
        validate_form_schema(form_schema)
        
        # Use factory method for backward compatible construction
        session = ConversationSession.create(
            id=str(uuid.uuid4()),
            form_schema=form_schema,
            form_url=form_url,
            extracted_fields=initial_data or {},
            client_type=client_type
        )
        
        await self._save_session(session)
        logger.info(f"Created session: {session.id}")
        return session
    
    async def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Retrieve an existing session from Redis or local cache."""
        # Try local cache first
        if session_id in self._sessions:
            session = self._sessions[session_id]
            if not session.is_expired():
                return session
        
        # Try SessionManager (Redis)
        if self.session_manager:
            try:
                data = await self.session_manager.get_session(session_id)
                if data:
                    session = ConversationSession.from_dict(data)
                    self._sessions[session_id] = session
                    return session
            except Exception as e:
                logger.error(f"Error retrieving session from Redis: {e}")
        
        return None
    
    async def _save_session(self, session: ConversationSession) -> None:
        """Save session to Redis via SessionManager, with local fallback."""
        self._sessions[session.id] = session
        
        if self.session_manager:
            try:
                await self.session_manager.save_session(session.to_dict())
            except Exception as e:
                logger.error(f"Error saving session to Redis: {e}")
    
    async def delete_session(self, session_id: str) -> None:
        """Delete session from storage."""
        if session_id in self._sessions:
            del self._sessions[session_id]
        
        if self.session_manager:
            await self.session_manager.delete_session(session_id)

    async def cleanup_expired_sessions(self):
        """Cleanup expired sessions from storage."""
        if self.session_manager:
            await self.session_manager.cleanup_local_cache()
    
    # =========================================================================
    # Greeting Generation
    # =========================================================================
    
    async def generate_initial_greeting(self, session: ConversationSession) -> AgentResponse:
        """
        Generate the initial greeting and first questions.
        
        Args:
            session: The conversation session
            
        Returns:
            AgentResponse with greeting and first batch of questions
        """
        return GreetingHandler.generate_initial_greeting(session, self.clusterer)
    
    # =========================================================================
    # Main Processing Pipeline
    # =========================================================================
    
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
        - Value extraction (LLM or fallback)
        - Response adaptation
        
        Args:
            session_id: Session identifier
            user_input: User's text or voice input
            input_metadata: Optional metadata (is_voice, stt_confidence, etc.)
            
        Returns:
            AgentResponse with extracted values and next questions
        """
        # 1. Load session
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        session.update_activity()
        
        # Get remaining fields and current batch
        remaining_fields = session.get_remaining_fields()
        
        # DEBUG: Log session state
        logger.info(f"🔍 Session Debug - Extracted: {list(session.extracted_fields.keys())}")
        logger.info(f"🔍 Session Debug - Remaining ({len(remaining_fields)}): {[f.get('name') for f in remaining_fields]}")
        
        # Determine max fields based on client type and feature flag
        # Web frontend gets grouped questions when SMART_GROUPING_ENABLED is True
        is_web_client = getattr(session, 'client_type', 'extension') == 'web'
        
        # Smart Grouping: Allow batching for web clients when enabled
        if is_web_client and not settings.SMART_GROUPING_ENABLED:
            max_fields = 1  # Legacy: Linear single-field flow
        else:
            max_fields = None  # Smart Grouping: Allow natural batching
        
        batches = self.clusterer.create_batches(remaining_fields, max_fields=max_fields)
        current_batch = batches[0] if batches else []
        
        # Store current batch in session
        session.current_question_batch = [f.get('name') for f in current_batch]
        
        # 2. Detect voice mode and normalize
        input_metadata = input_metadata or {}
        is_voice = input_metadata.get('is_voice', False)
        stt_confidence = input_metadata.get('stt_confidence', 1.0)
        
        if is_voice:
            expected_type = current_batch[0].get('type') if current_batch else None
            original_input = user_input
            user_input = VoiceInputProcessor.normalize_voice_input(
                user_input,
                expected_field_type=expected_type
            )
            if original_input != user_input:
                logger.info(f"Voice normalized: '{original_input}' -> '{user_input}'")
        
        # 3. Detect intent
        intent, intent_confidence = self.intent_recognizer.detect_intent(user_input)
        
        if intent and intent_confidence < CONFIDENCE_THRESHOLD:
            logger.debug(f"Low intent confidence ({intent_confidence:.2f}), treating as DATA")
            intent = UserIntent.DATA
        
        logger.info(f"Detected intent: {intent} (confidence: {intent_confidence:.2f})")
        
        # Update conversation context
        session.conversation_context.update_from_input(user_input)
        session.conversation_context.last_intent = intent
        
        # 4. Handle special intents
        if intent == UserIntent.UNDO or intent == UserIntent.BACK:
            result = await IntentHandler.handle_undo(session, user_input, remaining_fields)
            await self._save_session(session)
            return result
        
        if intent == UserIntent.SKIP and current_batch:
            result = await IntentHandler.handle_skip(session, current_batch, remaining_fields)
            
            # IMPROVEMENT: Don't just stop there. Proactively ask the next question.
            # Convert response message to include next question
            new_remaining = session.get_remaining_fields()
            if new_remaining:
                next_batches = self.clusterer.create_batches(new_remaining)
                if next_batches:
                    next_batch = next_batches[0]
                    next_labels = [f.get('label', f.get('name', '')) for f in next_batch[:3]]
                    
                    if len(next_labels) == 1:
                        result.message += f" What's your {next_labels[0]}?"
                    elif len(next_labels) == 2:
                        result.message += f" What's your {next_labels[0]} and {next_labels[1]}?"
                    else:
                        result.message += f" What's your {', '.join(next_labels[:-1])}, and {next_labels[-1]}?"
                    
                    result.next_questions = [
                        {'name': f.get('name'), 'label': f.get('label'), 'type': f.get('type')} 
                        for f in next_batch
                    ]
            
            await self._save_session(session)
            return result
        
        if intent == UserIntent.HELP:
            return IntentHandler.handle_help(current_batch, remaining_fields)
        
        if intent == UserIntent.STATUS:
            return IntentHandler.handle_status(session, remaining_fields)
        
        if intent == UserIntent.CORRECTION:
            result = await IntentHandler.handle_correction(session, user_input, remaining_fields)
            await self._save_session(session)
            return result
        
        # 5. Check for compound intent (DATA + SKIP combined)
        # e.g., "contact reason is job application and rest skip it"
        has_skip_rest = bool(re.search(
            r'\b(and\s+)?(rest\s+skip|skip\s+(the\s+)?rest|and\s+skip|rest\s+skip\s+it)\b',
            user_input.lower()
        ))
        
        if has_skip_rest and current_batch:
            logger.info("Detected compound intent: DATA + SKIP REST")
            
            # First, extract values from the data portion
            # Remove skip-related phrases before extraction
            clean_input = re.sub(
                r'\b(and\s+)?(rest\s+skip(\s+it)?|skip\s+(the\s+)?rest(\s+of\s+them)?|and\s+skip(\s+it)?)\b',
                '',
                user_input,
                flags=re.IGNORECASE
            ).strip()
            
            logger.info(f"Clean input for extraction: '{clean_input}'")
            
            # Extract from clean input
            extracted, confidence_scores, message = await self._extract_values(
                session, clean_input, current_batch, remaining_fields, is_voice
            )
            
            # Refine and store extracted values
            refined = self.value_refiner.refine_values(extracted, remaining_fields)
            
            for field_name, value in refined.items():
                # Add to undo stack
                session.undo_stack.append({
                    'field_name': field_name,
                    'value': value,
                    'timestamp': datetime.now().isoformat()
                })
                
                # Use FormDataManager for atomic field update
                confidence = confidence_scores.get(field_name, 0.8)
                session.form_data_manager.update_field(
                    field_name=field_name,
                    value=value,
                    confidence=confidence,
                    intent=StateUserIntent.DIRECT_ANSWER,
                    turn=session.context_window.current_turn
                )
            
            # Now skip the remaining fields in current batch that weren't filled
            filled_names = set(refined.keys())
            skipped_labels = []
            for field in current_batch:
                field_name = field.get('name')
                if field_name not in filled_names:
                    already_skipped = session.form_data_manager.get_skipped_field_names()
                    if field_name and field_name not in already_skipped:
                        session.form_data_manager.skip_field(
                            field_name=field_name,
                            turn=getattr(session.context_window, 'current_turn', 0)
                        )
                        if hasattr(session.context_window, 'mark_field_skipped'):
                            session.context_window.mark_field_skipped(field_name)
                        skipped_labels.append(field.get('label', field_name))
            
            # Save session and generate response
            await self._save_session(session)
            
            # Build response message
            extracted_labels = []
            for field_name in refined.keys():
                field_info = next((f for f in current_batch if f.get('name') == field_name), {})
                extracted_labels.append(field_info.get('label', field_name))
            
            if extracted_labels:
                message = f"Got your {', '.join(extracted_labels)}!"
            else:
                message = ""
            
            if skipped_labels:
                if message:
                    message += f" Skipped {', '.join(skipped_labels)}."
                else:
                    message = f"Skipped {', '.join(skipped_labels)}."
            
            # Add next question
            new_remaining = session.get_remaining_fields()
            if new_remaining:
                next_batches = self.clusterer.create_batches(new_remaining)
                if next_batches:
                    next_batch = next_batches[0]
                    next_labels = [f.get('label', f.get('name', '')) for f in next_batch[:3]]
                    
                    if len(next_labels) == 1:
                        message += f" What's your {next_labels[0]}?"
                    elif len(next_labels) == 2:
                        message += f" What's your {next_labels[0]} and {next_labels[1]}?"
                    else:
                        message += f" What's your {', '.join(next_labels[:-1])}, and {next_labels[-1]}?"
            
            return AgentResponse(
                message=message,
                extracted_values=refined,
                confidence_scores=confidence_scores,
                needs_confirmation=[],
                remaining_fields=new_remaining,
                is_complete=len([f for f in new_remaining if f.get('required', False)]) == 0,
                next_questions=[
                    {'name': f.get('name'), 'label': f.get('label'), 'type': f.get('type')} 
                    for f in (next_batches[0] if next_batches else [])
                ]
            )
        
        # 6. Add to conversation history
        session.conversation_history.append({
            'role': 'user',
            'content': user_input,
            'intent': intent.value if intent else None,
            'sentiment': session.conversation_context.user_sentiment.value
        })
        
        # 7. Extract values
        logger.info(f"Processing input: '{user_input[:100]}...'")
        logger.info(f"Current batch fields: {[f.get('name') for f in current_batch]}")
        
        # Get full schema for extraction and refinement
        all_fields = remaining_fields
        if hasattr(session, 'form_schema') and session.form_schema:
            raw_schema = session.form_schema
            flattened = []
            for item in raw_schema:
                if isinstance(item, dict) and 'fields' in item:
                    flattened.extend(item['fields'])
                else:
                    flattened.append(item)
            all_fields = flattened
        
        extracted, confidence_scores, message = await self._extract_values(
            session, user_input, current_batch, remaining_fields, is_voice
        )
        
        # 8. Refine and store extracted values using atomic FormDataManager
        # Use simple cleaning without heavy NLP for speed, or pass True if AI refinement desired
        refined = self.value_refiner.refine_values(extracted, all_fields)
        
        for field_name, value in refined.items():
            # Get field info from ALL fields to ensure type logic applies
            field_info = next(
                (f for f in all_fields if f.get('name') == field_name),
                {}
            )
            
            # Add to undo stack (legacy support)
            session.undo_stack.append({
                'field_name': field_name,
                'value': value,
                'timestamp': datetime.now().isoformat()
            })
            
            # Use FormDataManager for atomic field update with metadata
            confidence = confidence_scores.get(field_name, 0.8)
            session.form_data_manager.update_field(
                field_name=field_name,
                value=value,
                confidence=confidence,
                intent=StateUserIntent.DIRECT_ANSWER,
                turn=session.context_window.current_turn
            )
            
            # Detect patterns from this field for suggestion engine
            patterns = self.suggestion_engine.detect_patterns(
                field_name=field_name,
                field_value=value,
                field_type=field_info.get('type', 'text'),
                field_label=field_info.get('label', field_name)
            )
            
            # Store detected patterns in inference cache
            for pattern_type, pattern_data in patterns.items():
                session.inference_cache.detected_patterns[str(pattern_type)] = pattern_data
            
            logger.debug(f"Detected {len(patterns)} patterns from {field_name}")
        
        logger.info(f"Extracted values: {refined}")
        
        # Update context window for field navigation
        session.context_window.current_turn += 1
        
        # 8. Save session
        await self._save_session(session)
        
        # 9. Generate response
        remaining_fields = session.get_remaining_fields()
        
        # Determine max fields based on client type and feature flag
        is_web_client = getattr(session, 'client_type', 'extension') == 'web'
        
        # Smart Grouping: Allow batching for web clients when enabled
        if is_web_client and not settings.SMART_GROUPING_ENABLED:
            max_fields = 1  # Legacy: Linear single-field flow
        else:
            max_fields = None  # Smart Grouping: Allow natural batching
        
        batches = self.clusterer.create_batches(remaining_fields, max_fields=max_fields)
        next_batch = batches[0] if batches else []
        
        # Check if form is complete (all required fields filled)
        required_remaining = [f for f in remaining_fields if f.get('required', False)]
        is_complete = len(required_remaining) == 0
        
        # If complete, add completion message
        if is_complete and not next_batch:
            message += " \n\n🎉 All required fields completed! You can now submit the form."
        
        # Update context window with current/next field tracking
        if next_batch:
            session.context_window.active_field = next_batch[0].get('name')
            session.context_window.next_field = next_batch[1].get('name') if len(next_batch) > 1 else None
        
        # Generate suggestions for upcoming fields
        suggestions = []
        if next_batch and session.inference_cache.detected_patterns:
            suggestions = self.suggestion_engine.generate_suggestions(
                target_fields=next_batch,
                extracted_fields=session.extracted_fields,
                detected_patterns=session.inference_cache.detected_patterns
            )
            
            # Store suggestions in inference cache
            for suggestion in suggestions:
                session.inference_cache.contextual_suggestions[suggestion.target_field] = {
                    'value': suggestion.suggested_value,
                    'confidence': suggestion.confidence,
                    'reasoning': suggestion.reasoning
                }
            
            # Optionally enhance message with suggestion
            if suggestions and suggestions[0].confidence >= 0.75:
                top_suggestion = suggestions[0]
                logger.info(f"Generated suggestion: {top_suggestion.target_field} = {top_suggestion.suggested_value}")
        
        # Adapt message to user style
        if session.conversation_context.user_preference_style:
            message = ResponseAdapter.adapt_response(
                message, 
                session.conversation_context.user_preference_style
            )
        
        # Build suggestions list for response
        suggestions_data = [
            {
                'field': s.target_field,
                'value': s.suggested_value,
                'confidence': s.confidence,
                'prompt': s.prompt_template
            }
            for s in suggestions
        ]
        
        # Smart Grouping: Detect partial extraction for current batch
        # Check what fields from current_batch were actually filled
        batch_field_names = [f.get('name') for f in current_batch]
        filled_in_batch = [name for name in batch_field_names if name in refined]
        missing_from_batch = [name for name in batch_field_names if name not in refined]
        
        # Calculate fill ratio
        fill_ratio = len(filled_in_batch) / len(batch_field_names) if batch_field_names else 1.0
        min_fill_ratio = settings.SMART_GROUPING_MIN_FILL_RATIO
        
        # Determine extraction status and follow-up needs
        if not refined:
            extraction_status = "failed"
            requires_followup = True
        elif fill_ratio < min_fill_ratio and missing_from_batch:
            extraction_status = "partial_extraction"
            requires_followup = True
            # Generate targeted follow-up message
            missing_labels = []
            for field_name in missing_from_batch:
                field_info = next((f for f in current_batch if f.get('name') == field_name), {})
                missing_labels.append(field_info.get('label', field_name))
            
            if len(missing_labels) == 1:
                message += f" I still need your {missing_labels[0]}."
            elif len(missing_labels) == 2:
                message += f" I still need your {missing_labels[0]} and {missing_labels[1]}."
            else:
                message += f" I still need your {', '.join(missing_labels[:-1])}, and {missing_labels[-1]}."
        else:
            extraction_status = "complete"
            requires_followup = False
        
        return AgentResponse(
            message=message,
            extracted_values=refined,
            confidence_scores=confidence_scores,
            needs_confirmation=[],
            remaining_fields=remaining_fields,
            is_complete=is_complete,
            next_questions=[
                {'name': f.get('name'), 'label': f.get('label'), 'type': f.get('type')} 
                for f in next_batch
            ],
            suggestions=suggestions_data,
            # Smart Grouping fields
            status=extraction_status,
            missing_from_group=missing_from_batch,
            requires_followup=requires_followup
        )
    
    # =========================================================================
    # Extraction Pipeline
    # =========================================================================
    
    async def _extract_values(
        self,
        session: ConversationSession,
        user_input: str,
        current_batch: List[Dict[str, Any]],
        remaining_fields: List[Dict[str, Any]],
        is_voice: bool
    ) -> tuple:
        """
        Extraction pipeline: LLM first, fallback second.
        
        Returns:
            Tuple of (extracted_values, confidence_scores, message)
        """
        # Try local LLM first (primary path - fast & free)
        if self.local_llm:
            try:
                logger.info("Using Local LLM (primary)...")
                extracted = {}
                confidence = {}
                
                # Prepare field list for extraction - use ALL remaining fields, not just current_batch
                # This allows users to provide multiple fields at once (e.g., "my name is X and email is Y")
                # Prepare field list for extraction - pass FULL objects for context-aware extraction
                # This allows the LLM to see options, types, and labels
                # CHANGE: Use session.form_schema (ALL fields) instead of remaining_fields
                # This enables "Smart Update/Correction" where the user can update any field value at any time
                if hasattr(session, 'form_schema') and session.form_schema:
                    raw_schema = session.form_schema
                    # Flatten schema: If it's a list provides forms with 'fields', extract them
                    all_fields = []
                    for item in raw_schema:
                        if isinstance(item, dict) and 'fields' in item:
                            all_fields.extend(item['fields'])
                        else:
                            all_fields.append(item)
                    fields_to_extract = all_fields
                else:
                    fields_to_extract = remaining_fields
                
                # If form_schema is somehow empty (shouldn't be), fall back
                if not fields_to_extract:
                    fields_to_extract = remaining_fields
                
                logger.info(f"Extracting from {len(fields_to_extract)} fields: {fields_to_extract[:5]}...")
                
                if fields_to_extract:
                    # Use new batch extraction method
                    batch_result = self.local_llm.extract_all_fields(user_input, fields_to_extract)
                    
                    if batch_result.get('extracted'):
                        new_extracted = batch_result['extracted']
                        new_confidence = batch_result.get('confidence', {})
                        
                        logger.info(f"Local LLM raw extraction: {new_extracted}")
                        
                        # Update main extracted dict
                        # Update main extracted dict
                        for key, value in new_extracted.items():
                            # Find matching field name from key - search in fields_to_extract (which effectively covers everything)
                            # This ensures we match against any field in the schema, not just remaining ones
                            field_match = next(
                                (f for f in fields_to_extract if f.get('name') == key or f.get('label') == key), 
                                None
                            )
                            if field_match:
                                field_name = field_match.get('name')
                                extracted[field_name] = value
                                confidence[field_name] = new_confidence.get(key, 0.8)

                if extracted:
                    logger.info(f"Local LLM extracted: {list(extracted.keys())}")
                    
                    # Generate confirmation message
                    extracted_labels = []
                    for field_name in extracted.keys():
                        # Look up label in fields_to_extract to ensure we get labels for ANY field (even past ones)
                        field_info = next((f for f in fields_to_extract if f.get('name') == field_name), {})
                        extracted_labels.append(field_info.get('label', field_name))
                    
                    if len(extracted_labels) == 1:
                        message = f"Got your {extracted_labels[0]}!"
                    else:
                        # Limit to first 3 to avoid super long messages
                        if len(extracted_labels) > 3:
                            message = f"Got your {', '.join(extracted_labels[:3])} and others!"
                        else:
                            message = f"Got your {', '.join(extracted_labels)}!"
                    
                    # Add next question if more fields remain
                    # We accept that 'extracted' might contain fields NOT in 'remaining_fields' (updates)
                    # So we just filter remaining_fields by what is now extracted
                    remaining_after = [f for f in remaining_fields if f.get('name') not in extracted]
                    if remaining_after:
                        next_batches = self.clusterer.create_batches(remaining_after)
                        if next_batches:
                            next_labels = [f.get('label', f.get('name', '')) for f in next_batches[0][:3]]
                            if len(next_labels) == 1:
                                message += f" What's your {next_labels[0]}?"
                            elif len(next_labels) == 2:
                                message += f" What's your {next_labels[0]} and {next_labels[1]}?"
                            else:
                                message += f" What's your {', '.join(next_labels[:-1])}, and {next_labels[-1]}?"
                    
                    return extracted, confidence, message
                    
            except Exception as e:
                logger.warning(f"Local LLM extraction failed, trying Gemini: {e}")
        
        # Try Gemini for complex reasoning (secondary)
        if self.llm and self.llm_extractor:
            try:
                logger.info("Using Gemini for complex extraction...")
                extracted, confidence, message = await self.llm_extractor.extract(
                    user_input=user_input,
                    current_batch=current_batch,
                    remaining_fields=remaining_fields,
                    conversation_history=session.conversation_history,
                    already_extracted=session.extracted_fields,
                    is_voice=is_voice
                )
                
                if extracted:
                    logger.info(f"Gemini extracted: {list(extracted.keys())}")
                    return extracted, confidence, message
                    
            except Exception as e:
                logger.warning(f"Gemini extraction failed, using rule-based fallback: {e}")
        
        # Fallback to rule-based extraction
        logger.info("Using FALLBACK extraction...")
        extracted, confidence = self.fallback_extractor.extract_with_intelligence(
            user_input=user_input,
            current_batch=current_batch,
            remaining_fields=remaining_fields
        )
        
        logger.info(f"Fallback extracted: {extracted}")
        
        # Generate response message
        if extracted:
            field_labels = []
            for field_name in extracted.keys():
                field_info = next((f for f in remaining_fields if f.get('name') == field_name), {})
                field_labels.append(field_info.get('label', field_name))
            
            if len(field_labels) == 1:
                message = f"Got your {field_labels[0]}!"
            else:
                message = f"Got your {', '.join(field_labels)}!"
            
            # Add next question if more fields remain
            remaining_after = [f for f in remaining_fields if f.get('name') not in extracted]
            if remaining_after:
                next_batches = self.clusterer.create_batches(remaining_after)
                if next_batches:
                    next_labels = [f.get('label', f.get('name', '')) for f in next_batches[0][:3]]
                    if len(next_labels) == 1:
                        message += f" What's your {next_labels[0]}?"
                    elif len(next_labels) == 2:
                        message += f" What's your {next_labels[0]} and {next_labels[1]}?"
                    else:
                        message += f" What's your {', '.join(next_labels[:-1])}, and {next_labels[-1]}?"
        else:
            # No extraction - provide helpful guidance
            if current_batch:
                field = current_batch[0]
                label = field.get('label', field.get('name', 'that'))
                message = f"I didn't quite catch your {label}. Could you try again?"
            else:
                message = "I didn't quite catch that. Could you try again?"
        
        return extracted, confidence, message


# =============================================================================
# Backwards Compatibility Exports
# =============================================================================

# Re-export commonly used classes for backwards compatibility
__all__ = [
    'ConversationAgent',
    'ConversationSession',
    'AgentResponse',
    'FieldClusterer',
    'VoiceInputProcessor',
    'IntentRecognizer',
    'UserIntent',
]
