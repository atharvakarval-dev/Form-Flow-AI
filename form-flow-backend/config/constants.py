"""
Application Constants

Centralizes magic numbers and configuration values for the conversation agent.
Avoids hardcoded values scattered throughout the codebase.

Usage:
    from config.constants import CONFIDENCE_THRESHOLD_HIGH, SESSION_TTL_MINUTES
"""

# =============================================================================
# Confidence Thresholds
# =============================================================================

# High confidence - accept without confirmation
CONFIDENCE_THRESHOLD_HIGH = 0.95

# Medium confidence - accept but may note uncertainty
CONFIDENCE_THRESHOLD_MEDIUM = 0.70

# Low confidence - needs confirmation from user
CONFIDENCE_THRESHOLD_LOW = 0.60

# Below this, extraction is considered failed
CONFIDENCE_THRESHOLD_REJECT = 0.40


# =============================================================================
# Session Settings
# =============================================================================

# Session time-to-live in minutes
SESSION_TTL_MINUTES = 30

# Maximum number of local cached sessions (prevents memory leak)
MAX_LOCAL_SESSIONS = 1000

# Session lock timeout in seconds (for distributed locks)
SESSION_LOCK_TIMEOUT_SECONDS = 10


# =============================================================================
# Conversation Context
# =============================================================================

# Number of recent conversation turns to include in LLM context
MAX_CONVERSATION_CONTEXT_TURNS = 4

# Maximum number of fields to show in "upcoming" context
MAX_UPCOMING_FIELDS_CONTEXT = 5


# =============================================================================
# LLM/API Settings
# =============================================================================

# Maximum retry attempts for LLM calls
LLM_MAX_RETRIES = 3

# Base delay for exponential backoff (seconds)
LLM_RETRY_BASE_DELAY = 1.0

# Maximum delay cap for retries (seconds)
LLM_RETRY_MAX_DELAY = 10.0

# LLM temperature for extraction (lower = more consistent)
LLM_TEMPERATURE = 0.3

# Default model name
DEFAULT_LLM_MODEL = "gemini-2.5-flash-lite"


# =============================================================================
# Batching Settings
# =============================================================================

# Maximum questions per batch by complexity
BATCH_SIZE_SIMPLE = 4      # text, email, phone
BATCH_SIZE_MODERATE = 2    # select, radio
BATCH_SIZE_COMPLEX = 1     # textarea, file


# =============================================================================
# Input Validation
# =============================================================================

# Maximum user input length (prevents DoS)
MAX_USER_INPUT_LENGTH = 10000

# Minimum user input length
MIN_USER_INPUT_LENGTH = 1


# =============================================================================
# Field Type Classifications
# =============================================================================

SIMPLE_FIELD_TYPES = {'text', 'email', 'tel', 'number', 'date'}
MODERATE_FIELD_TYPES = {'select', 'radio'}
COMPLEX_FIELD_TYPES = {'textarea', 'file', 'checkbox'}


# =============================================================================
# Extraction Validation
# =============================================================================

# Phone number length range
PHONE_MIN_DIGITS = 10
PHONE_MAX_DIGITS = 15

# Name word count range
NAME_MIN_WORDS = 1
NAME_MAX_WORDS = 4

# Generic text length range
TEXT_MIN_LENGTH = 2
TEXT_MAX_LENGTH = 500
