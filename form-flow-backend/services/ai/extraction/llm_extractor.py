"""
LLM Extractor

LLM-powered extraction using Google Gemini.
Handles prompt building, API calls with retry, and response parsing.
"""

import asyncio
import json
from typing import Dict, List, Any, Optional, Tuple

from utils.logging import get_logger
from services.ai.prompts import EXTRACTION_SYSTEM_PROMPT, build_extraction_context
from services.ai.normalizers import (
    normalize_email_smart,
    normalize_phone_smart,
    normalize_name_smart,
    normalize_text_smart,
)

logger = get_logger(__name__)

# Retry configuration
LLM_MAX_RETRIES = 3
LLM_RETRY_BASE_DELAY = 1.0
LLM_RETRY_MAX_DELAY = 10.0


class LLMExtractor:
    """
    LLM-powered extraction using Google Gemini.
    
    Handles:
    - Prompt construction
    - API calls with exponential backoff retry
    - Response parsing and validation
    - Post-extraction normalization
    """
    
    def __init__(self, llm_client, model_name: str = "gemini-2.5-flash-lite"):
        """
        Initialize LLM extractor.
        
        Args:
            llm_client: LangChain LLM client (ChatGoogleGenerativeAI)
            model_name: Model name for logging
        """
        self.llm = llm_client
        self.model_name = model_name
    
    async def extract(
        self,
        user_input: str,
        current_batch: List[Dict[str, Any]],
        remaining_fields: List[Dict[str, Any]],
        conversation_history: List[Dict[str, str]],
        already_extracted: Dict[str, str],
        is_voice: bool = False
    ) -> Tuple[Dict[str, str], Dict[str, float], str]:
        """
        Extract field values using LLM.
        
        Args:
            user_input: The user's input text
            current_batch: Fields being asked in this turn
            remaining_fields: All remaining unfilled fields
            conversation_history: Recent conversation turns
            already_extracted: Previously extracted values
            is_voice: Whether input is from voice
            
        Returns:
            Tuple of (extracted_values, confidence_scores, message)
        """
        try:
            # Build context prompt
            context = build_extraction_context(
                current_batch=current_batch,
                remaining_fields=remaining_fields,
                user_input=user_input,
                conversation_history=conversation_history,
                already_extracted=already_extracted,
                is_voice=is_voice
            )
            
            # Import LangChain messages
            from langchain_core.messages import HumanMessage, SystemMessage
            
            messages = [
                SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
                HumanMessage(content=context)
            ]
            
            # Call LLM with retry
            response = await self._invoke_with_retry(messages)
            
            # Parse response
            extracted, confidence, message = self._parse_response(
                response.content, 
                remaining_fields
            )
            
            # Normalize extracted values
            extracted = self._normalize_values(extracted, remaining_fields)
            
            return extracted, confidence, message
            
        except Exception as e:
            logger.error(f"LLM extraction error: {e}")
            raise
    
    async def _invoke_with_retry(self, messages: List[Any]) -> Any:
        """
        Invoke LLM with exponential backoff retry.
        
        Args:
            messages: List of LangChain messages
            
        Returns:
            LLM response
            
        Raises:
            Exception: If all retries fail
        """
        last_error = None
        delay = LLM_RETRY_BASE_DELAY
        
        for attempt in range(LLM_MAX_RETRIES):
            try:
                if hasattr(self.llm, 'ainvoke'):
                    response = await self.llm.ainvoke(messages)
                else:
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None, 
                        lambda: self.llm.invoke(messages)
                    )
                return response
                
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # Check if error is retryable
                retryable = any(keyword in error_str for keyword in [
                    'rate limit', 'quota', 'timeout', 'connection',
                    'temporary', '429', '503', '502', 'overloaded'
                ])
                
                if not retryable or attempt == LLM_MAX_RETRIES - 1:
                    raise
                
                logger.warning(
                    f"LLM call failed (attempt {attempt + 1}/{LLM_MAX_RETRIES}), "
                    f"retrying in {delay:.1f}s: {e}"
                )
                
                await asyncio.sleep(delay)
                delay = min(delay * 2, LLM_RETRY_MAX_DELAY)
        
        raise last_error
    
    def _parse_response(
        self, 
        response_text: str,
        remaining_fields: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, str], Dict[str, float], str]:
        """
        Parse LLM response JSON.
        
        Args:
            response_text: Raw LLM response
            remaining_fields: Fields for validation
            
        Returns:
            Tuple of (extracted_values, confidence_scores, message)
        """
        try:
            # Clean up response (remove markdown code blocks)
            clean_text = response_text.replace('```json', '').replace('```', '').strip()
            data = json.loads(clean_text)
            
            extracted = data.get('extracted', {})
            confidence = {}
            
            # Convert confidence scores to floats
            for field, score in data.get('confidence', {}).items():
                confidence[field] = float(score)
            
            message = data.get('message', "I understood that.")
            
            return extracted, confidence, message
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response: {response_text[:100]}...")
            raise
    
    def _normalize_values(
        self, 
        extracted: Dict[str, str],
        remaining_fields: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        Normalize extracted values based on field type.
        
        Args:
            extracted: Raw extracted values
            remaining_fields: Field definitions
            
        Returns:
            Normalized values
        """
        normalized = {}
        
        for field_name, value in extracted.items():
            # Find field info
            field_info = next(
                (f for f in remaining_fields if f.get('name') == field_name), 
                {}
            )
            field_type = field_info.get('type', 'text')
            field_label = field_info.get('label', field_name).lower()
            
            # Apply appropriate normalizer
            if field_type == 'email' or 'email' in field_label:
                value = normalize_email_smart(value)
            elif field_type == 'tel' or any(k in field_label for k in ['phone', 'mobile', 'tel']):
                value = normalize_phone_smart(value)
            elif 'name' in field_label:
                value = normalize_name_smart(value)
            else:
                value = normalize_text_smart(value)
            
            normalized[field_name] = value
        
        return normalized
