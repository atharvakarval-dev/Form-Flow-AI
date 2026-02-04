"""
Form Intent Inferrer

This module is responsible for determining the purpose of a form.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from services.ai.gemini import get_gemini_service
from utils.logging import get_logger

logger = get_logger(__name__)

class FormIntent(BaseModel):
    """Data model for the inferred form intent."""
    intent: str = Field(description="The high-level purpose of the form (e.g., 'Business Lead', 'Support Ticket', 'Job Application', 'Clinical Intake').")
    persona: str = Field(description="The persona to adopt for suggestions (e.g., 'Customer', 'Patient', 'Applicant').")
    form_type: str = Field(description="The type of form, e.g., 'public_facing', 'internal', 'diagnostic_report'.")

class FormIntentInferrer:
    """
    Infers the intent of a form based on its URL and field labels.
    """
    def __init__(self):
        self._cache = {}

    async def infer_intent(self, form_url: str, all_field_labels: List[str]) -> Optional[FormIntent]:
        """
        Infers the intent of a form using an LLM.
        """
        logger.info(f"--- Form Intent Inference Request ---")
        logger.info(f"Form URL: {form_url}")
        logger.info(f"All Field Labels: {', '.join(all_field_labels)}")

        # Caching mechanism to avoid re-processing the same form
        cache_key = f"{form_url}-{'-'.join(sorted(all_field_labels))}"
        if cache_key in self._cache:
            logger.info(f"Cache hit for intent: {self._cache[cache_key].intent}")
            return self._cache[cache_key]

        gemini = get_gemini_service()
        if not gemini or not gemini.llm:
            logger.error("Gemini Service unavailable for intent inference.")
            return None

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a Form Intent Classifier. Your task is to analyze the labels of a form's fields and determine its primary purpose.

            You must classify the form into one of the following categories and adopt the corresponding persona:
            - **Business Lead**: A form for generating sales leads. Persona: "Customer". Form Type: "public_facing".
            - **Support Ticket**: A form for customer support. Persona: "Customer". Form Type: "public_facing".
            - **Job Application**: A form for applying to a job. Persona: "Applicant". Form Type: "public_facing".
            - **Contact Us**: A generic contact form. Persona: "Customer". Form Type: "public_facing".
            - **Clinical Intake**: A form for patient information. Persona: "Patient". Form Type: "clinical".
            - **Diagnostic Report**: A form for clinical diagnosis. Persona: "Clinician". Form Type: "diagnostic_report".
            - **Internal Tool**: A form for internal business processes. Persona: "Employee". Form Type: "internal".

            Analyze the provided URL and field labels to determine the most likely intent.
            URL: {form_url}
            Field Labels: {field_labels}

            Output your classification in the specified JSON format.
            """),
        ])

        parser = JsonOutputParser(pydantic_object=FormIntent)
        chain = prompt | gemini.llm | parser

        gemini = get_gemini_service()

        try:
        # Added form_url to the payload
            llm_payload = {
                "form_url": form_url,
                "field_labels": ", ".join(all_field_labels)
            }
        
            logger.info(f"Sending to LLM for intent inference: {llm_payload}")
            result = await chain.ainvoke(llm_payload)
            
            # GUARDRAIL: Check if result is None before proceeding
            if result is None:
                logger.warning("LLM returned None. Using fallback intent.")
                return FormIntent(intent="Contact Us", persona="Customer", form_type="public_facing")

            # Map result to Pydantic model
            intent = FormIntent(**result)
            self._cache[cache_key] = intent
            return intent

        except Exception as e:
            logger.error(f"Failed to infer form intent: {e}", exc_info=True)
            # Fallback to prevent downstream crashes
            return FormIntent(intent="Contact Us", persona="Customer", form_type="public_facing")

_intent_inferrer_instance: Optional[FormIntentInferrer] = None

def get_form_intent_inferrer() -> FormIntentInferrer:
    """Get a singleton instance of the FormIntentInferrer."""
    global _intent_inferrer_instance
    if _intent_inferrer_instance is None:
        _intent_inferrer_instance = FormIntentInferrer()
    return _intent_inferrer_instance
