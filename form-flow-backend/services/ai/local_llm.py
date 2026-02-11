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
import json
from typing import Dict, List, Any, Optional


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
            
            
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

            # Log GPU status for debugging
            logger.info(f"CUDA Available: {torch.cuda.is_available()}")
            if torch.cuda.is_available():
                logger.info(f"Current Device: {torch.cuda.get_device_name(0)}")
                logger.info(f"CUDA Version: {torch.version.cuda}")
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_id, 
                trust_remote_code=True
            )
            
            # ATTEMPT 1: Load with BitsAndBytes (4-bit quantization) - Most Efficient
            if torch.cuda.is_available():
                try:
                    logger.info("🚀 Attempting to load with bitsandbytes (4-bit quantization)...")
                    # Check if bitsandbytes is actually installed
                    import bitsandbytes
                    
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
                    logger.info("✅ Successfully loaded with 4-bit quantization")
                    self._initialized = True
                    return
                except ImportError:
                    logger.warning("⚠️ bitsandbytes not installed. Skipping 4-bit loading.")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to load with 4-bit quantization: {e}")
                    logger.info("🔄 Falling back to standard GPU loading...")

            # ATTEMPT 2: Standard GPU Loading (FP16) - More Compatible
            if torch.cuda.is_available():
                try:
                    logger.info("🚀 Attempting to load in float16 on GPU...")
                    self.model = AutoModelForCausalLM.from_pretrained(
                        self.model_id,
                        device_map="cuda",  # Force CUDA
                        trust_remote_code=True,
                        dtype=torch.float16, # Half precision to save memory
                        low_cpu_mem_usage=True
                    )
                    logger.info("✅ Successfully loaded in float16 on GPU")
                    self._initialized = True
                    return
                except Exception as e:
                    logger.error(f"❌ Failed to load on GPU (FP16): {e}")
                    logger.info("🔄 Falling back to CPU...")

            # ATTEMPT 3: CPU Loading (Fallback)
            logger.info("🐌 Loading on CPU (Warning: This will be slow)...")
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                device_map="cpu",
                trust_remote_code=True,
                dtype=torch.float32,
                low_cpu_mem_usage=True
            )
            logger.info("✅ Successfully loaded on CPU")
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize local LLM: {e}")
            raise AIServiceError(f"Local LLM initialization failed: {e}")
    
    def extract_field_value(self, user_input: str, field_name: str) -> Dict[str, Any]:
        """
        Extract a single field value using the Local LLM.
        Now uses the smart batch extraction logic for consistency.
        """
        try:
            # Re-use the robust batch extraction for a single field
            batch_result = self.extract_all_fields(user_input, [field_name])
            
            extracted = batch_result.get('extracted', {})
            confidence = batch_result.get('confidence', {})
            
            # Check if our field was found
            # The batch extractor might return the key as the label or normalized name
            # We need to find the matching key in the result
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
                    "source": "local_llm"
                }
            
            return {
                "value": None,
                "confidence": 0.0,
                "source": "local_llm"
            }
            
        except Exception as e:
            logger.error(f"Error in extract_field_value: {e}")
            return {
                "value": None,
                "confidence": 0.0,
                "source": "local_llm",
                "error": str(e)
            }
    

    
    def extract_all_fields(self, user_input: str, fields: List[Any]) -> Dict[str, Any]:
        """
        Extract ALL fields from a single user input using Context-Aware LLM Inference.
        
        Args:
            user_input: The user's full input text
            fields: List of field definitions (Dicts) or field names (strings)
            
        Returns:
            Dict with extracted values, confidences, and source
        """
        # Ensure initialization
        self._initialize()
        
        # 1. Build the Schema Context
        schema_lines = []
        field_names = []
        
        for f in fields:
            # Handle both dict objects and simple strings (backward compatibility)
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
                field_names.append(name)
            else:
                schema_lines.append(f"- {str(f)}")
                field_names.append(str(f))

        schema_text = "\n".join(schema_lines)
        
        # 2. Construct the Smart Prompt
        # We tell the LLM to map the speech to the fields, respecting options
        prompt = f"""Instruct: You are a smart form-filling assistant. Map the user's speech to the following form fields.
        
FORM FIELDS:
{schema_text}

USER SPEECH:
"{user_input}"

INSTRUCTIONS:
1. Extract values for any fields mentioned in the speech.
2. For "Options" fields, map the speech to the closest valid option.
3. Infer values from context if explicit labels are missing (e.g. name at start of speech).
4. If a field is NOT mentioned, do not include it in the output.
5. Output format: "Field Label: Value"
6. Do NOT generate any code or extra text.

Output:"""

        # 3. Running Inference
        import torch
        inputs = self.tokenizer(prompt, return_tensors="pt")
        if self.model.device.type == "cuda":
            inputs = inputs.to("cuda")
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=256,
                temperature=0.1,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
                repetition_penalty=1.1, # Prevent repetition
                eos_token_id=self.tokenizer.eos_token_id
            )
        
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # 4. Parse the Output
        # Remove prompt to get just the generated text
        try:
            if "Output:" in response:
                generated = response.split("Output:")[-1].strip()
            else:
                generated = response[len(prompt):].strip()
        except:
            generated = response[len(prompt):].strip()
            
        logger.info(f"LLM Batch Extraction Output:\n{generated}")
        
        extracted_values = {}
        confidences = {}
        
        # Create a map of Label -> Field Name for easy lookup
        # and normalize labels for matching
        label_to_field = {}
        for f in fields:
            if isinstance(f, dict):
                label_to_field[f.get('label', f.get('name')).lower().strip()] = f.get('name')
                label_to_field[f.get('name').lower().strip()] = f.get('name')
            else:
                label_to_field[str(f).lower().strip()] = str(f)

        # Parse "Label: Value" lines with support for multi-line values
        current_field = None
        current_value = []
        
        for line in generated.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Stop parsing if we hit code blocks or obvious hallucinations
            if line.startswith("```") or line.startswith("def ") or line.startswith("import ") or line.startswith("#"):
                break
                
            # Handle bullet points if present "- Name: Value"
            if line.startswith("- "):
                line = line[2:]
            
            # Check if this line looks like a field definition "Label: Value"
            is_field_line = False
            parts = None
            
            if ':' in line:
                parts = line.split(':', 1)
                potential_key = parts[0].strip().lower()
                
                # Heuristic: Is this likely a label?
                # Labels are usually short (< 50 chars), no quotes, and mostly alphabetic
                # This prevents "Note: I said..." from being treated as a field
                if len(potential_key) < 50 and '"' not in potential_key and "'" not in potential_key:
                    is_field_line = True

            # Match against known fields
            matched_field_name = None
            if is_field_line:
                for label, field_name in label_to_field.items():
                    # Stricter matching: exact match or contained
                    # BUT be careful with "company" in "other company"
                    if label == potential_key:
                        matched_field_name = field_name
                        break
                    elif label in potential_key:
                        # Check if it's a "clean" containment (word boundary)
                        # e.g. "company" in "my company" is ok
                        # "age" in "message" is NOT ok
                        if f" {label}" in f" {potential_key}" or f"{label} " in f"{potential_key} ":
                             matched_field_name = field_name
                             break

            # Logic for field transition
            if matched_field_name:
                # It's a KNOWN field -> Save previous and start new
                if current_field and current_value:
                    # Save block
                    full_val = " ".join(current_value).strip()
                    if full_val and "\"" in full_val:
                        full_val = full_val.replace("\"", "")
                    
                    is_type_echo = False
                    for f in fields:
                        if isinstance(f, dict) and f.get('name') == current_field:
                            f_type = f.get('type', '').lower()
                            if full_val.lower() == f_type or full_val.lower() == f"type: {f_type}":
                                is_type_echo = True
                    
                    if not is_type_echo:
                        extracted_values[current_field] = full_val
                        confidences[current_field] = 0.85
                
                current_field = matched_field_name
                current_value = [parts[1].strip()]
            
            elif is_field_line:
                # It looks like a field "Key: Value" but UNKNOWN
                # This implies the LLM hallucinated an extra field or extracted one not in this batch
                # STOP capturing the previous field to avoid pollution
                if current_field and current_value:
                    # Save block
                    full_val = " ".join(current_value).strip()
                    if full_val and "\"" in full_val:
                        full_val = full_val.replace("\"", "")
                    
                    is_type_echo = False
                    for f in fields:
                        if isinstance(f, dict) and f.get('name') == current_field:
                            f_type = f.get('type', '').lower()
                            if full_val.lower() == f_type or full_val.lower() == f"type: {f_type}":
                                is_type_echo = True
                    
                    if not is_type_echo:
                        extracted_values[current_field] = full_val
                        confidences[current_field] = 0.85
                
                # We do NOT start a new current_field, effectively ignoring this unknown field and its value
                current_field = None
                current_value = []
                
            else:
                # Not a field line (just text value)
                if current_field:
                    if not current_value or line != current_value[-1]:
                        current_value.append(line)
        
        # Save the last field
        if current_field and current_value:
            full_val = " ".join(current_value).strip()
            if full_val and "\"" in full_val:
                full_val = full_val.replace("\"", "")
                
            is_type_echo = False
            for f in fields:
                if isinstance(f, dict) and f.get('name') == current_field:
                    f_type = f.get('type', '').lower()
                    if full_val.lower() == f_type or full_val.lower() == f"type: {f_type}":
                        is_type_echo = True
            
            if not is_type_echo:
                extracted_values[current_field] = full_val
                confidences[current_field] = 0.85
        
        return {
            "extracted": extracted_values,
            "confidence": confidences,
            "source": "local_llm_batch"
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