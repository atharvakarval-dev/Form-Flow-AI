"""
Response Model

Data structure for agent responses.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass  
class AgentResponse:
    """
    Response from the conversation agent.
    
    Contains extracted values, next questions, and metadata
    for the frontend to display.
    """
    message: str
    extracted_values: Dict[str, str]
    confidence_scores: Dict[str, float]
    needs_confirmation: List[str]
    remaining_fields: List[Dict[str, Any]]
    is_complete: bool
    next_questions: List[Dict[str, Any]]
    fallback_options: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[Dict[str, Any]] = field(default_factory=list)  # Contextual suggestions
    
    # Smart Grouping: Partial response fields
    status: str = "complete"  # "complete", "partial_extraction", "failed"
    missing_from_group: List[str] = field(default_factory=list)  # Field names not extracted
    requires_followup: bool = False  # True if user should provide more info for current group
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'message': self.message,
            'extracted_values': self.extracted_values,
            'confidence_scores': self.confidence_scores,
            'needs_confirmation': self.needs_confirmation,
            'remaining_fields': self.remaining_fields,
            'is_complete': self.is_complete,
            'next_questions': self.next_questions,
            'fallback_options': self.fallback_options,
            'suggestions': self.suggestions,
            # Smart Grouping fields
            'status': self.status,
            'missing_from_group': self.missing_from_group,
            'requires_followup': self.requires_followup,
        }
