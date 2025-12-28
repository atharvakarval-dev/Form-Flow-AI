"""
Gemini AI Service (LangChain Enhanced)

Provides integration with Google's Gemini AI for conversational form flow generation
using LangChain for structured reasoning and output parsing.

Uses:
    - langchain-google-genai for LLM integration
    - google-genai SDK (wrapped by langchain)
    - LangChain output parsers for reliable JSON extraction

Usage:
    from services.ai.gemini import GeminiService, SmartFormFillerChain
    
    service = GeminiService()
    result = service.generate_conversational_flow(
        extracted_fields={"name": "John"},
        form_schema=[{"fields": [...]}]
    )
    
    # Magic Fill
    filler = SmartFormFillerChain(service.llm)
    filled = await filler.fill(user_profile, form_schema)
"""

import os
import json
from typing import Dict, List, Any, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from utils.logging import get_logger, log_api_call
from utils.exceptions import AIServiceError

logger = get_logger(__name__)


# --- Pydantic Models for Structured Output ---

class FormFieldSuggestion(BaseModel):
    """Suggestion for a single form field."""
    field_name: str = Field(description="The exact name of the form field")
    value: str = Field(description="The suggested value for this field")
    confidence: float = Field(description="Confidence score between 0 and 1")
    source: str = Field(description="Where this value came from (profile, inferred, default)")


class MagicFillResult(BaseModel):
    """Result of Magic Fill operation."""
    filled_fields: List[FormFieldSuggestion] = Field(description="List of filled field suggestions")
    unfilled_fields: List[str] = Field(description="Field names that couldn't be filled")
    summary: str = Field(description="Brief summary of what was filled")


class ConversationalFlow(BaseModel):
    """Structure for conversational flow."""
    acknowledgment: str = Field(description="Message acknowledging captured data")
    questions: List[Dict[str, Any]] = Field(description="List of questions to ask")
    completion_message: str = Field(description="Message when all fields are collected")


# --- LangChain Enhanced Service ---

class GeminiService:
    """
    Service for interacting with Google Gemini AI via LangChain.
    
    Generates conversational flows for form completion based on
    extracted user data and remaining form fields.
    
    Attributes:
        llm: ChatGoogleGenerativeAI instance
        model: Model name (default: gemini-1.5-flash)
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-flash"):
        """
        Initialize Gemini service with LangChain.
        
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
        
        # Initialize LangChain LLM
        self.llm = ChatGoogleGenerativeAI(
            model=self.model,
            google_api_key=self.api_key,
            temperature=0.3,  # Lower temp for more consistent outputs
            convert_system_message_to_human=True
        )
        
        logger.info(f"GeminiService initialized with LangChain, model: {self.model}")

    def generate_conversational_flow(
        self,
        extracted_fields: Dict[str, str],
        form_schema: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate a conversational flow for collecting remaining form fields.
        
        Uses LangChain for structured output parsing.
        
        Args:
            extracted_fields: Dictionary of already captured {field_name: value}
            form_schema: Form schema from parser (list of forms with fields)
            
        Returns:
            dict: Result with conversational_flow, remaining_fields, and success flag
        """
        try:
            logger.info(f"Generating flow for {len(extracted_fields)} extracted fields")
            
            remaining_fields = self._get_remaining_fields(extracted_fields, form_schema)
            
            # Create prompt
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an AI assistant that creates conversational flows for form completion.
                Return ONLY valid JSON matching this structure:
                {
                    "acknowledgment": "Brief message",
                    "questions": [{"field_name": "...", "question": "...", "field_type": "...", "required": true}],
                    "completion_message": "Done message"
                }"""),
                ("human", """EXTRACTED DATA: {extracted}
                
REMAINING FIELDS: {remaining}

Create a friendly conversational flow to collect the remaining fields.""")
            ])
            
            # Create chain with JSON parser
            parser = JsonOutputParser(pydantic_object=ConversationalFlow)
            chain = prompt | self.llm | parser
            
            # Invoke
            flow_data = chain.invoke({
                "extracted": json.dumps(extracted_fields, indent=2),
                "remaining": json.dumps([{
                    'name': f.get('name'),
                    'type': f.get('type'),
                    'label': f.get('label'),
                    'required': f.get('required', False)
                } for f in remaining_fields], indent=2)
            })
            
            log_api_call("Gemini-LangChain", "generate_content", success=True)
            logger.info(f"Generated flow with {len(remaining_fields)} remaining fields")
            
            return {
                "success": True,
                "conversational_flow": flow_data,
                "remaining_fields": remaining_fields
            }
            
        except Exception as e:
            logger.error(f"Gemini/LangChain API error: {e}")
            log_api_call("Gemini-LangChain", "generate_content", success=False, error=str(e))
            
            return {
                "success": False,
                "error": str(e),
                "conversational_flow": self._get_fallback_flow()
            }

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
        """Get list of fields that still need to be collected."""
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


class SmartFormFillerChain:
    """
    LangChain-powered intelligent form filler.
    
    Analyzes user profile against form schema and fills as many fields
    as possible in a single LLM call ("Magic Fill").
    """
    
    def __init__(self, llm: ChatGoogleGenerativeAI):
        self.llm = llm
        self.parser = JsonOutputParser(pydantic_object=MagicFillResult)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an intelligent form-filling assistant.
Your task is to match user profile data to form fields intelligently.

RULES:
1. Match fields by semantic meaning, not just exact name match.
2. For "Years of Experience", infer from job history if available.
3. For "Skills", extract from resume/projects.
4. For addresses, infer city/state/country from full address.
5. For names, split "Full Name" into first/last if needed.
6. Set confidence based on how direct the match is (1.0 = exact, 0.5 = inferred).
7. Do NOT fill password, secrets, or payment fields.

Return ONLY valid JSON matching this schema:
{format_instructions}"""),
            ("human", """USER PROFILE:
{profile}

FORM SCHEMA (fields to fill):
{schema}

Fill as many fields as possible from the user's profile. Be intelligent about mapping data.""")
        ])
    
    async def fill(
        self, 
        user_profile: Dict[str, Any], 
        form_schema: List[Dict[str, Any]],
        min_confidence: float = 0.5
    ) -> Dict[str, Any]:
        """
        Perform "Magic Fill" - fill entire form from user profile.
        
        Args:
            user_profile: User's profile data (name, email, resume, etc.)
            form_schema: Form schema with all fields
            min_confidence: Minimum confidence to include a suggestion
            
        Returns:
            dict: {
                "filled": {field_name: value, ...},
                "unfilled": [field_names],
                "summary": "Filled X of Y fields"
            }
        """
        try:
            # Extract fillable fields from schema
            fillable_fields = []
            for form in form_schema:
                for field in form.get('fields', []):
                    if not field.get('hidden') and field.get('type') not in ['submit', 'button', 'hidden']:
                        fillable_fields.append({
                            'name': field.get('name'),
                            'type': field.get('type', 'text'),
                            'label': field.get('label', ''),
                            'required': field.get('required', False),
                            'options': field.get('options', [])[:5]  # Limit options for context
                        })
            
            # Create and run chain
            chain = self.prompt | self.llm | self.parser
            
            result = await chain.ainvoke({
                "profile": json.dumps(user_profile, indent=2, default=str),
                "schema": json.dumps(fillable_fields, indent=2),
                "format_instructions": self.parser.get_format_instructions()
            })
            
            # Filter by confidence
            filled = {}
            for suggestion in result.get('filled_fields', []):
                if suggestion.get('confidence', 0) >= min_confidence:
                    filled[suggestion['field_name']] = suggestion['value']
            
            unfilled = result.get('unfilled_fields', [])
            
            logger.info(f"Magic Fill: {len(filled)} filled, {len(unfilled)} unfilled")
            
            return {
                "success": True,
                "filled": filled,
                "unfilled": unfilled,
                "summary": f"Filled {len(filled)} of {len(fillable_fields)} fields automatically"
            }
            
        except Exception as e:
            logger.error(f"SmartFormFillerChain error: {e}")
            return {
                "success": False,
                "error": str(e),
                "filled": {},
                "unfilled": [],
                "summary": "Magic fill failed, please fill manually"
            }


# --- Singleton ---
_service_instance: Optional[GeminiService] = None


def get_gemini_service() -> GeminiService:
    """Get singleton GeminiService instance."""
    global _service_instance
    if _service_instance is None:
        try:
            _service_instance = GeminiService()
        except ValueError as e:
            logger.warning(f"Could not initialize GeminiService: {e}")
            return None
    return _service_instance