"""
Custom Exceptions Module

Defines application-specific exceptions for clearer error handling.
All exceptions inherit from a base FormFlowError for easy catching.

Usage:
    from utils.exceptions import FormParsingError, FormSubmissionError
    
    try:
        parse_form(url)
    except FormParsingError as e:
        logger.error(f"Parsing failed: {e}")
"""

from typing import Optional, Dict, Any


class FormFlowError(Exception):
    """
    Base exception for all Form Flow application errors.
    
    Attributes:
        message: Human-readable error message
        details: Additional error details (optional)
        status_code: HTTP status code to return (optional)
    """
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500
    ):
        self.message = message
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details
        }


# =============================================================================
# Form Processing Exceptions
# =============================================================================

class FormParsingError(FormFlowError):
    """
    Raised when form scraping/parsing fails.
    
    Common causes:
        - Invalid URL
        - Page not accessible
        - No forms found on page
        - Timeout during scraping
    """
    
    def __init__(
        self,
        message: str = "Failed to parse form",
        url: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            details={"url": url, **(details or {})},
            status_code=400
        )


class FormSubmissionError(FormFlowError):
    """
    Raised when form submission fails.
    
    Common causes:
        - Form validation failed on target site
        - Network error during submission
        - CAPTCHA encountered
        - Session timeout
    """
    
    def __init__(
        self,
        message: str = "Failed to submit form",
        url: Optional[str] = None,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            details={"url": url, "field": field, **(details or {})},
            status_code=500
        )


class FormValidationError(FormFlowError):
    """
    Raised when form data validation fails.
    
    Common causes:
        - Required field missing
        - Invalid field format
        - Value not in allowed options
    """
    
    def __init__(
        self,
        message: str = "Form validation failed",
        field: Optional[str] = None,
        value: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            details={"field": field, "value": value, **(details or {})},
            status_code=422
        )


# =============================================================================
# Voice/Speech Exceptions
# =============================================================================

class SpeechGenerationError(FormFlowError):
    """
    Raised when text-to-speech generation fails.
    
    Common causes:
        - ElevenLabs API error
        - Invalid API key
        - Rate limit exceeded
    """
    
    def __init__(
        self,
        message: str = "Failed to generate speech",
        text: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            details={"text_preview": text[:50] if text else None, **(details or {})},
            status_code=500
        )


class SpeechRecognitionError(FormFlowError):
    """
    Raised when speech-to-text recognition fails.
    
    Common causes:
        - Invalid audio format
        - Vosk model not loaded
        - Audio too short/silent
    """
    
    def __init__(
        self,
        message: str = "Failed to recognize speech",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            details=details,
            status_code=400
        )


class VoiceProcessingError(FormFlowError):
    """
    Raised when voice input processing fails.
    
    Common causes:
        - LLM API error
        - Invalid field context
        - Formatting failure
    """
    
    def __init__(
        self,
        message: str = "Failed to process voice input",
        field: Optional[str] = None,
        transcript: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            details={"field": field, "transcript": transcript, **(details or {})},
            status_code=500
        )


# =============================================================================
# AI/LLM Exceptions
# =============================================================================

class AIServiceError(FormFlowError):
    """
    Raised when AI/LLM service calls fail.
    
    Common causes:
        - Gemini API error
        - OpenAI API error
        - Invalid API key
        - Rate limit exceeded
    """
    
    def __init__(
        self,
        message: str = "AI service error",
        service: str = "unknown",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            details={"service": service, **(details or {})},
            status_code=502
        )


# =============================================================================
# Authentication Exceptions
# =============================================================================

class AuthenticationError(FormFlowError):
    """
    Raised when authentication fails.
    
    Common causes:
        - Invalid credentials
        - Expired token
        - Missing token
    """
    
    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            details=details,
            status_code=401
        )


class AuthorizationError(FormFlowError):
    """
    Raised when user lacks permission.
    
    Common causes:
        - Accessing another user's data
        - Insufficient role/permissions
    """
    
    def __init__(
        self,
        message: str = "Permission denied",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            details=details,
            status_code=403
        )


# =============================================================================
# External Service Exceptions
# =============================================================================

class ExternalServiceError(FormFlowError):
    """
    Raised when an external API call fails.
    
    Use specific exceptions (SpeechGenerationError, AIServiceError) when possible.
    """
    
    def __init__(
        self,
        message: str = "External service error",
        service: str = "unknown",
        status_code: int = 502,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            details={"service": service, **(details or {})},
            status_code=status_code
        )
