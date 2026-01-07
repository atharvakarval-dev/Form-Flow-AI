"""
Profile Validation Engine

Handles data quality checks, input validation, and LLM output verification.
Ensures only high-quality data reaches the LLM and the database.
"""

import json
from typing import Dict, Any, Tuple, Optional
from .config import profile_config

class ProfileValidator:
    """
    Validator for the profile generation pipeline.
    """
    
    @staticmethod
    def validate_form_quality(form_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate if the form data is sufficient for profiling.
        
        Args:
            form_data: Dictionary of question-answer pairs
            
        Returns:
            (is_valid, reason)
        """
        if not form_data:
            return False, "Empty form data"
            
        # Count valid answers (non-empty, meets min length)
        valid_answers = 0
        for value in form_data.values():
            if value and isinstance(value, str) and len(value.strip()) >= profile_config.MIN_ANSWER_LENGTH:
                valid_answers += 1
                
        if valid_answers < profile_config.MIN_QUESTIONS_FOR_PROFILE:
            return False, f"Insufficient valid answers ({valid_answers}/{profile_config.MIN_QUESTIONS_FOR_PROFILE})"
            
        return True, "Form data valid"

    @staticmethod
    def validate_llm_output(output_text: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Validate LLM output structure and content.
        
        Args:
            output_text: Raw string response from LLM
            
        Returns:
            (is_valid, parsed_json, error_message)
        """
        if not output_text:
            return False, None, "Empty LLM output"
            
        # 1. JSON parsing check
        try:
            # Clean potential markdown code blocks
            clean_text = output_text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            
            data = json.loads(clean_text)
        except json.JSONDecodeError as e:
            return False, None, f"Invalid JSON format: {str(e)}"
            
        # 2. Schema validation (Essential keys)
        required_keys = ["executive_summary", "psychological_profile", "behavioral_patterns"]
        missing_keys = [key for key in required_keys if key not in data]
        
        if missing_keys:
            # DEBUG
            print(f"DEBUG VALIDATOR: Found keys: {list(data.keys())}")
            return False, data, f"Missing required sections: {', '.join(missing_keys)}"
            
        return True, data, "Output valid"

    @staticmethod
    def calculate_confidence(
        old_profile: Optional[Dict[str, Any]], 
        new_profile: Dict[str, Any],
        form_quality_score: float
    ) -> float:
        """
        Calculate confidence score for the new profile.
        
        Args:
            old_profile: Previous profile data (if any)
            new_profile: Newly generated profile data
            form_quality_score: 0.0-1.0 score based on input richness
            
        Returns:
            0.0-1.0 confidence score
        """
        # Base confidence from input quality
        base_score = form_quality_score * 0.6
        
        # Stability score (if previous profile exists)
        stability_score = 0.0
        if old_profile:
            # Simple check: does executive summary length deviate wildly?
            # A more advanced check would use semantic similarity
            len_old = len(str(old_profile.get("executive_summary", "")))
            len_new = len(str(new_profile.get("executive_summary", "")))
            
            if len_new > 0:
                ratio = min(len_old, len_new) / max(len_old, len_new)
                stability_score = ratio * 0.4
        else:
            # For new profiles, boost base score weight
            base_score = form_quality_score * 0.9
            stability_score = 0.1 # Small bonus for fresh start
            
        return min(base_score + stability_score, 1.0)
