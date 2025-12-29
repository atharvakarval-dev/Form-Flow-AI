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
        local_model_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "models", "phi-2")
        if os.path.exists(local_model_path):
            self.model_id = os.path.abspath(local_model_path)
            logger.info(f"Using local model: {self.model_id}")
        else:
            self.model_id = model_id
            logger.info(f"Using HuggingFace model: {self.model_id}")
            
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
                    model="gemini-1.5-flash",
                    google_api_key=gemini_api_key,
                    temperature=0.3
                )
                logger.info("Gemini fallback initialized")
            except Exception as e:
                logger.warning(f"Gemini fallback failed: {e}")
        
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
        
        prompt = f"Extract {field_name} from: {user_input}\nAnswer:"
        inputs = self.tokenizer(prompt, return_tensors="pt")
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=8,
                temperature=0.1,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id
            )
        
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        extracted = response[len(prompt):].strip()
        
        return {
            "value": extracted,
            "confidence": min(0.9, len(extracted) / 15) if extracted else 0.1,
            "source": "local_llm"
        }
    
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
        
        field_lower = field_name.lower()
        
        # Email detection
        if 'email' in field_lower:
            email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', user_input)
            if email_match:
                return {"value": email_match.group(), "confidence": 0.9, "source": "heuristic"}
        
        # Name detection
        if 'name' in field_lower:
            # Look for capitalized words
            name_match = re.search(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', user_input)
            if name_match:
                return {"value": name_match.group(), "confidence": 0.7, "source": "heuristic"}
        
        # Phone detection
        if 'phone' in field_lower:
            phone_match = re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', user_input)
            if phone_match:
                return {"value": phone_match.group(), "confidence": 0.8, "source": "heuristic"}
        
        return {"value": "", "confidence": 0.0, "source": "heuristic"}


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