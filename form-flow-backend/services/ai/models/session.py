"""
Session Model

Data classes for conversation session state management.
Pure data models with no business logic.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from services.ai.conversation_intelligence import ConversationContext


@dataclass
class ConversationSession:
    """
    Session state management.
    
    Stores all conversation state including extracted values,
    history, and user context. Pure data accessors only.
    """
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
    
    # Enhanced conversational intelligence
    conversation_context: ConversationContext = field(default_factory=ConversationContext)
    undo_stack: List[Dict[str, Any]] = field(default_factory=list)
    correction_history: List[Dict[str, Any]] = field(default_factory=list)
    field_attempt_counts: Dict[str, int] = field(default_factory=dict)
    shown_milestones: set = field(default_factory=set)
    turns_per_field: Dict[str, int] = field(default_factory=dict)
    
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
        for form in self.form_schema:
            for f in form.get('fields', []):
                field_name = f.get('name', '')
                field_type = f.get('type', '')
                
                if field_type in ['submit', 'button', 'hidden'] or f.get('hidden'):
                    continue
                if field_name in self.extracted_fields or field_name in self.skipped_fields:
                    continue
                    
                remaining.append(f)
        return remaining
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to dictionary for persistence."""
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
