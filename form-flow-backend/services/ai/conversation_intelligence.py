"""
Conversational Intelligence Module

Provides enhanced conversational capabilities for the form-filling agent:
- Context tracking (sentiment, confusion, preferences)
- Intent recognition (corrections, help, status, etc.)
- Adaptive response generation
- Correction/undo handling
- Progress tracking
- Personality configuration

Usage:
    from services.ai.conversation_intelligence import (
        ConversationContext,
        IntentRecognizer,
        AdaptiveResponseGenerator,
        ProgressTracker,
    )
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from utils.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Enums
# =============================================================================

class UserSentiment(str, Enum):
    """User sentiment states."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    CONFUSED = "confused"


class UserIntent(str, Enum):
    """Recognized user intents."""
    CORRECTION = "correction"
    CLARIFICATION = "clarification"
    CONFIRMATION = "confirmation"
    NEGATION = "negation"
    SKIP = "skip"
    HELP = "help"
    BACK = "back"
    UNDO = "undo"
    STATUS = "status"
    SMALL_TALK = "small_talk"
    DATA = "data"  # Contains actual form data


# =============================================================================
# Conversation Context
# =============================================================================

@dataclass
class ConversationContext:
    """
    Enhanced conversation context tracking.

    Tracks user sentiment, confusion levels, and interaction patterns
    to enable more natural and helpful responses.
    """
    user_sentiment: UserSentiment = UserSentiment.NEUTRAL
    confusion_count: int = 0
    clarification_requests: List[str] = field(default_factory=list)
    user_preference_style: str = "balanced"  # concise, detailed, casual, formal
    repeated_corrections: Dict[str, int] = field(default_factory=dict)
    topic_switches: int = 0
    last_intent: Optional[UserIntent] = None
    positive_interactions: int = 0
    negative_interactions: int = 0
    clean_turn_count: int = 0  # Track clean turns for negative decay
    
    # Markers for detection
    CONFUSION_MARKERS = [
        'what?', 'huh?', 'confused', "don't understand", "dont understand",
        'what do you mean', 'sorry?', 'repeat', 'again?', "didn't get",
        "didnt get", 'unclear', 'not sure what'
    ]
    
    FRUSTRATION_MARKERS = [
        'already said', 'told you', 'annoying', 'frustrating',
        'stop asking', 'enough', 'ugh', 'just', 'come on', 'seriously'
    ]
    
    POSITIVE_MARKERS = [
        'thanks', 'thank you', 'great', 'perfect', 'awesome', 'cool',
        'nice', 'good', 'helpful', 'amazing', 'excellent', 'wonderful'
    ]
    
    def update_from_input(self, user_input: str) -> None:
        """
        Analyze user input to update context state using weighted scoring.
        
        Uses accumulated scores instead of early returns to handle
        mixed signals (e.g., "No problem, my email is...").
        """
        lower_input = user_input.lower().strip()
        
        # Weighted scoring - accumulate signals
        scores = {'confusion': 0, 'negative': 0, 'positive': 0}
        
        # Check all marker types
        for marker in self.CONFUSION_MARKERS:
            if marker in lower_input:
                scores['confusion'] += 2
                
        for marker in self.FRUSTRATION_MARKERS:
            if marker in lower_input:
                scores['negative'] += 2
                
        for marker in self.POSITIVE_MARKERS:
            if marker in lower_input:
                scores['positive'] += 1
        
        # Resolve sentiment by highest score
        max_score = max(scores.values())
        
        if max_score == 0:
            # No signals detected - clean turn
            self.clean_turn_count += 1
            
            # Decay negative state after 3 clean turns
            if self.clean_turn_count >= 3 and self.negative_interactions > 0:
                self.negative_interactions = max(0, self.negative_interactions - 1)
                self.clean_turn_count = 0
                logger.debug("Decaying negative state after clean turns")
            
            # Return to neutral from positive
            if self.user_sentiment == UserSentiment.POSITIVE:
                self.user_sentiment = UserSentiment.NEUTRAL
            return
        
        # Reset clean turn count on any signal
        self.clean_turn_count = 0
        
        if scores['confusion'] >= scores['negative'] and scores['confusion'] >= scores['positive']:
            self.confusion_count += 1
            self.user_sentiment = UserSentiment.CONFUSED
            logger.debug(f"Confusion detected (count: {self.confusion_count})")
        elif scores['negative'] > scores['positive']:
            self.user_sentiment = UserSentiment.NEGATIVE
            self.negative_interactions += 1
            logger.debug("Frustration detected")
        elif scores['positive'] > 0:
            self.user_sentiment = UserSentiment.POSITIVE
            self.positive_interactions += 1
            # Reset confusion on positive
            self.confusion_count = max(0, self.confusion_count - 1)
            logger.debug("Positive sentiment detected")
    
    def record_correction(self, field_name: str) -> None:
        """Record a field correction."""
        self.repeated_corrections[field_name] = (
            self.repeated_corrections.get(field_name, 0) + 1
        )
    
    def needs_extra_clarity(self) -> bool:
        """Check if user needs extra clarification."""
        return self.confusion_count >= 2
    
    def is_frustrated(self) -> bool:
        """Check if user seems frustrated."""
        return (
            self.user_sentiment == UserSentiment.NEGATIVE or
            self.negative_interactions >= 2
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for session storage."""
        return {
            'user_sentiment': self.user_sentiment.value,
            'confusion_count': self.confusion_count,
            'clarification_requests': self.clarification_requests,
            'user_preference_style': self.user_preference_style,
            'repeated_corrections': self.repeated_corrections,
            'topic_switches': self.topic_switches,
            'last_intent': self.last_intent.value if self.last_intent else None,
            'positive_interactions': self.positive_interactions,
            'negative_interactions': self.negative_interactions,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationContext':
        """Deserialize from session storage."""
        ctx = cls()
        if data:
            ctx.user_sentiment = UserSentiment(data.get('user_sentiment', 'neutral'))
            ctx.confusion_count = data.get('confusion_count', 0)
            ctx.clarification_requests = data.get('clarification_requests', [])
            ctx.user_preference_style = data.get('user_preference_style', 'balanced')
            ctx.repeated_corrections = data.get('repeated_corrections', {})
            ctx.topic_switches = data.get('topic_switches', 0)
            last_intent = data.get('last_intent')
            ctx.last_intent = UserIntent(last_intent) if last_intent else None
            ctx.positive_interactions = data.get('positive_interactions', 0)
            ctx.negative_interactions = data.get('negative_interactions', 0)
        return ctx


# =============================================================================
# Intent Recognition
# =============================================================================

class IntentRecognizer:
    """
    Recognize user intents beyond data extraction.
    
    Enables the agent to understand what the user wants to do,
    not just extract data from their input.
    """
    
    # Intent patterns (order matters - more specific first)
    INTENT_PATTERNS = {
        UserIntent.CORRECTION: [
            r'^actually\b', r'\bi meant\b', r'^no[,\s]+(?!problem|worries)',
            r'\bnot\s+\w+[,\s]+(?:it\'?s|its)\b', r'\bcorrection\b',
            r'\bwrong\b', r'\bchange that\b', r'\bfix that\b',
            r'\blet me correct\b', r'\bthat\'?s not right\b'
        ],
        UserIntent.UNDO: [
            r'\bundo\b', r'\bgo back\b', r'\bprevious\b', r'\blast one\b',
            r'\btake that back\b', r'\bremove that\b', r'\bdelete that\b'
        ],
        UserIntent.BACK: [
            r'\bback\b', r'\bbefore\b', r'\bearlier\b'
        ],
        UserIntent.CLARIFICATION: [
            r'\bwhat do you mean\b', r'\bwhat does that mean\b',
            r'\bwhich\b.*\?', r'\bcan you explain\b', r'\bwhat\'?s\b.*\?',
            r'\bhuh\b', r'\bsorry\b.*\?', r'\bconfused\b'
        ],
        UserIntent.CONFIRMATION: [
            r'^yes\b', r'^yeah\b', r'^yep\b', r'^yup\b', r'\bcorrect\b',
            r'\bright\b', r'\bthat\'?s right\b', r'\bexactly\b', r'^sure\b',
            r'^ok\b', r'^okay\b'
        ],
        UserIntent.NEGATION: [
            r'^no$', r'^nope$', r'\bnot really\b', r'\bincorrect\b',
            r'\bthat\'?s wrong\b', r'^nah\b'
        ],
        UserIntent.SKIP: [
            r'\bskip\b', r'\bpass\b', r'\bnext\b', r'\blater\b',
            r"\bdon\'?t have\b", r'\bnot sure\b', r'\bno idea\b',
            r'\bleave (?:it )?blank\b', r'\bmove on\b'
        ],
        UserIntent.HELP: [
            r'\bhelp\b', r'\bwhat should i\b', r'\bhow do i\b',
            r'\bexample\b', r'\bfor instance\b', r'\bshow me\b',
            r'\bi don\'?t know\b', r'\bwhat to say\b'
        ],
        UserIntent.STATUS: [
            r'\bhow many\b', r'\bprogress\b', r'\balmost done\b',
            r'\bhow much\b.*\bleft\b', r'\bremaining\b', r'\bhow long\b'
        ],
        UserIntent.SMALL_TALK: [
            r'^hi$', r'^hello$', r'^hey$', r'\bhow are you\b',
            r'^thanks?$', r'^thank you$', r'\bgood morning\b',
            r'\bgood afternoon\b', r'\bgood evening\b'
        ],
    }
    
    def __init__(self):
        """Initialize with compiled patterns."""
        self._compiled_patterns = {
            intent: [re.compile(p, re.IGNORECASE) for p in patterns]
            for intent, patterns in self.INTENT_PATTERNS.items()
        }
    
    def detect_intent(self, user_input: str) -> Tuple[Optional[UserIntent], float]:
        """
        Detect primary user intent with confidence score.
        
        Uses priority gating to avoid misclassifying data as intents.
        
        Args:
            user_input: Raw user input
            
        Returns:
            Tuple of (intent, confidence) or (None, 0.0) if no intent detected
        """
        user_input = user_input.strip()
        user_lower = user_input.lower()
        words = user_input.split()
        
        # --- PRIORITY GATING ---
        # Long input with strong data signals → bias toward DATA
        if len(words) > 5 and self._contains_strong_data_signals(user_input):
            logger.debug("Priority gating: long input with data signals → DATA")
            return UserIntent.DATA, 0.90
        
        # Short input that's mostly data → likely DATA
        if len(words) <= 5 and self._contains_strong_data_signals(user_input):
            # Check if any intent pattern matches at start
            for intent, patterns in self._compiled_patterns.items():
                for pattern in patterns:
                    if pattern.pattern.startswith('^') and pattern.search(user_lower):
                        # Intent at start, but also has data → return both signals
                        return intent, 0.75  # Lower confidence due to mixed signals
            return UserIntent.DATA, 0.85
        
        # --- STANDARD INTENT DETECTION ---
        for intent, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(user_lower):
                    # Higher confidence for start-of-string matches
                    if pattern.pattern.startswith('^'):
                        return intent, 0.95
                    return intent, 0.85
        
        # If no special intent, check if it contains data
        if self.has_data_content(user_input):
            return UserIntent.DATA, 0.80
        
        return None, 0.0
    
    def _contains_strong_data_signals(self, user_input: str) -> bool:
        """Check if input contains strong data signals (emails, numbers, etc.)."""
        import re
        
        # Email pattern
        if re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', user_input):
            return True
        
        # Phone-like numbers (5+ digits)
        if re.search(r'\d{5,}', user_input.replace(' ', '')):
            return True
        
        # Date patterns
        if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', user_input):
            return True
        
        # Names with capitalization (First Last pattern)
        if re.search(r'[A-Z][a-z]+ [A-Z][a-z]+', user_input):
            return True
        
        return False
    
    def has_data_content(self, user_input: str) -> bool:
        """
        Check if input contains actual form data (not just commands).
        
        Args:
            user_input: Raw user input
            
        Returns:
            True if input seems to contain data
        """
        # Remove common intent phrases and check remaining content
        cleaned = user_input.lower()
        
        # Remove all intent patterns
        for patterns in self.INTENT_PATTERNS.values():
            for pattern in patterns:
                cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Check if substantial text remains
        remaining_words = cleaned.strip().split()
        return len(remaining_words) >= 1
    
    def extract_correction_info(
        self, 
        user_input: str
    ) -> Optional[Tuple[str, str]]:
        """
        Extract correction details from input.
        
        Args:
            user_input: Input containing correction
            
        Returns:
            Tuple of (field_identifier, new_value) or None
        """
        correction_patterns = [
            r'(?:actually|i meant|no)[,\s]+(?:my\s+)?(\w+)\s+is\s+(.+)',
            r'(?:change|correct|fix)\s+(?:my\s+)?(\w+)\s+to\s+(.+)',
            r'not\s+(.+?)[,\s]+(?:it\'?s|its|it is)\s+(.+)',
            r'(\w+)\s+should be\s+(.+)',
        ]
        
        for pattern in correction_patterns:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                field_identifier = match.group(1).strip().lower()
                new_value = match.group(2).strip()
                # Clean up trailing punctuation
                new_value = re.sub(r'[.,!?]+$', '', new_value)
                return field_identifier, new_value
        
        return None


# =============================================================================
# Progress Tracking
# =============================================================================

class ProgressTracker:
    """Track and communicate form completion progress."""
    
    MILESTONES = {
        25: "Great start! We're a quarter of the way through.",
        50: "Awesome! We're halfway done!",
        75: "Almost there! Just a few more questions.",
        90: "So close! Just wrapping up.",
    }
    
    ENCOURAGEMENTS = [
        "You're doing great!",
        "Nice work!",
        "Smooth sailing!",
        "Making good progress!",
    ]
    
    @staticmethod
    def calculate_progress(
        extracted_count: int,
        total_count: int
    ) -> int:
        """Calculate progress percentage."""
        if total_count == 0:
            return 100
        return int((extracted_count / total_count) * 100)
    
    @staticmethod
    def get_milestone_message(
        extracted_count: int,
        total_count: int,
        include_count: bool = True
    ) -> Optional[str]:
        """
        Get milestone message if at a milestone.
        
        Args:
            extracted_count: Number of fields completed
            total_count: Total number of fields
            include_count: Whether to include field count
            
        Returns:
            Milestone message or None
        """
        progress = ProgressTracker.calculate_progress(extracted_count, total_count)
        remaining = total_count - extracted_count
        
        # Check for exact milestone
        for threshold, message in ProgressTracker.MILESTONES.items():
            if progress >= threshold and progress < threshold + 10:
                if include_count and remaining > 0:
                    return f"{message} ({remaining} fields left)"
                return message
        
        return None
    
    @staticmethod
    def get_status_message(
        extracted_count: int,
        total_count: int
    ) -> str:
        """Get detailed status message when user asks for progress."""
        progress = ProgressTracker.calculate_progress(extracted_count, total_count)
        remaining = total_count - extracted_count
        
        if remaining == 0:
            return "We're all done! All fields have been filled."
        elif remaining == 1:
            return f"Almost finished! Just 1 more field to go ({progress}% complete)."
        else:
            return f"We've completed {extracted_count} of {total_count} fields ({progress}% done). {remaining} more to go!"
    
    @staticmethod
    def should_show_progress(extracted_count: int) -> bool:
        """Determine if we should show an unprompted progress update."""
        # Show at milestones or every 5 fields
        return extracted_count > 0 and (
            extracted_count % 5 == 0 or
            extracted_count in [1, 3, 10]
        )


# =============================================================================
# Adaptive Response Generator
# =============================================================================

class AdaptiveResponseGenerator:
    """Generate contextually appropriate, natural responses with style adaptation."""
    
    # Response variations by sentiment
    ACKNOWLEDGMENTS = {
        UserSentiment.POSITIVE: ['Perfect!', 'Excellent!', 'Awesome!', 'Great!', 'Wonderful!'],
        UserSentiment.NEUTRAL: ['Got it!', 'Thanks!', 'Okay!', 'Noted!', 'Alright!'],
        UserSentiment.CONFUSED: ['I see.', 'Alright,', 'Okay,', 'Got it.'],
        UserSentiment.NEGATIVE: ['Thank you.', 'Understood.', 'Noted.', 'Got it.'],
    }
    
    # Style matrix - responses by user_preference_style
    STYLE_VARIATIONS = {
        'concise': {
            'ack': 'Got it.',
            'question': "What's your {label}?",
            'next': "{label}?",
        },
        'casual': {
            'ack': 'Cool!',
            'question': "So what's your {label}?",
            'next': "And {label}?",
        },
        'formal': {
            'ack': 'Thank you.',
            'question': "May I have your {label}, please?",
            'next': "Could you provide your {label}?",
        },
        'detailed': {
            'ack': "I've recorded that, thank you!",
            'question': "Now I need your {label}. Please provide it when ready.",
            'next': "Next, I'll need your {label}.",
        },
        'balanced': {
            'ack': 'Got it!',
            'question': "What's your {label}?",
            'next': "And your {label}?",
        },
    }
    
    QUESTION_STYLES = [
        "What's your {label}?",
        "And your {label}?",
        "Can you tell me your {label}?",
        "Now, what's your {label}?",
        "How about your {label}?",
    ]
    
    @classmethod
    def _get_style_adjusted_ack(cls, context: 'ConversationContext') -> str:
        """
        Get acknowledgment adjusted for user style, confusion, and frustration.
        
        Uses deterministic selection when user is confused/frustrated (no randomness).
        """
        style = context.user_preference_style
        
        # Deterministic phrasing when confused or frustrated
        if context.is_frustrated() or context.needs_extra_clarity():
            # Use simple, consistent acknowledgment (first item, no randomness)
            return cls.ACKNOWLEDGMENTS.get(context.user_sentiment, ['Got it.'])[0]
        
        # Use style matrix if available
        if style in cls.STYLE_VARIATIONS:
            return cls.STYLE_VARIATIONS[style]['ack']
        
        # Default: sentiment-based with variety
        acks = cls.ACKNOWLEDGMENTS.get(context.user_sentiment, cls.ACKNOWLEDGMENTS[UserSentiment.NEUTRAL])
        return acks[hash(str(context.positive_interactions)) % len(acks)]
    
    @classmethod
    def _get_style_adjusted_question(cls, label: str, context: 'ConversationContext', is_first: bool = True) -> str:
        """Get question adjusted for user style."""
        style = context.user_preference_style
        
        if style in cls.STYLE_VARIATIONS:
            template = cls.STYLE_VARIATIONS[style]['question' if is_first else 'next']
            return template.format(label=label)
        
        # Default
        return f"What's your {label}?"
    
    @classmethod
    def generate_response(
        cls,
        extracted_values: Dict[str, str],
        remaining_fields: List[Dict[str, Any]],
        context: ConversationContext,
        current_batch: List[Dict[str, Any]],
        user_intent: Optional[UserIntent] = None,
        extracted_count: int = 0,
        total_count: int = 0
    ) -> str:
        """
        Generate an adaptive, natural response.
        
        Args:
            extracted_values: Values extracted this turn
            remaining_fields: Fields still to fill
            context: Conversation context
            current_batch: Current question batch
            user_intent: Detected user intent
            extracted_count: Total extracted so far
            total_count: Total fields in form
            
        Returns:
            Natural language response
        """
        # Handle extra clarity needed
        if context.needs_extra_clarity():
            return cls._generate_clarification_response(current_batch)
        
        # Handle frustration
        if context.is_frustrated():
            return cls._generate_empathetic_response(
                extracted_count, total_count, remaining_fields
            )
        
        # Handle small talk
        if user_intent == UserIntent.SMALL_TALK:
            return cls._handle_small_talk(extracted_count, len(remaining_fields))
        
        # Standard response
        return cls._generate_standard_response(
            extracted_values,
            remaining_fields,
            context,
            extracted_count
        )
    
    @classmethod
    def _generate_clarification_response(
        cls,
        current_batch: List[Dict[str, Any]],
        confusion_count: int = 1
    ) -> str:
        """
        Extra clear response when user is confused.
        
        Progressive clarification:
        - 1st confusion: Short rephrase
        - 2nd confusion: Provide example
        - 3rd+ confusion: Structured options
        """
        if not current_batch:
            return "Let me be clearer. I'm helping you fill out a form by collecting some information. Just answer naturally!"
        
        field = current_batch[0]
        label = field.get('label', field.get('name', 'information'))
        field_type = field.get('type', 'text').lower()
        
        # Progressive clarification based on confusion count
        if confusion_count == 1:
            # 1st confusion: Short rephrase
            if 'name' in label.lower():
                return f"I just need your {label} - like 'John Smith'."
            return f"Could you tell me your {label}?"
        
        elif confusion_count == 2:
            # 2nd confusion: Provide example
            examples = {
                'email': f"For your email, try: 'john at example dot com' or 'john@example.com'.",
                'tel': f"For your phone, say the digits: 'five five five one two three four'.",
                'text': f"For {label}, just say it directly, like 'My {label} is ...'.",
            }
            if 'name' in label.lower():
                return "Try saying: 'First name John, last name Smith' or just 'John Smith'."
            return examples.get(field_type, f"Try saying: 'My {label} is ...' followed by your answer.")
        
        else:
            # 3rd+ confusion: Structured options
            return (
                f"Having trouble with {label}? Here are your options:\n"
                f"• Say '{label}' directly\n"
                f"• Say 'skip' to skip this field\n"
                f"• Say 'help' for more assistance"
            )
    
    @classmethod
    def _generate_empathetic_response(
        cls,
        extracted_count: int,
        total_count: int,
        remaining_fields: List[Dict[str, Any]]
    ) -> str:
        """Empathetic response when user shows frustration."""
        progress = ProgressTracker.calculate_progress(extracted_count, total_count)
        remaining = len(remaining_fields)
        
        if progress > 70:
            return f"I appreciate your patience! We're {progress}% done - just {remaining} more quick {'question' if remaining == 1 else 'questions'}."
        elif progress > 40:
            return f"I know forms can be tedious. We're halfway there with {remaining} fields left. Let's power through!"
        else:
            next_field = remaining_fields[0] if remaining_fields else None
            if next_field:
                label = next_field.get('label', next_field.get('name', ''))
                return f"Thanks for your patience. Let's just get your {label} and keep moving."
            return "Thanks for sticking with me. Let's continue."
    
    @classmethod
    def _handle_small_talk(
        cls,
        extracted_count: int,
        remaining_count: int
    ) -> str:
        """Handle casual conversation naturally."""
        if extracted_count == 0:
            return "Hey there! I'm here to help you fill out this form quickly. Ready to get started?"
        elif remaining_count == 0:
            return "We're all done! Thanks for chatting with me. Ready to submit?"
        else:
            return f"Thanks! We're making good progress. {remaining_count} more {'field' if remaining_count == 1 else 'fields'} to go."
    
    @classmethod
    def _generate_standard_response(
        cls,
        extracted_values: Dict[str, str],
        remaining_fields: List[Dict[str, Any]],
        context: ConversationContext,
        extracted_count: int
    ) -> str:
        """Standard acknowledgment + next question."""
        # Get acknowledgment based on sentiment
        ack_list = cls.ACKNOWLEDGMENTS.get(
            context.user_sentiment,
            cls.ACKNOWLEDGMENTS[UserSentiment.NEUTRAL]
        )
        ack = ack_list[extracted_count % len(ack_list)]
        
        # Check if form is complete
        if not remaining_fields:
            return f"{ack} We've got everything we need! Ready to submit the form?"
        
        # Generate next question
        next_field = remaining_fields[0]
        label = next_field.get('label', next_field.get('name', 'next field'))
        
        # Vary question style
        style_idx = extracted_count % len(cls.QUESTION_STYLES)
        question = cls.QUESTION_STYLES[style_idx].format(label=label)
        
        # Combine with extracted acknowledgment if we got values
        if extracted_values:
            return f"{ack} {question}"
        else:
            # No extraction - be more encouraging
            return f"No problem. {question}"


# =============================================================================
# Correction History
# =============================================================================

@dataclass
class CorrectionRecord:
    """Record of a field value correction."""
    field_name: str
    original_value: str
    corrected_value: str
    timestamp: datetime = field(default_factory=datetime.now)
    correction_reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'field_name': self.field_name,
            'original_value': self.original_value,
            'corrected_value': self.corrected_value,
            'timestamp': self.timestamp.isoformat(),
            'correction_reason': self.correction_reason,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CorrectionRecord':
        return cls(
            field_name=data['field_name'],
            original_value=data['original_value'],
            corrected_value=data['corrected_value'],
            timestamp=datetime.fromisoformat(data['timestamp']) if isinstance(data.get('timestamp'), str) else datetime.now(),
            correction_reason=data.get('correction_reason', ''),
        )


@dataclass
class UndoRecord:
    """Record for undo stack."""
    field_name: str
    value: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'field_name': self.field_name,
            'value': self.value,
            'timestamp': self.timestamp.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UndoRecord':
        return cls(
            field_name=data['field_name'],
            value=data['value'],
            timestamp=datetime.fromisoformat(data['timestamp']) if isinstance(data.get('timestamp'), str) else datetime.now(),
        )


# =============================================================================
# Personality Configuration
# =============================================================================

class PersonalityConfig:
    """Configure agent personality and response variations."""
    
    GREETING_VARIATIONS = [
        "Hi there! I'll help you fill out this form quickly.",
        "Hello! Ready to get through this form together?",
        "Hey! Let's make this form easy and quick.",
        "Hi! I'm here to help you complete this form. Let's get started!",
    ]
    
    COMPLETION_MESSAGES = [
        "Perfect! We've got everything. Ready to submit?",
        "Excellent! All done collecting information. Shall we submit?",
        "Great work! We're finished. Ready to submit the form?",
        "All set! Everything's filled in. Want to submit now?",
    ]
    
    FAREWELL_MESSAGES = [
        "Thanks for using FormFlow! Have a great day!",
        "Form submitted successfully! Take care!",
        "All done! Thanks for your time!",
    ]
    
    @classmethod
    def get_greeting(cls, form_field_count: int = 0) -> str:
        """Get a greeting message."""
        import random
        greeting = random.choice(cls.GREETING_VARIATIONS)
        if form_field_count > 0:
            greeting += f" We have {form_field_count} fields to fill."
        return greeting
    
    @classmethod
    def get_completion_message(cls) -> str:
        """Get a completion message."""
        import random
        return random.choice(cls.COMPLETION_MESSAGES)
    
    @classmethod
    def get_farewell(cls) -> str:
        """Get a farewell message."""
        import random
        return random.choice(cls.FAREWELL_MESSAGES)
