"""
Session Model

Data classes for conversation session state management.
Pure data models with no business logic.

Version: 2.0.0 - Enhanced with industry-grade state management
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from services.ai.conversation_intelligence import ConversationContext
from services.ai.models.state import (
    FieldData,
    FieldStatus,
    InferenceCache,
    ContextWindow,
    FormDataManager,
    UserIntent as StateUserIntent,
)


@dataclass
class ConversationSession:
    """
    Session state management with enhanced context tracking.
    
    This is the central state object for conversational form-filling.
    Implements patterns from modern LLM-based conversational AI:
    
    1. ATOMIC STATE UPDATES: All field updates go through FormDataManager
       to prevent partial state corruption.
    
    2. CONTEXT WINDOW: Tracks active/previous/next fields like LLMs
       track token context, enabling natural conversation flow.
    
    3. INFERENCE CACHE: Stores detected patterns for intelligent
       suggestions, similar to RAG context caching.
    
    4. BACKWARD COMPATIBLE: Maintains all original properties through
       computed accessors, ensuring existing code continues to work.
    
    Stores all conversation state including extracted values,
    history, and user context. Pure data accessors only.
    """
    id: str
    form_schema: List[Dict[str, Any]]
    form_url: str
    
    # Enhanced state management (v2.0)
    form_data_manager: FormDataManager = field(default_factory=FormDataManager)
    inference_cache: InferenceCache = field(default_factory=InferenceCache)
    context_window: ContextWindow = field(default_factory=ContextWindow)
    
    # Conversation state
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    current_question_batch: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    # Enhanced conversational intelligence
    conversation_context: ConversationContext = field(default_factory=ConversationContext)
    undo_stack: List[Dict[str, Any]] = field(default_factory=list)
    correction_history: List[Dict[str, Any]] = field(default_factory=list)
    field_attempt_counts: Dict[str, int] = field(default_factory=dict)
    shown_milestones: set = field(default_factory=set)
    turns_per_field: Dict[str, int] = field(default_factory=dict)
    
    # Session metadata
    session_version: str = "2.0.0"
    
    # Legacy compatibility fields (for backward compatible constructor)
    # These are processed in __post_init__ and not used directly
    _init_extracted_fields: Optional[Dict[str, str]] = field(default=None, repr=False)
    _init_skipped_fields: Optional[List[str]] = field(default=None, repr=False)
    _init_confidence_scores: Optional[Dict[str, float]] = field(default=None, repr=False)
    
    def __post_init__(self):
        """
        Initialize session after construction.
        
        Handles:
        1. Legacy constructor args (extracted_fields, skipped_fields)
        2. Context window initialization from schema
        """
        # Process legacy constructor arguments
        if self._init_extracted_fields:
            for field_name, field_value in self._init_extracted_fields.items():
                confidence = 1.0
                if self._init_confidence_scores:
                    confidence = self._init_confidence_scores.get(field_name, 1.0)
                self.form_data_manager.update_field(
                    field_name=field_name,
                    value=field_value,
                    confidence=confidence,
                    turn=0,
                    intent=StateUserIntent.DIRECT_ANSWER
                )
            # Update context window
            for field_name in self._init_extracted_fields:
                self.context_window.mark_field_completed(field_name)
        
        if self._init_skipped_fields:
            for field_name in self._init_skipped_fields:
                self.form_data_manager.skip_field(field_name, turn=0)
                self.context_window.mark_field_skipped(field_name)
        
        # Initialize context window from schema
        if self.form_schema and not self.context_window.pending_fields:
            self.context_window.initialize_from_schema(self.form_schema)
    
    # =========================================================================
    # Factory Methods for Backward Compatibility
    # =========================================================================
    
    @classmethod
    def create(
        cls,
        id: str,
        form_schema: List[Dict[str, Any]],
        form_url: str,
        extracted_fields: Dict[str, str] = None,
        skipped_fields: List[str] = None,
        confidence_scores: Dict[str, float] = None,
        **kwargs
    ) -> 'ConversationSession':
        """
        Factory method for backward-compatible session creation.
        
        Accepts legacy parameters (extracted_fields, skipped_fields)
        alongside new parameters.
        
        Usage:
            # Old style (still supported):
            session = ConversationSession.create(
                id="test",
                form_schema=[...],
                form_url="...",
                extracted_fields={"name": "John"},
                skipped_fields=["phone"]
            )
            
            # New style (preferred):
            session = ConversationSession(
                id="test",
                form_schema=[...],
                form_url="..."
            )
            session.update_field("name", "John", confidence=0.95)
        """
        return cls(
            id=id,
            form_schema=form_schema,
            form_url=form_url,
            _init_extracted_fields=extracted_fields,
            _init_skipped_fields=skipped_fields,
            _init_confidence_scores=confidence_scores,
            **kwargs
        )
    

    # =========================================================================
    # Backward Compatible Property Accessors
    # =========================================================================
    
    @property
    def extracted_fields(self) -> Dict[str, str]:
        """
        Get extracted field values (backward compatible).
        
        Returns Dict[str, str] like the original implementation.
        Under the hood, this maps to FormDataManager.get_filled_fields().
        """
        return self.form_data_manager.get_filled_fields()
    
    @extracted_fields.setter
    def extracted_fields(self, value: Dict[str, str]) -> None:
        """
        Set extracted fields (backward compatible).
        
        Converts simple dict to FieldData objects.
        """
        for field_name, field_value in value.items():
            self.form_data_manager.update_field(
                field_name=field_name,
                value=field_value,
                confidence=1.0,  # Assume high confidence for direct sets
                turn=self.context_window.current_turn,
                intent=StateUserIntent.DIRECT_ANSWER
            )
    
    @property
    def confidence_scores(self) -> Dict[str, float]:
        """Get confidence scores (backward compatible)."""
        return self.form_data_manager.get_confidence_scores()
    
    @confidence_scores.setter
    def confidence_scores(self, value: Dict[str, float]) -> None:
        """Set confidence scores (backward compatible, limited support)."""
        # Note: This is limited because we can't update confidence without value
        # For full control, use form_data_manager directly
        pass
    
    @property
    def skipped_fields(self) -> List[str]:
        """Get skipped field names (backward compatible)."""
        return self.form_data_manager.get_skipped_field_names()
    
    @skipped_fields.setter  
    def skipped_fields(self, value: List[str]) -> None:
        """Set skipped fields (backward compatible)."""
        for field_name in value:
            self.form_data_manager.skip_field(
                field_name=field_name,
                turn=self.context_window.current_turn
            )
    
    # =========================================================================
    # Enhanced State Operations
    # =========================================================================
    
    def update_field(
        self,
        field_name: str,
        value: str,
        confidence: float = 1.0,
        intent: StateUserIntent = StateUserIntent.DIRECT_ANSWER,
        reasoning: str = ""
    ) -> FieldData:
        """
        Update a field with full metadata tracking.
        
        This is the preferred method for field updates in v2.0+.
        Automatically updates context window and undo stack.
        """
        # Update via manager for atomic operation
        field_data = self.form_data_manager.update_field(
            field_name=field_name,
            value=value,
            confidence=confidence,
            turn=self.context_window.current_turn,
            intent=intent,
            reasoning=reasoning
        )
        
        # Update context window
        self.context_window.mark_field_completed(field_name)
        
        # Push to undo stack
        self.undo_stack.append({
            'action': 'fill',
            'field_name': field_name,
            'value': value,
            'turn': self.context_window.current_turn,
            'timestamp': datetime.now().isoformat()
        })
        
        # Track field attempt
        self.field_attempt_counts[field_name] = (
            self.field_attempt_counts.get(field_name, 0) + 1
        )
        
        return field_data
    
    def skip_current_field(self) -> Optional[str]:
        """
        Skip the currently active field ONLY.
        
        This is the critical method that prevents the "skip it" bug.
        Only skips context_window.active_field, preserving all other state.
        
        Returns:
            Name of the skipped field, or None if no active field
        """
        active_field = self.context_window.active_field
        if not active_field:
            return None
        
        # Skip via manager for atomic operation
        self.form_data_manager.skip_field(
            field_name=active_field,
            turn=self.context_window.current_turn
        )
        
        # Update context window
        self.context_window.mark_field_skipped(active_field)
        
        # Push to undo stack
        self.undo_stack.append({
            'action': 'skip',
            'field_name': active_field,
            'turn': self.context_window.current_turn,
            'timestamp': datetime.now().isoformat()
        })
        
        return active_field
    
    def get_field_data(self, field_name: str) -> FieldData:
        """Get full FieldData for a field."""
        return self.form_data_manager.get_field(field_name)
    
    def get_active_field_name(self) -> Optional[str]:
        """Get currently active field name (what we're asking about)."""
        return self.context_window.active_field
    
    def set_active_field(
        self,
        field_name: str,
        field_schema: Dict[str, Any] = None
    ) -> None:
        """Set the currently active field for disambiguation."""
        self.context_window.set_active_field(field_name, field_schema)
    
    def advance_turn(self) -> int:
        """Advance conversation turn counter."""
        return self.context_window.advance_turn()
    
    def get_progress(self) -> Dict[str, Any]:
        """Get form completion progress."""
        return self.context_window.get_progress()
    
    # =========================================================================
    # Original Methods (maintained for compatibility)
    # =========================================================================
    
    def is_expired(self, ttl_minutes: int = 30) -> bool:
        """Check if session has expired."""
        return datetime.now() - self.last_activity > timedelta(minutes=ttl_minutes)
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now()
    
    def get_all_fields(self) -> List[Dict[str, Any]]:
        """Get all fields from the schema."""
        fields = []
        for form in self.form_schema:
            for f in form.get('fields', []):
                fields.append(f)
        return fields

    def get_total_field_count(self) -> int:
        """Get total number of fillable fields."""
        count = 0
        for form in self.form_schema:
            for f in form.get('fields', []):
                if f.get('type') not in ['submit', 'button', 'hidden'] and not f.get('hidden'):
                    count += 1
        return count
    
    def get_remaining_fields(self) -> List[Dict[str, Any]]:
        """Get fields that haven't been filled or skipped yet."""
        remaining = []
        filled = self.form_data_manager.get_filled_fields()
        skipped = self.form_data_manager.get_skipped_field_names()
        
        for form in self.form_schema:
            for f in form.get('fields', []):
                field_name = f.get('name', '')
                field_type = f.get('type', '')
                
                if field_type in ['submit', 'button', 'hidden'] or f.get('hidden'):
                    continue
                if field_name in filled or field_name in skipped:
                    continue
                    
                remaining.append(f)
        return remaining
    
    # =========================================================================
    # Serialization
    # =========================================================================
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to dictionary for persistence."""
        
        def safe_to_dict(obj):
            """Helper to safely serialize objects that might accidentally be dicts."""
            if isinstance(obj, dict):
                return obj
            if hasattr(obj, 'to_dict'):
                return obj.to_dict()
            return obj

        return {
            'id': self.id,
            'form_schema': self.form_schema,
            'form_url': self.form_url,
            'conversation_history': self.conversation_history,
            'current_question_batch': self.current_question_batch,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'conversation_context': safe_to_dict(self.conversation_context),
            'undo_stack': self.undo_stack,
            'correction_history': self.correction_history,
            'field_attempt_counts': self.field_attempt_counts,
            'shown_milestones': list(self.shown_milestones),
            'turns_per_field': self.turns_per_field,
            # Enhanced state (v2.0)
            'session_version': self.session_version,
            'form_data': safe_to_dict(self.form_data_manager),
            'inference_cache': safe_to_dict(self.inference_cache),
            'context_window': safe_to_dict(self.context_window),
            # Backward compatible fields (for older code reading this)
            'extracted_fields': self.extracted_fields,
            'confidence_scores': self.confidence_scores,
            'skipped_fields': self.skipped_fields,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationSession':
        """Deserialize session from dictionary."""
        session_version = data.get('session_version', '1.0.0')
        
        # Initialize form data manager
        if session_version >= '2.0.0' and 'form_data' in data:
            # V2.0+ format - use new structure
            form_data_manager = FormDataManager.from_dict(data.get('form_data', {}))
        else:
            # V1.x format - migrate from old structure
            form_data_manager = FormDataManager()
            
            # Migrate extracted_fields
            for field_name, value in data.get('extracted_fields', {}).items():
                confidence = data.get('confidence_scores', {}).get(field_name, 1.0)
                form_data_manager.update_field(
                    field_name=field_name,
                    value=value,
                    confidence=confidence,
                    turn=0,
                    intent=StateUserIntent.DIRECT_ANSWER
                )
            
            # Migrate skipped_fields
            for field_name in data.get('skipped_fields', []):
                form_data_manager.skip_field(field_name, turn=0)
        
        # Initialize inference cache
        inference_cache = InferenceCache.from_dict(
            data.get('inference_cache', {})
        )
        
        # Initialize context window
        if session_version >= '2.0.0' and 'context_window' in data:
            context_window = ContextWindow.from_dict(data.get('context_window', {}))
        else:
            # V1.x format - reconstruct from old structure
            context_window = ContextWindow()
            context_window.completed_fields = list(data.get('extracted_fields', {}).keys())
            context_window.skipped_fields = data.get('skipped_fields', [])
        
        # Parse timestamps
        created_at = datetime.now()
        if isinstance(data.get('created_at'), str):
            try:
                created_at = datetime.fromisoformat(data['created_at'])
            except ValueError:
                pass
        elif isinstance(data.get('created_at'), datetime):
            created_at = data['created_at']
        
        last_activity = datetime.now()
        if isinstance(data.get('last_activity'), str):
            try:
                last_activity = datetime.fromisoformat(data['last_activity'])
            except ValueError:
                pass
        elif isinstance(data.get('last_activity'), datetime):
            last_activity = data['last_activity']
        
        session = cls(
            id=data['id'],
            form_schema=data['form_schema'],
            form_url=data['form_url'],
            form_data_manager=form_data_manager,
            inference_cache=inference_cache,
            context_window=context_window,
            conversation_history=data.get('conversation_history', []),
            current_question_batch=data.get('current_question_batch', []),
            created_at=created_at,
            last_activity=last_activity,
            conversation_context=ConversationContext.from_dict(
                data.get('conversation_context', {})
            ),
            undo_stack=data.get('undo_stack', []),
            correction_history=data.get('correction_history', []),
            field_attempt_counts=data.get('field_attempt_counts', {}),
            shown_milestones=set(data.get('shown_milestones', [])),
            turns_per_field=data.get('turns_per_field', {}),
            session_version='2.0.0'  # Upgrade to new version on load
        )
        
        # Initialize context window from schema if needed
        if session.form_schema and not session.context_window.pending_fields:
            session.context_window.initialize_from_schema(session.form_schema)
        
        return session

