"""
Profile Service Configuration

Centralized configuration for the behavioral profile system.
Defines rate limits, quality gates, and system constants.
"""

from typing import Dict, List

# =============================================================================
# Production Safeguards
# =============================================================================

class ProfileConfig:
    # Rate Limiting
    MAX_UPDATES_PER_HOUR: int = 5
    MAX_LLM_CALLS_PER_DAY: int = 1000
    
    # Quality Gates
    MIN_QUESTIONS_FOR_PROFILE: int = 3  # Minimum questions to trigger update
    MIN_ANSWER_LENGTH: int = 2          # Minimum chars for an answer to count
    MIN_CONFIDENCE_SCORE: float = 0.5   # Minimum confidence to accept update
    
    # Validation
    MAX_PROFILE_TOKENS: int = 3000      # Soft limit for profile length
    MAX_PROFILE_WORDS: int = 1000       # Hard word limit
    
    # Update Triggers
    UPDATE_FORM_INTERVAL: int = 1       # Update after EVERY form
    UPDATE_DAYS_INTERVAL: int = 30      # Update if stale
    
    # Circuit Breaker
    MAX_CONSECUTIVE_FAILURES: int = 5
    CIRCUIT_RESET_TIMEOUT: int = 300    # Seconds
    
    # Feature Flags
    ENABLE_PROFILING: bool = True
    ENABLE_VERSIONING: bool = True
    ENABLE_AUTO_ROLLBACK: bool = True

profile_config = ProfileConfig()
