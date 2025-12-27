"""
Greeting Handler

Generates initial greetings and first questions.
"""

from typing import Dict, List, Any

from services.ai.models import AgentResponse
from services.ai.extraction import FieldClusterer


class GreetingHandler:
    """
    Generate initial greetings for form filling sessions.
    
    Creates natural, welcoming greetings that introduce the form
    and ask the first batch of questions.
    """
    
    @staticmethod
    def generate_initial_greeting(
        session,
        clusterer: FieldClusterer
    ) -> AgentResponse:
        """
        Create greeting with first questions.
        
        Args:
            session: The conversation session
            clusterer: Field clusterer for batching
            
        Returns:
            AgentResponse with greeting and first questions
        """
        remaining_fields = session.get_remaining_fields()
        
        if not remaining_fields:
            return AgentResponse(
                message="Great news - all fields are already filled! Ready to submit?",
                extracted_values={},
                confidence_scores={},
                needs_confirmation=[],
                remaining_fields=[],
                is_complete=True,
                next_questions=[]
            )
        
        # Create batches
        batches = clusterer.create_batches(remaining_fields)
        first_batch = batches[0] if batches else [remaining_fields[0]]
        
        # Generate greeting
        greeting = GreetingHandler._create_greeting(first_batch, len(remaining_fields))
        
        # Store current batch
        session.current_question_batch = [f.get('name') for f in first_batch]
        
        return AgentResponse(
            message=greeting,
            extracted_values={},
            confidence_scores={},
            needs_confirmation=[],
            remaining_fields=remaining_fields,
            is_complete=False,
            next_questions=[
                {'name': f.get('name'), 'label': f.get('label'), 'type': f.get('type')} 
                for f in first_batch
            ]
        )
    
    @staticmethod
    def _create_greeting(first_batch: List[Dict[str, Any]], total_fields: int) -> str:
        """
        Format natural greeting based on form size.
        
        Args:
            first_batch: First batch of fields to ask
            total_fields: Total number of fields
            
        Returns:
            Greeting message string
        """
        # Opening based on form size
        if total_fields <= 5:
            opening = "Hi! Let's quickly fill out this form together. 👋"
        elif total_fields <= 10:
            opening = "Hello! I'll help you fill out this form - it won't take long! 👋"
        else:
            opening = "Hi there! I'll guide you through this form step by step. 👋"
        
        # Format question
        labels = [f.get('label', f.get('name', 'value')) for f in first_batch]
        
        if len(labels) == 1:
            question = f"Let's start with your {labels[0]}."
        elif len(labels) == 2:
            question = f"Let's start with your {labels[0]} and {labels[1]}."
        else:
            leading = ', '.join(labels[:-1])
            question = f"Let's start with your {leading}, and {labels[-1]}."
        
        return f"{opening}\n\n{question}"
