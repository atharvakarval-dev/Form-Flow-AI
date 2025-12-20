"""
Utilities Module

Provides shared utilities across the application:
- Logging configuration
- Custom exceptions
- Rate limiting
- Input sanitization
"""

from .logging import get_logger, setup_logging, log_api_call, log_form_action
from .exceptions import (
    FormFlowError,
    FormParsingError,
    FormSubmissionError,
    FormValidationError,
    SpeechGenerationError,
    SpeechRecognitionError,
    VoiceProcessingError,
    AIServiceError,
    AuthenticationError,
    AuthorizationError,
    ExternalServiceError,
)
from .rate_limit import (
    limiter,
    rate_limit_exceeded_handler,
    RATE_LIMITS,
    limit_auth,
    limit_scrape,
    limit_submit,
    limit_speech,
)
from .sanitize import (
    validate_form_url,
    is_google_form_url,
    sanitize_string,
    sanitize_field_name,
)

__all__ = [
    # Logging
    "get_logger",
    "setup_logging",
    "log_api_call",
    "log_form_action",
    # Exceptions
    "FormFlowError",
    "FormParsingError",
    "FormSubmissionError",
    "FormValidationError",
    "SpeechGenerationError",
    "SpeechRecognitionError",
    "VoiceProcessingError",
    "AIServiceError",
    "AuthenticationError",
    "AuthorizationError",
    "ExternalServiceError",
    # Rate Limiting
    "limiter",
    "rate_limit_exceeded_handler",
    "RATE_LIMITS",
    "limit_auth",
    "limit_scrape",
    "limit_submit",
    "limit_speech",
    # Sanitization
    "validate_form_url",
    "is_google_form_url",
    "sanitize_string",
    "sanitize_field_name",
]
