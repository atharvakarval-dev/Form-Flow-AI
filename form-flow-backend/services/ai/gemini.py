import os
from google import genai
from typing import Dict, List, Any
import json

class GeminiService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            raise ValueError("Google API key not found")

    def generate_conversational_flow(self, extracted_fields: Dict[str, str], form_schema: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze extracted fields and generate conversational flow for remaining fields
        """
        try:
            # Create prompt for Gemini
            prompt = self._create_flow_prompt(extracted_fields, form_schema)
            
            # Generate response from Gemini
            response = self.client.models.generate_content(
                model='gemini-1.5-pro',
                contents=prompt
            )
            
            # Parse the response
            flow_data = self._parse_gemini_response(response.text)
            
            return {
                "success": True,
                "conversational_flow": flow_data,
                "remaining_fields": self._get_remaining_fields(extracted_fields, form_schema)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "conversational_flow": None
            }

    def _create_flow_prompt(self, extracted_fields: Dict[str, str], form_schema: List[Dict[str, Any]]) -> str:
        """Create prompt for Gemini to generate conversational flow"""
        
        # Get all form fields
        all_fields = []
        for form in form_schema:
            all_fields.extend(form.get('fields', []))
        
        # Identify remaining fields
        remaining_fields = [
            field for field in all_fields 
            if field.get('name') not in extracted_fields and not field.get('hidden', False)
        ]
        
        prompt = f"""
You are an AI assistant that creates conversational flows for form completion. 

EXTRACTED DATA (already captured):
{json.dumps(extracted_fields, indent=2)}

REMAINING FORM FIELDS TO COLLECT:
{json.dumps([{
    'name': field.get('name'),
    'type': field.get('type'),
    'label': field.get('label'),
    'required': field.get('required', False),
    'options': field.get('options', []) if field.get('type') == 'select' else None
} for field in remaining_fields], indent=2)}

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
        """Parse Gemini response and extract JSON"""
        try:
            # Clean the response text
            cleaned_text = response_text.strip()
            
            # Find JSON in the response
            start_idx = cleaned_text.find('{')
            end_idx = cleaned_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = cleaned_text[start_idx:end_idx]
                return json.loads(json_str)
            else:
                # Fallback: create basic structure
                return {
                    "acknowledgment": "Thank you for the information provided.",
                    "questions": [],
                    "completion_message": "All required information has been collected."
                }
                
        except json.JSONDecodeError:
            # Fallback response
            return {
                "acknowledgment": "Thank you for the information provided.",
                "questions": [],
                "completion_message": "All required information has been collected."
            }

    def _get_remaining_fields(self, extracted_fields: Dict[str, str], form_schema: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get list of fields that still need to be collected"""
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