"""
Gemini AI Service

Provides integration with Google's Gemini AI for conversational form flow generation.
Uses the Gemini API to analyze form schemas and create natural conversation flows.

Usage:
    from services.ai.gemini import GeminiService
    
    service = GeminiService()
    result = service.generate_conversational_flow(
        extracted_fields={"name": "John"},
        form_schema=[{"fields": [...]}]
    )
"""

import os
import json
from typing import Dict, List, Any, Optional

from google import genai

from utils.logging import get_logger, log_api_call
from utils.exceptions import AIServiceError

logger = get_logger(__name__)


class GeminiService:
    """
    Service for interacting with Google Gemini AI.
    
    Generates conversational flows for form completion based on
    extracted user data and remaining form fields.
    
    Attributes:
        api_key: Google API key for Gemini
        client: Gemini client instance
        model: Model name (default: gemini-1.5-pro)
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-pro"):
        """
        Initialize Gemini service.
        
        Args:
            api_key: Google API key. Falls back to GOOGLE_API_KEY env var.
            model: Gemini model to use.
            
        Raises:
            ValueError: If no API key is provided or found.
        """
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        self.model = model
        
        if not self.api_key:
            raise ValueError("Google API key not found. Set GOOGLE_API_KEY env variable.")
        
        self.client = genai.Client(api_key=self.api_key)
        logger.info(f"GeminiService initialized with model: {self.model}")

    def generate_conversational_flow(
        self,
        extracted_fields: Dict[str, str],
        form_schema: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate a conversational flow for collecting remaining form fields.
        
        Analyzes what data has been extracted and creates natural language
        questions for the remaining fields.
        
        Args:
            extracted_fields: Dictionary of already captured {field_name: value}
            form_schema: Form schema from parser (list of forms with fields)
            
        Returns:
            dict: Result with conversational_flow, remaining_fields, and success flag
            
        Example:
            result = service.generate_conversational_flow(
                extracted_fields={"name": "John", "email": "john@example.com"},
                form_schema=[{"fields": [{"name": "phone", "type": "tel"}]}]
            )
            # Returns:
            # {
            #     "success": True,
            #     "conversational_flow": {...},
            #     "remaining_fields": [{"name": "phone", ...}]
            # }
        """
        try:
            logger.info(f"Generating flow for {len(extracted_fields)} extracted fields")
            
            # Create prompt for Gemini
            prompt = self._create_flow_prompt(extracted_fields, form_schema)
            
            # Generate response
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            
            log_api_call("Gemini", "generate_content", success=True)
            
            # Parse response
            flow_data = self._parse_gemini_response(response.text)
            remaining_fields = self._get_remaining_fields(extracted_fields, form_schema)
            
            logger.info(f"Generated flow with {len(remaining_fields)} remaining fields")
            
            return {
                "success": True,
                "conversational_flow": flow_data,
                "remaining_fields": remaining_fields
            }
            
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            log_api_call("Gemini", "generate_content", success=False, error=str(e))
            
            return {
                "success": False,
                "error": str(e),
                "conversational_flow": None
            }

    def _create_flow_prompt(
        self,
        extracted_fields: Dict[str, str],
        form_schema: List[Dict[str, Any]]
    ) -> str:
        """
        Create prompt for Gemini to generate conversational flow.
        
        Args:
            extracted_fields: Already captured field values
            form_schema: Form schema with all fields
            
        Returns:
            str: Formatted prompt for Gemini
        """
        # Get all form fields
        all_fields = []
        for form in form_schema:
            all_fields.extend(form.get('fields', []))
        
        # Identify remaining fields
        remaining_fields = [
            field for field in all_fields
            if field.get('name') not in extracted_fields and not field.get('hidden', False)
        ]
        
        # Format remaining fields for prompt
        remaining_summary = [
            {
                'name': field.get('name'),
                'type': field.get('type'),
                'label': field.get('label'),
                'required': field.get('required', False),
                'options': field.get('options', []) if field.get('type') == 'select' else None
            }
            for field in remaining_fields
        ]
        
        prompt = f"""
You are an AI assistant that creates conversational flows for form completion. 

EXTRACTED DATA (already captured):
{json.dumps(extracted_fields, indent=2)}

REMAINING FORM FIELDS TO COLLECT:
{json.dumps(remaining_summary, indent=2)}

Create a conversational flow that:
1. Acknowledges the data already captured
2. Asks for remaining required fields in a natural, conversational way
3. Groups related fields together
4. Provides clear instructions for each field type
5. Uses friendly, professional tone

Return ONLY a JSON object with this structure:
{{
  "acknowledgment": "Brief message acknowledging captured data",
  "questions": [
    {{
      "field_name": "field_name",
      "question": "Natural question to ask",
      "field_type": "text|email|select|etc",
      "required": true/false,
      "options": ["option1", "option2"] // only for select fields
    }}
  ],
  "completion_message": "Message when all fields are collected"
}}
"""
        return prompt

    def _parse_gemini_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse Gemini response and extract JSON.
        
        Args:
            response_text: Raw response text from Gemini
            
        Returns:
            dict: Parsed conversational flow data
        """
        try:
            cleaned_text = response_text.strip()
            
            # Find JSON in response
            start_idx = cleaned_text.find('{')
            end_idx = cleaned_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = cleaned_text[start_idx:end_idx]
                return json.loads(json_str)
            else:
                logger.warning("No JSON found in Gemini response, using fallback")
                return self._get_fallback_flow()
                
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Gemini response: {e}")
            return self._get_fallback_flow()

    def _get_fallback_flow(self) -> Dict[str, Any]:
        """Get a fallback conversational flow when parsing fails."""
        return {
            "acknowledgment": "Thank you for the information provided.",
            "questions": [],
            "completion_message": "All required information has been collected."
        }

    def _get_remaining_fields(
        self,
        extracted_fields: Dict[str, str],
        form_schema: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Get list of fields that still need to be collected.
        
        Args:
            extracted_fields: Already captured fields
            form_schema: Complete form schema
            
        Returns:
            list: Remaining fields with metadata
        """
        remaining = []
        
        for form in form_schema:
            for field in form.get('fields', []):
                field_name = field.get('name')
                
                if (field_name not in extracted_fields and
                    not field.get('hidden', False) and
                    field.get('type') != 'submit'):
                    
                    remaining.append({
                        'name': field_name,
                        'type': field.get('type'),
                        'label': field.get('label'),
                        'required': field.get('required', False)
                    })
        
        return remaining