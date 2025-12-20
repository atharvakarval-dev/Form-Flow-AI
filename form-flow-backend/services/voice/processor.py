import openai
from google import genai
from typing import Dict, List, Any, Optional
import json
import re
from services.form.parser import format_email_input

class VoiceProcessor:
    def __init__(self, openai_key: str = None, gemini_key: str = None):
        self.openai_client = None
        if openai_key:
            try:
                self.openai_client = openai.OpenAI(api_key=openai_key)
            except TypeError:
                # Fallback if local httpx version is incompatible with the OpenAI SDK
                self.openai_client = None
        if gemini_key:
            self.client = genai.Client(api_key=gemini_key)
        else:
            self.client = None

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
        """Process voice input using LLM to improve clarity and accuracy"""
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
            response = self.client.models.generate_content(
                model='gemini-1.5-pro',
                contents=prompt
            )
            result = json.loads(response.text)
            # Apply additional formatting for special field types
            if is_email:
                result["processed_text"] = self._format_email_from_voice(result["processed_text"])
            elif is_checkbox:
                result["processed_text"] = self._format_checkbox_from_voice(result["processed_text"])
            return result
        except Exception as e:
            processed_text = self._format_field_input(transcript, field_info)
            return {
                "processed_text": processed_text,
                "confidence": 0.3,
                "suggestions": [f"Could you repeat that for {field_name}?"],
                "clarifying_questions": [f"I didn't catch that clearly. Could you repeat {field_name}?"]
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
                
            prompt = f"""
            Field: {field_name}
            User said: "{transcript}"
            
            Check if this looks correct for a {field_name} field.
            If it seems like there might be pronunciation errors, suggest a correction.
            For email fields, ensure proper format with @ and . symbols.
            
            Respond in JSON:
            {{
                "needs_confirmation": true/false,
                "suggestion": "corrected version",
                "confidence": 0.8
            }}
            """
            
            try:
                response = self.client.models.generate_content(
                    model='gemini-1.5-pro',
                    contents=prompt
                )
                result = json.loads(response.text)
                if is_email:
                    result["suggestion"] = self._format_email_from_voice(result["suggestion"])
                return result
            except:
                suggestion = self._format_field_input(transcript, field_info)
                return {"needs_confirmation": True, "suggestion": suggestion, "confidence": 0.5}
        
        return {"needs_confirmation": False, "suggestion": transcript, "confidence": 0.9}
    
    def _format_email_from_voice(self, text: str) -> str:
        """Convert voice input to proper email format with enhanced Gmail support"""
        if not text:
            return text
            
        # Convert common voice patterns to email symbols
        email_text = text.lower().strip()
        
        # Handle common email provider variations
        # "gmail" -> "gmail.com" if not already present
        email_text = re.sub(r'\bgmail\b(?!\.com)', 'gmail.com', email_text)
        email_text = re.sub(r'\byahoo\b(?!\.com)', 'yahoo.com', email_text)
        email_text = re.sub(r'\boutlook\b(?!\.com)', 'outlook.com', email_text)
        email_text = re.sub(r'\bhotmail\b(?!\.com)', 'hotmail.com', email_text)
        
        # Convert "at" to "@" (handle variations)
        email_text = re.sub(r'\b(at|add|ampersand)\b', '@', email_text, flags=re.IGNORECASE)
        
        # Convert "dot" to "." (handle variations)
        email_text = re.sub(r'\b(dot|period|point|full stop)\b', '.', email_text, flags=re.IGNORECASE)
        
        # Handle "underscore" or "under score"
        email_text = re.sub(r'\b(underscore|under score|under_score)\b', '_', email_text, flags=re.IGNORECASE)
        
        # Handle "dash" or "hyphen" or "minus"
        email_text = re.sub(r'\b(dash|hyphen|minus)\b', '-', email_text, flags=re.IGNORECASE)
        
        # Remove "space" mentions
        email_text = re.sub(r'\bspace\b', '', email_text, flags=re.IGNORECASE)
        
        # Remove all actual spaces
        email_text = email_text.replace(' ', '')
        
        # Clean up multiple consecutive dots (except in domain)
        email_text = re.sub(r'\.{2,}', '.', email_text)
        
        # Ensure @ symbol exists (if not, try to infer from structure)
        if '@' not in email_text and '.' in email_text:
            # Try to find where @ should be (usually before the last dot sequence)
            parts = email_text.split('.')
            if len(parts) >= 2:
                # Common pattern: "john dot smith at gmail dot com"
                # After processing becomes: "john.smithgmail.com"
                # Try to fix: look for common domain patterns
                common_domains = ['gmail', 'yahoo', 'outlook', 'hotmail', 'icloud', 'protonmail']
                for domain in common_domains:
                    if domain in email_text:
                        # Replace domain with domain.com
                        email_text = re.sub(rf'\b{domain}\b', f'{domain}.com', email_text)
                        # Try to insert @ before domain
                        domain_pos = email_text.find(domain)
                        if domain_pos > 0:
                            # Check if there's already a @ nearby
                            before_domain = email_text[:domain_pos]
                            if '@' not in before_domain:
                                # Insert @ before the domain
                                email_text = before_domain.rstrip('.') + '@' + email_text[domain_pos:]
                        break
        
        # Final cleanup: ensure proper email format
        # Remove any remaining spaces
        email_text = email_text.replace(' ', '').strip()
        
        # Validate basic email structure
        if '@' in email_text and '.' in email_text.split('@')[1]:
            # Basic validation passed
            return email_text
        
        # If still no @, return as-is (let LLM handle it)
        return email_text
    
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
        Normalize email by fixing STT spacing errors and converting voice keywords.
        
        Assumes user spoke email correctly, but STT inserted spaces or converted
        spoken punctuation to words.
        
        Example 1: " Atharv shashikant.karwal@gmail.com" 
                → "atharv.shashikant.karwal@gmail.com"
        Example 2: "Atharv dot shashikant at gmail dot com"
                → "atharv.shashikant@gmail.com"
        
        Logic:
        1. Strip leading/trailing spaces
        2. Convert to lowercase
        3. Replace voice keywords (dot → ., at → @, underscore → _)
        4. Split at @ symbol
        5. In local part (before @): replace spaces with dots
        6. Preserve domain part exactly
        7. Don't insert dot if space is immediately before/after @
        """
        email = text.strip().lower()
        
        # Convert voice keywords to punctuation
        # "atharv dot shashikant at gmail dot com" → "atharv.shashikant@gmail.com"
        email = email.replace(' dot ', '.')
        email = email.replace(' at ', '@')
        email = email.replace(' underscore ', '_')
        email = email.replace(' dash ', '-')
        
        # Handle edge cases where dot/at are at the end
        email = email.replace(' dot', '.')
        email = email.replace(' at', '@')
        email = email.replace(' underscore', '_')
        
        # Add common domain endings if missing
        if '@' in email and '.' not in email.split('@')[1]:
            # "user@gmail" → "user@gmail.com"
            if email.endswith('gmail'):
                email += '.com'
            elif email.endswith('yahoo'):
                email += '.com'
            elif email.endswith('outlook'):
                email += '.com'
        
        if '@' not in email:
            # Not an email, return as-is
            return email
        
        # Split into local and domain parts
        parts = email.split('@', 1)
        local_part = parts[0].strip()
        domain_part = parts[1].strip() if len(parts) > 1 else ''
        
        # Replace remaining spaces with dots in local part
        # "atharv shashikant.karwal" → "atharv.shashikant.karwal"
        normalized_local = local_part.replace(' ', '.')
        
        # Remove consecutive dots (in case of multiple spaces)
        while '..' in normalized_local:
            normalized_local = normalized_local.replace('..', '.')
        
        # Remove leading/trailing dots
        normalized_local = normalized_local.strip('.')
        
        return f"{normalized_local}@{domain_part}"
    
    def _strengthen_password(self, password: str, requirements: dict) -> str:
        """
        Add missing special characters if password doesn't meet requirements.
        
        Common form requirements:
        - At least one special character
        - At least one number
        - At least one uppercase letter
        """
        # Check requirements (default to True if not specified)
        needs_special = requirements.get('special_char', True)
        needs_number = requirements.get('number', True)
        needs_uppercase = requirements.get('uppercase', True)
        
        # Check what's missing
        has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password))
        has_number = bool(re.search(r'\d', password))
        has_uppercase = bool(re.search(r'[A-Z]', password))
        
        # Add special character if missing and needed
        if needs_special and not has_special:
            # Intelligent replacement: replace space with @ or add @ at end
            if ' ' in password:
                password = password.replace(' ', '@', 1)  # Replace only first space
            else:
                password = password + '@'
        
        # Note: We don't auto-add numbers or uppercase as that changes the user's intended password too much
        # The form validation will catch those if truly required
        
        return password