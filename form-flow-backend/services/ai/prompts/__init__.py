"""
Prompts Package

LLM prompt engineering for conversation agent and profile generation.
"""

from services.ai.prompts.extraction_prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    build_extraction_context,
    get_expected_format,
)

from services.ai.prompts.profile_prompts import (
    PROFILE_CREATE_PROMPT,
    PROFILE_UPDATE_PROMPT,
    build_create_prompt,
    build_update_prompt,
    build_condense_prompt,
)

__all__ = [
    # Extraction
    'EXTRACTION_SYSTEM_PROMPT',
    'build_extraction_context',
    'get_expected_format',
    # Profile
    'PROFILE_CREATE_PROMPT',
    'PROFILE_UPDATE_PROMPT',
    'build_create_prompt',
    'build_update_prompt',
    'build_condense_prompt',
]
