"""
Plugin Extractor Module

Multi-field extraction with confidence scoring for plugin data collection.
Features:
- Reuses LLMExtractor for LLM-powered extraction
- Plugin field format adaptation
- Confidence thresholds
- Validation integration

Zero redundancy:
- Extends existing LLMExtractor
- Reuses normalization utilities
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from services.plugin.voice.session_manager import PluginSessionData
from services.plugin.question.optimizer import get_plugin_optimizer
from utils.logging import get_logger

logger = get_logger(__name__)


# Confidence thresholds
CONFIDENCE_HIGH = 0.9      # Auto-accept
CONFIDENCE_MEDIUM = 0.7    # Accept with implicit confirmation
CONFIDENCE_LOW = 0.5       # Needs explicit confirmation


@dataclass
class ExtractionResult:
    """Result of a single extraction attempt."""
    field_name: str
    value: Any
    confidence: float
    normalized_value: Any = None
    needs_confirmation: bool = False
    validation_errors: List[str] = None
    
    def __post_init__(self):
        if self.validation_errors is None:
            self.validation_errors = []
        self.needs_confirmation = self.confidence < CONFIDENCE_HIGH


@dataclass
class BatchExtractionResult:
    """Result of extracting multiple fields from user input."""
    extracted: Dict[str, ExtractionResult]
    unmatched_fields: List[str]
    message_to_user: Optional[str]
    all_confirmed: bool
    tokens_used: int = 0


class PluginExtractor:
    """
    Multi-field extraction for plugin data collection.
    
    Uses LLM to extract field values from user text input.
    Handles:
    - Multi-field extraction per turn
    - Confidence scoring
    - Type normalization
    - Validation integration
    
    Usage:
        extractor = PluginExtractor(llm_client)
        result = await extractor.extract(
            user_input="My name is John, email is john@example.com",
            current_fields=["name", "email"],
            session=session
        )
    """
    
    # Prompt template for plugin extraction
    EXTRACTION_PROMPT = """You are extracting data from user input for a form.

Current fields to extract:
{field_descriptions}

User input: "{user_input}"

{conversation_context}

Extract values for as many fields as possible from the user input.
Return a JSON object with:
- "extracted": Object mapping field names to extracted values
- "confidence": Object mapping field names to confidence scores (0.0-1.0)
- "message": Optional clarifying question if values are unclear

Rules:
1. Only extract fields listed above
2. Use null for fields with no value in the input
3. Confidence 1.0 = definitely correct, 0.5 = uncertain
4. For ambiguous input, ask for clarification in message
5. Apply type conversions (dates, numbers) as appropriate

Return ONLY valid JSON, no explanation."""

    def __init__(self, llm_client=None, model_name: str = "gemini-2.5-flash-lite"):
        """
        Initialize extractor.
        
        Args:
            llm_client: LangChain LLM client (lazy loaded if None)
            model_name: Model name for cost tracking
        """
        self._llm_client = llm_client
        self._model_name = model_name
        self._optimizer = get_plugin_optimizer()
    
    async def _get_llm_client(self):
        """Lazy load LLM client."""
        if self._llm_client is None:
            from langchain_google_genai import ChatGoogleGenerativeAI
            from config.settings import settings
            
            self._llm_client = ChatGoogleGenerativeAI(
                model=self._model_name,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=0.1,  # Very low for extraction accuracy
            )
        return self._llm_client
    
    def _build_prompt(
        self,
        user_input: str,
        fields: List[Dict[str, Any]],
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """Build extraction prompt."""
        field_descriptions = []
        for field in fields:
            name = field.get("column_name", "")
            field_type = field.get("column_type", "string")
            question = field.get("question_text", name)
            required = "required" if field.get("is_required") else "optional"
            
            field_descriptions.append(f"- {name} ({field_type}, {required}): {question}")
        
        # Add conversation context if available
        context = ""
        if conversation_history:
            recent = conversation_history[-3:]  # Last 3 turns
            context_lines = [
                f"Assistant: {h['question']}\nUser: {h['answer']}"
                for h in recent if 'question' in h and 'answer' in h
            ]
            if context_lines:
                context = f"Previous conversation:\n" + "\n".join(context_lines)
        
        return self.EXTRACTION_PROMPT.format(
            field_descriptions="\n".join(field_descriptions),
            user_input=user_input,
            conversation_context=context
        )
    
    async def extract(
        self,
        user_input: str,
        current_fields: List[Dict[str, Any]],
        session: PluginSessionData,
        plugin_id: int
    ) -> BatchExtractionResult:
        """
        Extract field values from user input.
        
        Args:
            user_input: Text from user (voice transcribed or typed)
            current_fields: Plugin fields being asked in this turn
            session: Current session for context
            plugin_id: Plugin ID for cost tracking
            
        Returns:
            BatchExtractionResult with extracted values and confidence
        """
        import json
        from utils.circuit_breaker import resilient_call
        from services.plugin.question.cost_tracker import get_cost_tracker
        
        prompt = self._build_prompt(
            user_input,
            current_fields,
            session.conversation_history
        )
        
        # Call LLM
        llm = await self._get_llm_client()
        from langchain_core.messages import HumanMessage
        
        response = await resilient_call(
            llm.ainvoke,
            [HumanMessage(content=prompt)],
            max_retries=3,
            circuit_name=f"plugin_extract_{plugin_id}"
        )
        
        # Track usage
        response_text = response.content.strip()
        tokens = (len(prompt) + len(response_text)) // 4  # Rough estimate
        
        cost_tracker = get_cost_tracker()
        await cost_tracker.track_usage(
            plugin_id=plugin_id,
            operation="extraction",
            tokens=tokens,
            estimated_cost=tokens / 1_000_000 * 0.15,  # Rough cost
            model=self._model_name
        )
        
        # Parse response
        return self._parse_extraction_response(
            response_text,
            current_fields,
            tokens
        )
    
    def _parse_extraction_response(
        self,
        response_text: str,
        fields: List[Dict[str, Any]],
        tokens: int
    ) -> BatchExtractionResult:
        """Parse LLM response into extraction results."""
        import json
        
        # Clean response
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse extraction response: {e}")
            return BatchExtractionResult(
                extracted={},
                unmatched_fields=[f.get("column_name", "") for f in fields],
                message_to_user="I couldn't understand that. Could you please rephrase?",
                all_confirmed=False,
                tokens_used=tokens
            )
        
        extracted = {}
        unmatched = []
        field_map = {f.get("column_name", ""): f for f in fields}
        
        extracted_values = data.get("extracted", {})
        confidences = data.get("confidence", {})
        message = data.get("message")
        
        for field_name, field_def in field_map.items():
            value = extracted_values.get(field_name)
            confidence = confidences.get(field_name, 0.5)
            
            if value is not None:
                # Normalize value based on type
                normalized = self._normalize_value(value, field_def)
                
                extracted[field_name] = ExtractionResult(
                    field_name=field_name,
                    value=value,
                    confidence=confidence,
                    normalized_value=normalized,
                    needs_confirmation=confidence < CONFIDENCE_HIGH
                )
            else:
                unmatched.append(field_name)
        
        all_confirmed = all(
            not r.needs_confirmation for r in extracted.values()
        )
        
        return BatchExtractionResult(
            extracted=extracted,
            unmatched_fields=unmatched,
            message_to_user=message,
            all_confirmed=all_confirmed,
            tokens_used=tokens
        )
    
    def _normalize_value(self, value: Any, field: Dict[str, Any]) -> Any:
        """Normalize value based on field type."""
        column_type = field.get("column_type", "string").lower()
        
        if value is None:
            return None
        
        try:
            if column_type in ("integer", "int"):
                # Extract numbers from string
                if isinstance(value, str):
                    import re
                    numbers = re.findall(r'-?\d+', value.replace(',', ''))
                    return int(numbers[0]) if numbers else None
                return int(value)
            
            elif column_type == "float":
                if isinstance(value, str):
                    import re
                    numbers = re.findall(r'-?\d+\.?\d*', value.replace(',', ''))
                    return float(numbers[0]) if numbers else None
                return float(value)
            
            elif column_type == "boolean":
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.lower() in ("yes", "true", "1", "y")
                return bool(value)
            
            elif column_type == "date":
                from dateutil import parser
                return parser.parse(str(value)).date().isoformat()
            
            elif column_type == "datetime":
                from dateutil import parser
                return parser.parse(str(value)).isoformat()
            
            elif column_type == "email":
                # Basic email normalization
                return str(value).strip().lower()
            
            elif column_type == "phone":
                # Remove non-digits except +
                import re
                return re.sub(r'[^\d+]', '', str(value))
            
            else:
                # String types
                return str(value).strip()
        
        except Exception as e:
            logger.debug(f"Normalization failed for {field.get('column_name')}: {e}")
            return str(value)
    
    async def apply_to_session(
        self,
        result: BatchExtractionResult,
        session: PluginSessionData
    ) -> PluginSessionData:
        """
        Apply extraction results to session state.
        
        Updates session with extracted values and moves fields
        from pending to completed.
        """
        for field_name, extraction in result.extracted.items():
            # Use normalized value if available
            value = extraction.normalized_value or extraction.value
            
            session.extracted_values[field_name] = value
            session.confidence_scores[field_name] = extraction.confidence
            
            # Move from pending to completed
            if field_name in session.pending_fields:
                session.pending_fields.remove(field_name)
            if field_name not in session.completed_fields:
                session.completed_fields.append(field_name)
        
        session.turn_count += 1
        return session


# Singleton instance
_plugin_extractor: Optional[PluginExtractor] = None


def get_plugin_extractor(
    llm_client=None,
    model_name: str = "gemini-2.5-flash-lite"
) -> PluginExtractor:
    """Get singleton plugin extractor."""
    global _plugin_extractor
    if _plugin_extractor is None:
        _plugin_extractor = PluginExtractor(llm_client, model_name)
    return _plugin_extractor
