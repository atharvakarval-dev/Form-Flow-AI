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
        }
