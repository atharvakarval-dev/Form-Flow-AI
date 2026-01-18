from openai import OpenAI
from typing import Dict, List, Any, Optional
import json
import re
from services.form.parser import format_email_input
from config.settings import settings


class VoiceProcessor:
    """
    Voice input processor using OpenRouter API for LLM-based extraction.
    
    Uses OpenRouter with Gemma 3 27B for fast, accurate voice input processing.
    """
    
    def __init__(self, openrouter_key: str = None):
        self.client = None
        api_key = openrouter_key or settings.OPENROUTER_API_KEY
        
        if api_key:
            try:
                self.client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=api_key,
                    timeout=15.0
                )
                self.model = "google/gemma-3-27b-it"
                print(f"✅ VoiceProcessor initialized with OpenRouter ({self.model})")
            except Exception as e:
                print(f"⚠️ Failed to initialize OpenRouter client: {e}")
                self.client = None
        else:
            print("⚠️ OPENROUTER_API_KEY not configured - LLM features disabled")

    def analyze_form_context(self, form_schema: List[Dict]) -> str:
        """Analyze form structure and create context for intelligent prompts"""
        context = "Form Analysis:\n"
        for form in form_schema:
            context += f"Form Action: {form.get('action', 'N/A')}\n"
            context += "Fields:\n"
            for field in form.get('fields', []):
                field_type = field.get('type', 'text')
                label = field.get('label', field.get('name', 'Unnamed'))
                required = " (Required)" if field.get('required') else ""
                context += f"- {label}: {field_type}{required}\n"
                if field.get('options'):
                    options = [opt.get('label', opt.get('value', '')) for opt in field['options']]
                    context += f"  Options: {', '.join(options)}\n"
        return context

    def generate_smart_prompt(self, form_context: str, field_info: Dict) -> str:
        """Generate context-aware prompts for form fields"""
        field_name = field_info.get('label', field_info.get('name', 'field'))
        field_type = field_info.get('type', 'text')
        required = field_info.get('required', False)
        options = field_info.get('options', [])
        
        prompt_templates = {
            'email': f"Please provide your email address for {field_name}",
            'password': f"Please speak your password for {field_name}",
            'tel': f"Please provide your phone number for {field_name}",
            'date': f"Please provide the date for {field_name} (you can say it naturally like 'January 15th 2024')",
            'select': f"Please choose from the available options for {field_name}",
            'dropdown': f"Please choose from the available options for {field_name}",
            'radio': f"Please choose one of the options for {field_name}",
            'textarea': f"Please provide your response for {field_name}. You can speak as much as needed",
            'checkbox': f"Say 'yes' to check or 'no' to uncheck {field_name}",
            'text': f"Please provide {field_name}"
        }
        
        base_prompt = prompt_templates.get(field_type, f"Please provide {field_name}")
        
        # Add options listing for dropdown/select/radio fields with numbered format
        if field_type in ['select', 'dropdown', 'radio'] and options:
            option_labels = [opt.get('label', opt.get('value', '')) for opt in options if opt.get('label') or opt.get('value')]
            if option_labels:
                # Format as numbered list: "Option 1: Freshman, Option 2: Sophomore..."
                numbered_options = [f"Option {i+1}: {label}" for i, label in enumerate(option_labels[:8])]  # Limit to 8 for voice
                options_text = ". ".join(numbered_options)
                if len(option_labels) > 8:
                    options_text += f". And {len(option_labels) - 8} more options"
                base_prompt = f"For {field_name}, say the option name or number. {options_text}"
        
        if required:
            base_prompt += " (This field is required)"
            
        return base_prompt

    def process_voice_input(self, transcript: str, field_info: Dict, form_context: str) -> Dict:
        """Process voice input using Local LLM (speed) with Gemini fallback (accuracy)"""
        
        # 1. Try Local LLM first (Fastest Response)
        try:
            from services.ai.local_llm import get_local_llm_service
            local_llm = get_local_llm_service()
            
            if local_llm:
                field_name = field_info.get('label', field_info.get('name', 'field'))
                local_result = local_llm.extract_field_value(transcript, field_name)
                
                # If Local LLM is confident, return immediately!
                if local_result.get('confidence', 0) > 0.6:
                    print(f"⚡ Local LLM Hit: {local_result['value']} (conf: {local_result['confidence']})")
                    return {
                        "processed_text": local_result['value'],
                        "confidence": local_result['confidence'],
                        "suggestions": [],
                        "source": "local_phi2"
                    }
        except Exception as e:
            print(f"⚠️ Local LLM skipped: {e}")

        # 2. Fallback to OpenRouter (Cloud)
        if not self.client:
            processed_text = self._format_field_input(transcript, field_info)
            return {"processed_text": processed_text, "confidence": 0.5, "suggestions": []}

        field_type = field_info.get('type', 'text')
        field_name = field_info.get('label', field_info.get('name', 'field'))
        
        # Enhanced email detection: check type, flag, name patterns, or transcript content
        is_email = (
            field_info.get('is_email', False) or 
            field_type == 'email' or
            'email' in field_name.lower() or
            'e-mail' in field_name.lower() or
            '@' in transcript or
            ' at gmail' in transcript.lower() or
            ' at yahoo' in transcript.lower() or
            ' at outlook' in transcript.lower() or
            'dot com' in transcript.lower()
        )
        
        is_checkbox = field_info.get('is_checkbox', False) or field_type == 'checkbox'
        is_dropdown = field_info.get('is_dropdown', False) or field_type in ['select', 'dropdown', 'radio']
        options = field_info.get('options', [])
        
        special_instructions = ""
        if is_email:
            special_instructions = """
        SPECIAL EMAIL FORMATTING RULES (ENHANCED FOR GMAIL):
        - Convert 'at', 'add', 'ampersand' to '@'
        - Convert 'dot', 'period', 'point' to '.'
        - Convert 'underscore' or 'under score' to '_'
        - Convert 'dash', 'hyphen', 'minus' to '-'
        - Remove all spaces
        - Make everything lowercase
        - Handle common email providers: 'gmail' -> 'gmail.com', 'yahoo' -> 'yahoo.com', etc.
        - If user says just 'gmail' without '.com', automatically add '.com'
        - Examples:
          * 'john dot smith at gmail dot com' -> 'john.smith@gmail.com'
          * 'jane underscore doe at gmail' -> 'jane_doe@gmail.com'
          * 'test dash user at yahoo dot com' -> 'test-user@yahoo.com'
          * 'myemail at gmail' -> 'myemail@gmail.com'
        - Ensure proper email format: localpart@domain.tld
        - If format is unclear, suggest the most likely interpretation
        """
        elif is_checkbox:
            special_instructions = """
        SPECIAL CHECKBOX FORMATTING RULES:
        - Convert positive responses (yes, true, check, agree, etc.) to 'true'
        - Convert negative responses (no, false, uncheck, disagree, etc.) to 'false'
        - Default to 'false' if unclear
        - Example: 'yes I agree' becomes 'true', 'no thanks' becomes 'false'
        """
        elif is_dropdown and options:
            # Build options list for LLM
            options_list = []
            for opt in options:
                value = opt.get('value', '')
                label = opt.get('label', value)
                options_list.append(f'  - Value: "{value}", Label: "{label}"')
            options_text = "\n".join(options_list)
            
            special_instructions = f"""
        SPECIAL DROPDOWN/SELECT FIELD RULES:
        This is a constrained choice field. The user MUST select from these valid options ONLY:
{options_text}
        
        CRITICAL MATCHING RULES:
        1. Match the user's spoken input to the CLOSEST valid option above
        2. Use fuzzy matching - "united states" matches "USA", "u.s.a." matches "USA"
        3. Return the exact VALUE (not label) in processed_text for correct form submission
        4. If no reasonable match found, set confidence to 0.2 and ask for clarification
        5. If multiple options could match, ask user to clarify
        
        Examples:
        - User says "I'm from the United States" -> processed_text: "USA" (if USA is a valid value)
        - User says "the first option" -> processed_text: (first option's value)
        - User says "something not in list" -> confidence: 0.2, ask for clarification
        """
        
        prompt = f"""
        Form Context: {form_context}
        Current Field: {field_name} (Type: {field_type})
        User Voice Input: "{transcript}"
        {special_instructions}
        
        Task: Process and improve the voice input for this form field with HIGH ACCURACY.
        
        Requirements:
        1. Clean up the transcript (fix obvious speech-to-text errors, especially for email addresses)
        2. Format appropriately for the field type (CRITICAL for email fields)
        3. For email fields: Ensure proper format (localpart@domain.tld), handle Gmail and other providers correctly
        4. If unclear or incomplete, suggest clarifying questions
        5. Provide confidence score (0-1) - be conservative if uncertain
        6. For email fields, double-check that '@' and '.' are in correct positions
        7. For dropdown/select fields: ONLY return valid option values, never free text
        
        IMPORTANT FOR EMAIL FIELDS:
        - If the transcript contains email-like patterns, ensure proper formatting
        - Common errors to fix: missing @, missing .com, wrong spacing
        - If user says "gmail" without "dot com", assume they mean "gmail.com"
        - Validate the email structure before returning
        
        Respond in JSON format:
        {{
            "processed_text": "cleaned and formatted text",
            "confidence": 0.8,
            "suggestions": ["suggestion1", "suggestion2"],
            "clarifying_questions": ["question1", "question2"]
        }}
        """
        
        try:
            # Use OpenRouter with Gemma 3 27B for fast inference
            response = self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "https://formflow.ai",
                    "X-Title": "Form Flow AI Voice Processor",
                },
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a form-filling assistant. Process voice input and return JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Apply additional formatting for special field types
            if is_email:
                result["processed_text"] = self._format_email_from_voice(result.get("processed_text", ""))
            elif is_checkbox:
                result["processed_text"] = self._format_checkbox_from_voice(result.get("processed_text", ""))
            
            result["source"] = "openrouter_gemma3"
            return result
            
        except Exception as e:
            print(f"⚠️ OpenRouter voice processing error: {e}")
            processed_text = self._format_field_input(transcript, field_info)
            return {
                "processed_text": processed_text,
                "confidence": 0.3,
                "suggestions": [f"Could you repeat that for {field_name}?"],
                "clarifying_questions": [f"I didn't catch that clearly. Could you repeat {field_name}?"],
                "source": "fallback"
            }

    def handle_pause_suggestions(self, field_info: Dict, form_context: str) -> List[str]:
        """Generate helpful suggestions when user pauses"""
        field_type = field_info.get('type', 'text')
        field_name = field_info.get('label', field_info.get('name', 'field'))
        
        suggestions = {
            'email': [
                f"For {field_name}, say it like 'john dot smith at gmail dot com'",
                f"You can also say 'john underscore smith at gmail' and I'll format it correctly",
                f"For Gmail addresses, you can just say 'username at gmail' and I'll add the '.com' automatically"
            ],
            'tel': [f"For {field_name}, you can say your phone number digit by digit or naturally"],
            'date': [f"For {field_name}, you can say the date naturally like 'March 15th 2024'"],
            'select': [f"For {field_name}, please choose one of the available options"],
            'password': [f"For {field_name}, please speak your password clearly"],
            'textarea': [f"For {field_name}, you can speak as much as you need. Take your time."],
            'checkbox': [f"For {field_name}, say 'yes' to check it or 'no' to leave it unchecked"]
        }
        
        return suggestions.get(field_type, [f"Please provide your {field_name}. Take your time."])

    def validate_pronunciation(self, transcript: str, field_info: Dict) -> Dict:
        """Validate and suggest corrections for pronunciation-sensitive fields"""
        field_type = field_info.get('type', 'text')
        field_name = field_info.get('label', field_info.get('name', 'field'))
        
        # For name fields, email addresses, etc.
        is_email = field_info.get('is_email', False) or field_type == 'email'
        if 'name' in field_name.lower() or is_email:
            if not self.client:
                return {"needs_confirmation": True, "suggestion": transcript}
                
            prompt = f"""Field: {field_name}
User said: "{transcript}"

Check if this looks correct for a {field_name} field.
If it seems like there might be pronunciation errors, suggest a correction.
For email fields, ensure proper format with @ and . symbols.

Respond in JSON:
{{
    "needs_confirmation": true/false,
    "suggestion": "corrected version",
    "confidence": 0.8
}}"""
            
            try:
                response = self.client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "https://formflow.ai",
                        "X-Title": "Form Flow AI Pronunciation Validator",
                    },
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a pronunciation validator. Return JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )
                result = json.loads(response.choices[0].message.content)
                if is_email:
                    result["suggestion"] = self._format_email_from_voice(result.get("suggestion", ""))
                return result
            except Exception as e:
                print(f"⚠️ OpenRouter pronunciation validation error: {e}")
                suggestion = self._format_field_input(transcript, field_info)
                return {"needs_confirmation": True, "suggestion": suggestion, "confidence": 0.5}
        
        return {"needs_confirmation": False, "suggestion": transcript, "confidence": 0.9}
    
    def _format_email_from_voice(self, text: str) -> str:
        """
        Convert voice input to proper email format using centralized smart normalizer.
        
        This prevents corruption of names like "Atharva" → "@harva".
        See services/ai/normalizers.py for the implementation.
        """
        from services.ai.normalizers import normalize_email_smart
        return normalize_email_smart(text)
    
    def _format_checkbox_from_voice(self, text: str) -> str:
        """Convert voice input to checkbox boolean value"""
        if not text:
            return "false"
            
        text_lower = text.lower().strip()
        
        # Positive responses
        positive_words = ['yes', 'true', 'check', 'checked', 'tick', 'ticked', 'select', 'selected', 'agree', 'accept', 'on', 'enable', 'enabled']
        # Negative responses  
        negative_words = ['no', 'false', 'uncheck', 'unchecked', 'untick', 'unticked', 'deselect', 'deselected', 'disagree', 'decline', 'off', 'disable', 'disabled']
        
        if any(word in text_lower for word in positive_words):
            return "true"
        elif any(word in text_lower for word in negative_words):
            return "false"
        
        # Default to false if unclear
        return "false"
    
    def _format_field_input(self, text: str, field_info: Dict) -> str:
        """Format input based on field type"""
        field_type = field_info.get('type', 'text')
        is_email = field_info.get('is_email', False) or field_type == 'email'
        
        if is_email:
            return self._format_email_from_voice(text)
        elif field_info.get('is_checkbox', False) or field_type == 'checkbox':
            return self._format_checkbox_from_voice(text)
        
        return text
    
    def format_field_value(self, raw_value: str, field_info: Dict) -> str:
        """
        Basic cleanup only - NO form-specific formatting.
        Form schema (form_conventions.py) handles all validation/formatting.
        
        This method only does minimal voice transcription cleanup.
        """
        # Only strip leading/trailing whitespace from voice input
        return raw_value.strip()
    
    def _normalize_email(self, text: str) -> str:
        """
        Normalize email using centralized smart normalizer.
        
        This prevents corruption of names like "Atharva" → "@harva".
        See services/ai/normalizers.py for the implementation.
        """
        from services.ai.normalizers import normalize_email_smart
        return normalize_email_smart(text)
    
    def _strengthen_password(self, password: str, requirements: dict) -> str:
        """
        Generate a strong password or strengthen an existing one.
        
        Uses cryptographically secure randomness (secrets module).
        Guaranteed to include: uppercase, lowercase, digit, special char.
        
        Args:
            password: User's spoken password (may be weak or empty)
            requirements: Dict with optional 'min_length', 'special_char', etc.
        
        Returns:
            Strong password meeting all requirements
        """
        import secrets
        import string
        
        # Configuration
        min_length = requirements.get('min_length', 12)
        max_length = requirements.get('max_length', 20)
        needs_special = requirements.get('special_char', True)
        needs_number = requirements.get('number', True)
        needs_uppercase = requirements.get('uppercase', True)
        
        # Check if user's password already meets requirements
        has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=~`\[\]\\;\'\/]', password))
        has_number = bool(re.search(r'\d', password))
        has_uppercase = bool(re.search(r'[A-Z]', password))
        has_lowercase = bool(re.search(r'[a-z]', password))
        
        # If user's password is already strong enough, use it (respecting their choice)
        if (len(password) >= min_length and
            (not needs_special or has_special) and
            (not needs_number or has_number) and
            (not needs_uppercase or has_uppercase) and
            has_lowercase):
            return password
        
        # If user provided a weak password or nothing, generate a strong one
        # Character pools
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase
        digits = string.digits
        special = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        
        # Build the base character set
        all_chars = lowercase + uppercase + digits
        if needs_special:
            all_chars += special
        
        # Determine password length (use user's length if longer than minimum)
        length = max(min_length, len(password)) if password else min_length
        length = min(length, max_length)  # Cap at max
        
        # Generate password ensuring all required character types
        while True:
            # Guarantee at least one of each required type
            guaranteed_chars = [
                secrets.choice(lowercase),  # Always need lowercase
            ]
            if needs_uppercase:
                guaranteed_chars.append(secrets.choice(uppercase))
            if needs_number:
                guaranteed_chars.append(secrets.choice(digits))
            if needs_special:
                guaranteed_chars.append(secrets.choice(special))
            
            # Fill remaining length with random chars
            remaining_length = length - len(guaranteed_chars)
            random_chars = [secrets.choice(all_chars) for _ in range(remaining_length)]
            
            # Combine and shuffle
            password_chars = guaranteed_chars + random_chars
            secrets.SystemRandom().shuffle(password_chars)
            
            generated = ''.join(password_chars)
            
            # Verify it meets requirements (should always pass, but double-check)
            if (len(generated) >= min_length and
                bool(re.search(r'[a-z]', generated)) and
                (not needs_uppercase or bool(re.search(r'[A-Z]', generated))) and
                (not needs_number or bool(re.search(r'\d', generated))) and
                (not needs_special or bool(re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', generated)))):
                return generated


# Singleton instance
_voice_processor_instance: Optional[VoiceProcessor] = None


def get_voice_processor(openrouter_key: str = None) -> VoiceProcessor:
    """Get singleton VoiceProcessor instance."""
    global _voice_processor_instance
    if _voice_processor_instance is None:
        _voice_processor_instance = VoiceProcessor(
            openrouter_key=openrouter_key or settings.OPENROUTER_API_KEY
        )
    return _voice_processor_instance
