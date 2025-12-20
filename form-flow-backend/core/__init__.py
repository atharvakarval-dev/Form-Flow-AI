"""
Core Module

Provides database, models, schemas, and dependencies for the application.
"""

from .database import Base, engine, get_db, check_database_health
from .models import User, FormSubmission
from .schemas import (
    UserBase,
    UserCreate,
    UserLogin,
    UserResponse,
    FormSubmissionResponse,
    Token,
    TokenData,
    HealthResponse,
)
from .dependencies import (
    get_voice_processor,
    get_speech_service,
    get_form_submitter,
    get_gemini_service,
    get_vosk_service,
    get_speech_data,
    update_speech_data,
    clear_speech_data,
)

__all__ = [
    # Database
    "Base",
    "engine",
    "get_db",
    "check_database_health",
    # Models
    "User",
    "FormSubmission",
    # Schemas
    "UserBase",
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "FormSubmissionResponse",
    "Token",
    "TokenData",
    "HealthResponse",
    # Dependencies
    "get_voice_processor",
    "get_speech_service",
    "get_form_submitter",
    "get_gemini_service",
    "get_vosk_service",
    "get_speech_data",
    "update_speech_data",
    "clear_speech_data",
]
