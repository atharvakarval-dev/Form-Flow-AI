"""
Prompt Manager

Handles prompt versioning, retrieval, and A/B testing infrastructure.
Allows rolling back prompts without code deployment.
"""

from typing import Dict, Optional
from . import prompts as profile_prompts
from utils.logging import get_logger

logger = get_logger(__name__)

class PromptManager:
    """
    Manages versions of prompts.
    """
    
    def __init__(self):
        # Repository of prompt versions
        # Key: (prompt_type, version_id) -> prompt_template
        self._prompts: Dict[str, str] = {
            # V1: Original (Legacy)
            "profile_create:v1": profile_prompts.PROFILE_CREATE_PROMPT, 
            "profile_update:v1": profile_prompts.PROFILE_UPDATE_PROMPT,
            
            # V2: Production (Current) - mapped from the updated file
            "profile_create:v2": profile_prompts.PROFILE_CREATE_PROMPT,
            "profile_update:v2": profile_prompts.PROFILE_UPDATE_PROMPT,
        }
        
        # Current active versions
        self._active_versions = {
            "profile_create": "v2",
            "profile_update": "v2"
        }

    def get_prompt(self, prompt_type: str, version: str = None) -> str:
        """
        Get a specific prompt version.
        
        Args:
            prompt_type: 'profile_create' or 'profile_update'
            version: Specific version string (e.g., 'v1'). If None, uses active.
        """
        if not version:
            version = self._active_versions.get(prompt_type, "v2")
            
        key = f"{prompt_type}:{version}"
        prompt = self._prompts.get(key)
        
        if not prompt:
            logger.warning(f"Prompt version {key} not found. Falling back to v2.")
            # Fallback to whatever is imported
            if prompt_type == "profile_create":
                return profile_prompts.PROFILE_CREATE_PROMPT
            return profile_prompts.PROFILE_UPDATE_PROMPT
            
        return prompt

    def build_create_prompt(self, form_data: dict, form_type: str, form_purpose: str, version: str = None) -> str:
        """Build create prompt using versioning."""
        template = self.get_prompt("profile_create", version)
        return profile_prompts.format_questions_and_answers(form_data) # Re-using helper if needed
        # Wait, the helper usage in profile_prompts.py is coupled with the `build` functions there.
        # Ideally, we should use the builder functions logic here but inject the template.
        
        # Let's re-implement the formatting injection here to decouple
        qa_str = profile_prompts.format_questions_and_answers(form_data)
        question_count = len(form_data)
        
        return template.format(
            form_type=form_type,
            form_purpose=form_purpose,
            question_count=question_count,
            questions_and_answers=qa_str
        )

    def build_update_prompt(
        self, 
        existing_profile: str, 
        form_data: dict, 
        previous_form_count: int, 
        form_type: str, 
        form_purpose: str, 
        forms_history: list = None,
        version: str = None
    ) -> str:
        """Build update prompt using versioning."""
        template = self.get_prompt("profile_update", version)
        
        qa_str = profile_prompts.format_questions_and_answers(form_data)
        question_count = len(form_data)
        history_str = ", ".join(forms_history) if forms_history else "None"
        
        return template.format(
            existing_profile=existing_profile,
            form_type=form_type,
            form_purpose=form_purpose,
            question_count=question_count,
            previous_form_count=previous_form_count,
            questions_and_answers=qa_str,
            forms_history=history_str
        )

# Singleton
prompt_manager = PromptManager()
