"""
OpenRouter LLM Service for Form Flow AI

Provides inference using OpenRouter API (specifically Google Gemma 3 27B)
for form field extraction and conversational flow generation.

Usage:
    from services.ai.openrouter_llm import OpenRouterLLMService
    
    service = OpenRouterLLMService(api_key="sk-...")
    result = service.extract_all_fields("My name is John", fields)
"""

import json
from typing import Dict, List, Any, Optional
from openai import OpenAI
import httpx

from utils.logging import get_logger
from config.settings import settings

logger = get_logger(__name__)


class OpenRouterLLMService:
    """
    OpenRouter-based LLM service using Google Gemma 3 27B.
    
    Serves as the PRIMARY engine for extraction due to high speed and low latency.
    """
    
    def __init__(self, api_key: str, model: str = "google/gemma-3-27b-it"):
        self.api_key = api_key
        self.model = model
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            timeout=10.0  # OpenRouter is usually fast
        )
        logger.info(f"✅ OpenRouter LLM Service initialized with model: {model}")
        
    def extract_field_value(self, user_input: str, field_name: str) -> Dict[str, Any]:
        """
        Extract a single field value using OpenRouter.
        Re-uses the batch extraction logic for consistency.
        """
        try:
            # Re-use the robust batch extraction for a single field
            batch_result = self.extract_all_fields(user_input, [field_name])
            
            extracted = batch_result.get('extracted', {})
            confidence = batch_result.get('confidence', {})
            
            # Check if our field was found
            value = None
            conf = 0.0
            
            # Direct match
            if field_name in extracted:
                value = extracted[field_name]
                conf = confidence.get(field_name, 0.0)
            else:
                # Fuzzy match search in results
                for key, val in extracted.items():
                    if key.lower() in field_name.lower() or field_name.lower() in key.lower():
                        value = val
                        conf = confidence.get(key, 0.0)
                        break
            
            if value:
                return {
                    "value": value,
                    "confidence": conf,
                    "source": "openrouter_llm"
                }
            
            return {
                "value": None,
                "confidence": 0.0,
                "source": "openrouter_llm"
            }
            
        except Exception as e:
            logger.error(f"Error in extract_field_value (OpenRouter): {e}")
            return {
                "value": None,
                "confidence": 0.0,
                "source": "openrouter_llm",
                "error": str(e)
            }

    def extract_all_fields(self, user_input: str, fields: List[Any]) -> Dict[str, Any]:
        """
        Extract ALL fields from a single user input using OpenRouter.
        
        Args:
            user_input: The user's full input text
            fields: List of field definitions (Dicts) or field names (strings)
            
        Returns:
            Dict with extracted values, confidences, and source
        """
        try:
            # 1. Build the Schema Context
            schema_lines = []
            
            for f in fields:
                # Handle both dict objects and simple strings
                if isinstance(f, dict):
                    name = f.get('name', 'Unknown')
                    label = f.get('label', name)
                    f_type = f.get('type', 'text')
                    options = f.get('options', [])
                    
                    desc = f"- {label} (Type: {f_type})"
                    if options:
                        # Extract option labels/values
                        opt_strs = [str(opt.get('label', opt.get('value', ''))) for opt in options]
                        desc += f" [Options: {', '.join(opt_strs)}]"
                    schema_lines.append(desc)
                else:
                    schema_lines.append(f"- {str(f)}")

            schema_text = "\n".join(schema_lines)
            
            # 2. Construct the Smart Prompt
            system_prompt = f"""You are a smart form-filling assistant. Map the user's speech to the following form fields.

FORM FIELDS:
{schema_text}

INSTRUCTIONS:
1. Extract values for any fields mentioned in the speech.
2. For "Options" fields, map the speech to the closest valid option.
3. Infer values from context if explicit labels are missing.
4. If a field is NOT mentioned, do not include it.
5. Output strict JSON format: {{"field_label": "extracted_value"}}
6. Do NOT generate any markdown or explanation."""

            user_message = f"""USER SPEECH: "{user_input}"\n\nExtract fields in JSON:"""

            # 3. Running Inference
            completion = self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "https://formflow.ai", # Required by OpenRouter
                    "X-Title": "Form Flow AI", # Optional
                },
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,
                response_format={ "type": "json_object" }
            )
            
            response_content = completion.choices[0].message.content
            logger.info(f"OpenRouter Extraction Output: {response_content}")
            
            # 4. Parse the Output
            try:
                extracted_raw = json.loads(response_content)
            except json.JSONDecodeError:
                # Fallback manual parsing if JSON is broken
                logger.warning("OpenRouter returned invalid JSON, attempting manual parse")
                extracted_raw = {}
                # TODO: Add manual parsing if needed, but JSON mode usually works
            
            extracted_values = {}
            confidences = {}
            
            # Create a map of Label -> Field Name
            label_to_field = {}
            for f in fields:
                if isinstance(f, dict):
                    # Map both label and name to the official name
                    label_to_field[f.get('label', '').lower().strip()] = f.get('name')
                    label_to_field[f.get('name', '').lower().strip()] = f.get('name')
                else:
                    label_to_field[str(f).lower().strip()] = str(f)
            
            # Normalize extracted keys to field names
            for key, value in extracted_raw.items():
                key_norm = key.lower().strip()
                if key_norm in label_to_field:
                    field_name = label_to_field[key_norm]
                    extracted_values[field_name] = value
                    confidences[field_name] = 0.95  # High confidence for OpenRouter
                else:
                    # Fuzzy match?
                    # For now just log missed key
                    logger.debug(f"OpenRouter extracted unknown key: {key}")

            return {
                "extracted": extracted_values,
                "confidence": confidences,
                "source": "openrouter_llm"
            }
            
        except Exception as e:
            logger.error(f"OpenRouter extraction failed: {e}")
            return {
                "extracted": {},
                "confidence": {},
                "source": "openrouter_error",
                "error": str(e)
            }

# Singleton instance
_openrouter_instance: Optional[OpenRouterLLMService] = None

def get_openrouter_service(api_key: str = None) -> Optional[OpenRouterLLMService]:
    global _openrouter_instance
    if not api_key:
        api_key = settings.OPENROUTER_API_KEY
    
    if not api_key:
        return None
        
    if _openrouter_instance is None:
        try:
            _openrouter_instance = OpenRouterLLMService(api_key=api_key)
        except Exception as e:
            logger.warning(f"Could not initialize OpenRouterLLMService: {e}")
            return None
    return _openrouter_instance
