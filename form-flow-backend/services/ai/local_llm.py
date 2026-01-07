"""
Local LLM Service for Form Flow AI

Provides local inference using Phi-2 model for form field extraction
and conversational flow generation when cloud APIs are unavailable.

Usage:
    from services.ai.local_llm import LocalLLMService
    
    service = LocalLLMService()
    result = service.extract_field_value("My name is John", "First Name")
"""

import os
import json
import torch
from typing import Dict, List, Any, Optional
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

from utils.logging import get_logger
from utils.exceptions import AIServiceError

logger = get_logger(__name__)


class LocalLLMService:
    """
    Local-first LLM service with Gemini fallback.
    
    Routes:
    - Simple extraction → Local 3B LLM (instant, free)
    - Complex reasoning → Gemini API (rare, pay-per-use)
    - Cache hits → Instant return
    """
    
    def __init__(self, model_id: str = "microsoft/phi-2", gemini_api_key: str = None):
        # Use local model path if available, fallback to HuggingFace
        import os
        
        # Calculate project root (Form-Flow-AI directory)
        # Path: services/ai/local_llm.py -> services/ai -> services -> form-flow-backend -> Form-Flow-AI
        backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        project_root = os.path.dirname(backend_root)
        local_model_path = os.path.join(project_root, "models", "phi-2")
        
        # Also check settings for custom path
        try:
            from config.settings import settings
            if hasattr(settings, 'LOCAL_MODEL_PATH') and settings.LOCAL_MODEL_PATH:
                local_model_path = settings.LOCAL_MODEL_PATH
        except Exception:
            pass
        
        if os.path.exists(local_model_path):
            self.model_id = os.path.abspath(local_model_path)
            logger.info(f"✅ Using LOCAL model: {self.model_id}")
        else:
            self.model_id = model_id
            logger.info(f"🌐 Using HuggingFace model: {self.model_id}")
            
        self.gemini_api_key = gemini_api_key
        self.model = None
        self.tokenizer = None
        self._initialized = False
        self._cache = {}  # Simple in-memory cache
        
        # Initialize Gemini fallback if available
        self.gemini_llm = None
        if gemini_api_key:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                self.gemini_llm = ChatGoogleGenerativeAI(
                    model="gemini-2.0-flash",
                    google_api_key=gemini_api_key,
                    temperature=0.3
                )
                logger.info("Gemini fallback initialized")
            except Exception as e:
                logger.warning(f"Gemini fallback failed: {e}")
        
    async def initialize_async(self):
        """Async initialization to be called during startup."""
        try:
            import asyncio
            # Run blocking initialization in thread
            await asyncio.to_thread(self._initialize)
        except Exception as e:
            logger.error(f"Async LLM initialization failed: {e}")

    def _initialize(self):
        """Lazy initialization of model and tokenizer."""
        if self._initialized:
            return
            
        try:
            logger.info(f"Loading local LLM: {self.model_id}")
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_id, 
                trust_remote_code=True
            )
            
            # Load model with CPU/GPU optimization
            if torch.cuda.is_available():
                logger.info("GPU detected, loading with quantization")
                quant_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    llm_int8_enable_fp32_cpu_offload=True
                )
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_id,
                    device_map="auto",
                    quantization_config=quant_config,
                    trust_remote_code=True,
                    dtype=torch.float16
                )
            else:
                logger.info("No GPU detected, loading on CPU")
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_id,
                    device_map="cpu",
                    trust_remote_code=True,
                    dtype=torch.float32,
                    low_cpu_mem_usage=True
                )
            
            self._initialized = True
            logger.info("✅ Local LLM loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize local LLM: {e}")
            raise AIServiceError(f"Local LLM initialization failed: {e}")
    
    def extract_field_value(self, user_input: str, field_name: str) -> Dict[str, Any]:
        """
        Extract field value with local-first routing.
        
        Route logic:
        1. Check cache (instant)
        2. Use local LLM (fast, free)
        3. Fallback to Gemini for complex cases
        """
        # 1. Check cache first
        cache_key = f"{user_input.lower()}:{field_name.lower()}"
        if cache_key in self._cache:
            logger.info(f"Cache hit for {field_name}")
            return self._cache[cache_key]
        
        # 2. Try local LLM first (primary path)
        try:
            result = self._extract_with_local_llm(user_input, field_name)
            if result.get('confidence', 0) > 0.4:  # Good enough confidence
                self._cache[cache_key] = result
                return result
        except Exception as e:
            logger.warning(f"Local LLM failed: {e}")
        
        # 3. Fallback to Gemini for complex cases
        if self.gemini_llm:
            try:
                logger.info(f"Using Gemini fallback for {field_name}")
                result = self._extract_with_gemini(user_input, field_name)
                self._cache[cache_key] = result
                return result
            except Exception as e:
                logger.error(f"Gemini fallback failed: {e}")
        
        # 4. Final fallback - simple heuristics
        return self._extract_with_heuristics(user_input, field_name)
    
    
    def _extract_with_local_llm(self, user_input: str, field_name: str) -> Dict[str, Any]:
        """Extract using local 3B model."""
        self._initialize()
        
        # Preprocess input for common spoken patterns
        cleaned_input = user_input.replace("at the rate", "@").replace(" at ", "@").replace(" dot ", ".")
        
        # Improved prompt for phi-2
        prompt = f"Instruct: Extract the {field_name} from the user input.\nUser Input: {cleaned_input}\nOutput:"
        inputs = self.tokenizer(prompt, return_tensors="pt")
        
        if self.model.device.type == "cuda":
            inputs = inputs.to("cuda")
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=32,  # Increased from 8 to allow full emails/addresses
                temperature=0.1,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id
            )
        
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Phi-2 chat format parsing
        try:
            if "Output:" in response:
                extracted = response.split("Output:")[-1].strip()
            else:
                extracted = response[len(prompt):].strip()
        except:
            extracted = response[len(prompt):].strip()
            
        # Clean up any trailing text
        if "\n" in extracted:
            extracted = extracted.split("\n")[0].strip()
        
        return {
            "value": extracted,
            "confidence": min(0.9, len(extracted) / 10) if extracted else 0.1,
            "source": "local_llm"
        }

    def generate_response(self, system_instruction: str, user_input: str) -> str:
        """
        Generate a response using the local LLM.
        Useful for suggestions and chat-like interactions.
        """
        # Ensure initialization
        self._initialize()
        
        # Phi-2 instruct format
        prompt = f"Instruct: {system_instruction}\n\nUser: {user_input}\nOutput:"
        
        inputs = self.tokenizer(prompt, return_tensors="pt")
        if self.model.device.type == "cuda":
            inputs = inputs.to("cuda")
            
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=256,
                temperature=0.3,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id
            )
            
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        try:
            if "Output:" in response:
                return response.split("Output:")[-1].strip()
            return response[len(prompt):].strip()
        except:
            return response.strip()
    
    def _extract_with_gemini(self, user_input: str, field_name: str) -> Dict[str, Any]:
        """Extract using Gemini for complex cases."""
        from langchain_core.messages import HumanMessage
        
        message = HumanMessage(content=f"""
        Extract the {field_name} from this user input: "{user_input}"
        
        Return only the extracted value, nothing else.
        If you cannot extract it, return "UNKNOWN".
        """)
        
        response = self.gemini_llm.invoke([message])
        extracted = response.content.strip()
        
        return {
            "value": extracted if extracted != "UNKNOWN" else "",
            "confidence": 0.8 if extracted != "UNKNOWN" else 0.1,
            "source": "gemini_fallback"
        }
    
    def _extract_with_heuristics(self, user_input: str, field_name: str) -> Dict[str, Any]:
        """Simple heuristic extraction as final fallback."""
        import re
        
        # Normalize input first
        normalized = self._normalize_input(user_input)
        field_lower = field_name.lower()
        
        # Email detection (robust for spoken patterns)
        if 'email' in field_lower:
            email_match = re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', normalized)
            if email_match:
                return {"value": email_match.group().lower(), "confidence": 0.9, "source": "heuristic"}
        
        # Name detection (handles multi-word names)
        if 'name' in field_lower:
            # Look for "name is X" or "I'm X" patterns
            name_patterns = [
                r'(?:my\s+)?name\s+is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r"(?:i'?m|this is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)'  # 2+ capitalized words
            ]
            for pattern in name_patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    name = match.group(1).strip()
                    # Title case the name
                    name = ' '.join(word.capitalize() for word in name.split())
                    return {"value": name, "confidence": 0.85, "source": "heuristic"}
        
        # Phone detection (handles Indian and intl formats)
        if 'phone' in field_lower or 'mobile' in field_lower or 'number' in field_lower:
            # Remove spaces and common separators
            digits_only = re.sub(r'[^\d]', '', normalized)
            if len(digits_only) >= 9:
                # Take last 10 digits if longer (standardizing), or keep as is if 9-10
                phone = digits_only[-10:] if len(digits_only) > 10 else digits_only
                return {"value": phone, "confidence": 0.85, "source": "heuristic"}
        
        return {"value": "", "confidence": 0.0, "source": "heuristic"}
    
    def _normalize_input(self, user_input: str) -> str:
        """Normalize spoken input patterns to standard formats."""
        import re
        
        normalized = user_input
        
        # Email normalization - handle spoken patterns like "Atharva Karwal @ gmail.com"
        # Step 1: Replace "at the rate" with @
        normalized = re.sub(r'\bat\s+the\s+rate\b', '@', normalized, flags=re.IGNORECASE)
        
        # Step 2: Replace " at " with @ (common spoken pattern)
        normalized = re.sub(r'\s+at\s+', '@', normalized)
        
        # Step 3: Replace " dot " with .
        normalized = re.sub(r'\s+dot\s+', '.', normalized, flags=re.IGNORECASE)
        
        # Step 4: Handle spoken email patterns like "name name @ domain.com"
        # Find patterns where there are words before @ and after @
        # e.g., "Atharva Karwal @ gmail.com" -> "atharvakarwal@gmail.com"
        email_spoken_pattern = re.search(
            r'([A-Za-z]+(?:\s+[A-Za-z]+)*)\s*@\s*([A-Za-z0-9.-]+\.[A-Za-z]{2,})',
            normalized
        )
        if email_spoken_pattern:
            username_part = email_spoken_pattern.group(1).replace(' ', '').lower()
            domain_part = email_spoken_pattern.group(2).lower()
            reconstructed_email = f"{username_part}@{domain_part}"
            # Replace the original spoken pattern with the normalized email
            normalized = normalized[:email_spoken_pattern.start()] + reconstructed_email + normalized[email_spoken_pattern.end():]
        
        # Number word to digit (for phone numbers in speech)
        number_words = {
            'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
            'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
            'double': '  '  # placeholder for "double five" -> "55"
        }
        
        for word, digit in number_words.items():
            normalized = re.sub(rf'\b{word}\b', digit, normalized, flags=re.IGNORECASE)
        
        # Handle "double X" pattern (e.g., "double five" -> "55")
        normalized = re.sub(r'  (\d)', r'\1\1', normalized)
        
        return normalized
    
    def extract_all_fields(self, user_input: str, fields: List[str]) -> Dict[str, Any]:
        """
        Extract ALL fields from a single user input in one pass.
        
        This is more efficient than calling extract_field_value multiple times
        and better handles multi-field responses like:
        "My name is John, email is john@test.com, phone is 1234567890"
        
        Args:
            user_input: The user's full input text
            fields: List of field names to extract (e.g., ["Full Name", "Email", "Phone"])
            
        Returns:
            Dict with extracted values, confidences, and source
        """
        results = {}
        normalized = self._normalize_input(user_input)
        
        for field in fields:
            result = self._extract_with_heuristics(normalized, field)
            if result.get('value') and result.get('confidence', 0) > 0.3:
                results[field] = result
        
        return {
            "extracted": {k: v["value"] for k, v in results.items()},
            "confidence": {k: v["confidence"] for k, v in results.items()},
            "source": "batch_heuristic"
        }


# Singleton instance
_local_llm_instance: Optional[LocalLLMService] = None


def get_local_llm_service(gemini_api_key: str = None) -> Optional[LocalLLMService]:
    """Get singleton LocalLLMService instance with optional Gemini fallback."""
    global _local_llm_instance
    if _local_llm_instance is None:
        try:
            _local_llm_instance = LocalLLMService(gemini_api_key=gemini_api_key)
        except Exception as e:
            logger.warning(f"Could not initialize LocalLLMService: {e}")
            return None
    return _local_llm_instance


def is_local_llm_available() -> bool:
    """Check if local LLM can be initialized."""
    try:
        service = get_local_llm_service()
        return service is not None
    except:
        return False