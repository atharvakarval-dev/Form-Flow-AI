"""
Form Field Enrichment & Processing
Handles field purpose detection, display name generation, and form processing.
"""

import os
import re
from typing import List, Dict, Any

from ..utils.constants import FIELD_PATTERNS


# Module-level constant (avoids re-creation per call)
_EXCLUDE_KEYWORDS = frozenset(['search', 'login', 'signin', 'sign-in', 'newsletter', 'subscribe'])


def process_forms(forms_data: List[Dict]) -> List[Dict]:
    """Process and enrich extracted forms with additional metadata."""
    result = []
    
    for form in forms_data:
        # Skip forms that look like search/navigation forms
        form_id = (form.get("id") or "").lower()
        form_name = (form.get("name") or "").lower()
        form_action = (form.get("action") or "").lower()
        
        # Check if form ID/name/action contains exclude keywords
        combined = f"{form_id} {form_name} {form_action}"
        if any(kw in combined for kw in _EXCLUDE_KEYWORDS):
            print(f"⏭️ Skipping excluded form: {form_id or form_name or form_action}")
            continue
        
        # Filter out hidden fields and get visible field count
        visible_fields = [f for f in form.get("fields", []) if not f.get("hidden") and f.get("type") != "hidden"]
        
        # Skip forms with only 1-2 visible fields (likely search/nav forms)
        if len(visible_fields) < 3:
            field_names = [f.get("name", "") for f in visible_fields]
            # Unless it's specifically a contact/feedback form with few fields
            if not any(kw in str(field_names).lower() for kw in ['message', 'comment', 'feedback', 'contact']):
                print(f"⏭️ Skipping small form with {len(visible_fields)} visible field(s)")
                continue
        
        processed = {
            "formIndex": form.get("formIndex"),
            "action": form.get("action"),
            "method": form.get("method", "POST"),
            "id": form.get("id"),
            "name": form.get("name"),
            "title": form.get("title"),
            "description": form.get("description"),
            "fields": []
        }
        
        for field in form.get("fields", []):
            field_type = field.get("type", "text")
            
            # Skip hidden fields entirely
            if field.get("hidden") or field_type == "hidden":
                continue
            
            # Skip honeypot fields (common spam traps)
            field_name_lower = (field.get("name") or "").lower()
            if "fax" in field_name_lower or "honeypot" in field_name_lower:
                continue
                
            enriched = {
                **field,
                "display_name": generate_display_name(field),
                "purpose": detect_purpose(field),
                "is_checkbox": field_type in ["checkbox", "checkbox-group"],
                "is_multiple_choice": field_type in ["radio", "radio-group", "mcq"],
                "is_dropdown": field_type in ["select", "dropdown"],
            }
            processed["fields"].append(enriched)
        
        if processed["fields"]:  # Only add if has visible fields
            result.append(processed)
    
    return result


def detect_purpose(field: Dict) -> str:
    """Detect semantic purpose of a field."""
    text = f"{field.get('name', '')} {field.get('label', '')} {field.get('placeholder', '')}".lower()
    
    for purpose, keywords in FIELD_PATTERNS.items():
        if any(kw in text for kw in keywords):
            return purpose
    
    return field.get('type', 'text')


def generate_display_name(field: Dict) -> str:
    """Generate user-friendly display name."""
    # Try label first
    if field.get('label'):
        return field['label'].strip()
    
    # Try placeholder
    if field.get('placeholder'):
        return field['placeholder'].strip()
    
    # Clean up field name
    name = field.get('name', 'Field')
    # Remove common prefixes
    for prefix in ['input_', 'field_', 'form_', 'data_', 'entry.']:
        if name.lower().startswith(prefix):
            name = name[len(prefix):]
    
    # Convert to title case
    return name.replace('_', ' ').replace('-', ' ').title()


def generate_speech(fields: List[Dict]) -> Dict:
    """Generate speech data for fields."""
    try:
        from services.voice.speech import SpeechService
        service = SpeechService(api_key=os.getenv('ELEVENLABS_API_KEY'))
        return service.generate_form_speech(fields)
    except Exception as e:
        print(f"⚠️ Speech generation failed: {e}")
        return {}


def create_template(forms: List[Dict]) -> Dict[str, Any]:
    """Create a template dictionary for form filling."""
    template = {"forms": []}
    
    for form in forms:
        form_tpl = {"form_index": form.get("formIndex"), "form_name": form.get("name"), "fields": {}}
        
        for field in form.get("fields", []):
            name = field.get("name")
            if not name:
                continue
            
            ftype = field.get("type", "text")
            
            field_template = {
                "display_name": field.get("display_name"),
                "type": ftype,
                "required": field.get("required", False)
            }
            
            if ftype == "checkbox":
                field_template["value"] = False
            elif ftype == "checkbox-group":
                field_template["value"] = []
                field_template["options"] = field.get("options", [])
            elif ftype in ["radio", "mcq", "dropdown", "select"]:
                field_template["value"] = None
                field_template["options"] = field.get("options", [])
            elif ftype == "scale":
                field_template["value"] = None
                field_template["scale_min"] = field.get("scale_min")
                field_template["scale_max"] = field.get("scale_max")
            elif ftype == "grid":
                field_template["value"] = {}
                field_template["rows"] = field.get("rows", [])
                field_template["columns"] = field.get("columns", [])
            elif ftype == "file":
                field_template["value"] = None
                field_template["accept"] = field.get("accept")
                field_template["multiple"] = field.get("multiple", False)
            else:
                field_template["value"] = ""
                
            form_tpl["fields"][name] = field_template
        
        template["forms"].append(form_tpl)
    
    return template


def validate_field_value(value: Any, field: Dict) -> tuple:
    """Validate a field value. Returns (is_valid, error_message)."""
    ftype = field.get("type", "text")
    required = field.get("required", False)
    
    # Required check
    if required and not value:
        return False, f"{field.get('display_name', 'Field')} is required"
    
    if not value:
        return True, ""
    
    # Type-specific validation
    if ftype == "email" and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', str(value)):
        return False, "Invalid email format"
    
    if ftype in ["tel", "phone"] and not re.match(r'^[\d\s\-\+\(\)]+$', str(value)):
        return False, "Invalid phone format"
    
    if ftype == "url" and not re.match(r'^https?://', str(value)):
        return False, "Invalid URL format"
    
    # Options validation
    if ftype in ["radio", "dropdown", "select"]:
        options = field.get("options", [])
        valid_values = [o.get("value") or o.get("label") for o in options]
        if value not in valid_values:
            return False, f"Invalid option: {value}"
    
    return True, ""


def get_form_summary(forms: List[Dict]) -> Dict:
    """Get a summary of forms."""
    total_fields = sum(len(f.get('fields', [])) for f in forms)
    required = sum(1 for f in forms for field in f.get('fields', []) if field.get('required'))
    
    return {
        "total_forms": len(forms),
        "total_fields": total_fields,
        "required_fields": required,
        "field_types": list(set(field.get('type') for f in forms for field in f.get('fields', [])))
    }


def get_required_fields(forms: List[Dict]) -> List[Dict]:
    """Get all required fields from forms."""
    return [f for form in forms for f in form.get('fields', []) if f.get('required')]


def get_mcq_fields(forms: List[Dict]) -> List[Dict]:
    """Get all multiple choice fields from forms."""
    return [f for form in forms for f in form.get('fields', []) if f.get('type') in ['radio', 'mcq']]


def get_dropdown_fields(forms: List[Dict]) -> List[Dict]:
    """Get all dropdown fields from forms."""
    return [f for form in forms for f in form.get('fields', []) if f.get('type') in ['select', 'dropdown']]


def format_field_value(value: str, purpose: str, field_type: str = None) -> str:
    """Format a field value based on its purpose."""
    if not value:
        return value
    if purpose == 'email':
        return value.lower().replace(' ', '')
    if purpose in ['phone', 'mobile']:
        return re.sub(r'[^\d+]', '', value)
    return value.strip()


def format_email_input(text: str) -> str:
    """Format text for email fields"""
    return format_field_value(text, 'email')


def get_field_speech(field_name: str, speech_data: dict) -> bytes:
    """Get speech audio for a specific field"""
    if not speech_data:
        return None
    return speech_data.get(field_name)
