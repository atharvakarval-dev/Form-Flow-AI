"""
Application Configuration Module

Centralizes all application settings using Pydantic Settings.
Environment variables are loaded from .env file automatically.

Usage:
    from config.settings import settings
    
    print(settings.DATABASE_URL)
    print(settings.DEBUG)
"""

from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
from typing import List, Optional
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All settings can be overridden via environment variables or .env file.
    Variable names are case-insensitive.
    """
    
    # ==========================================================================
    # Database Configuration
    # ==========================================================================
    DATABASE_URL: str = Field(
        default="postgresql://localhost/formflow",
        description="PostgreSQL connection string"
    )
    
    # ==========================================================================
    # Authentication & Security
    # ==========================================================================
    SECRET_KEY: str = Field(
        default="your_super_secret_key_change_this_in_production",
        description="JWT signing secret key"
    )
    ALGORITHM: str = Field(
        default="HS256",
        description="JWT signing algorithm"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        description="JWT token expiration time in minutes"
    )
    
    # ==========================================================================
    # External API Keys
    # ==========================================================================
    GOOGLE_API_KEY: Optional[str] = Field(
        default=None,
        description="Google Gemini API key for AI features"
    )
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenAI API key (optional, for fallback)"
    )
    ELEVENLABS_API_KEY: Optional[str] = Field(
        default=None,
        description="ElevenLabs API key for text-to-speech"
    )
    
    # ==========================================================================
    # CAPTCHA Solving Configuration
    # ==========================================================================
    TWOCAPTCHA_API_KEY: Optional[str] = Field(
        default=None,
        description="2Captcha API key for automated CAPTCHA solving"
    )
    ANTICAPTCHA_API_KEY: Optional[str] = Field(
        default=None,
        description="AntiCaptcha API key for automated CAPTCHA solving"
    )
    CAPTCHA_SOLVE_TIMEOUT: int = Field(
        default=120,
        description="Maximum seconds to wait for CAPTCHA solution"
    )
    
    # ==========================================================================
    # Redis Configuration (for caching and rate limiting)
    # ==========================================================================
    REDIS_URL: Optional[str] = Field(
        default=None,
        description="Redis connection URL for caching and rate limiting"
    )
    
    # ==========================================================================
    # CORS Configuration
    # ==========================================================================
    CORS_ORIGINS: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        description="Allowed CORS origins (comma-separated)"
    )
    
    @property
    def cors_origins_list(self) -> list:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
    
    # ==========================================================================
    # Application Settings
    # ==========================================================================
    DEBUG: bool = Field(
        default=False,
        description="Enable debug mode with verbose logging"
    )
    APP_NAME: str = Field(
        default="Form Flow AI",
        description="Application name for OpenAPI docs"
    )
    APP_VERSION: str = Field(
        default="1.0.0",
        description="Application version"
    )
    
    # ==========================================================================
    # Local LLM Configuration
    # ==========================================================================
    USE_LOCAL_LLM: bool = Field(
        default=True,
        description="Use local Phi-2 model as primary LLM (faster, free)"
    )
    LOCAL_MODEL_PATH: Optional[str] = Field(
        default=None,
        description="Custom path to local model (defaults to models/phi-2)"
    )
    
    # ==========================================================================
    # Smart Question Engine Configuration
    # ==========================================================================
    SMART_GROUPING_ENABLED: bool = Field(
        default=True,
        description="Enable Smart Question Grouping (reduces 159 fields to ~30 groups)"
    )
    SMART_GROUPING_MIN_FILL_RATIO: float = Field(
        default=0.7,
        description="Minimum field fill ratio to consider a group complete"
    )
    
    # ==========================================================================
    # Voice/Speech Configuration
    # ==========================================================================
    ELEVENLABS_VOICE_ID: str = Field(
        default="21m00Tcm4TlvDq8ikWAM",
        description="Default ElevenLabs voice ID (Rachel)"
    )
    ELEVENLABS_MODEL: str = Field(
        default="eleven_turbo_v2_5",
        description="ElevenLabs model for TTS"
    )
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra env vars
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses LRU cache to ensure settings are only loaded once.
    
    Returns:
        Settings: Application settings instance
    """
    return Settings()


# Singleton instance for easy import
settings = get_settings()
