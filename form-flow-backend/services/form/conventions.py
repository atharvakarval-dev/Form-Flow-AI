"""
Form Conventions and Schema Validation

Dynamically builds validation rules from scraped form metadata.
Decouples voice processing from form validation logic.
"""

from typing import Dict, List, Any, Callable, Tuple, Optional
from dataclasses import dataclass, field
import re


# === Reusable Formatters ===

def strip_whitespace(value: str) -> str:
    """Remove leading/trailing whitespace"""
    return value.strip()


def normalize_email(value: str) -> str:
    """
    Convert voice email to proper format.
    Handles: 'dot' → '.', 'at' → '@', spaces → dots in local part
    """
    email = value.strip().lower()
    
    # Voice keyword conversion
    email = email.replace(' dot ', '.')
    email = email.replace(' at ', '@')
    email = email.replace(' underscore ', '_')
    email = email.replace(' dash ', '-')
    
    # Edge cases
    email = email.replace(' dot', '.')
    email = email.replace(' at', '@')
    email = email.replace(' underscore', '_')
    
    # Add .com if missing for common domains
    if '@' in email and '.' not in email.split('@')[1]:
        if any(domain in email for domain in ['gmail', 'yahoo', 'outlook']):
            email += '.com'
    
    if '@' not in email:
        return email
    
    # Normalize local part (replace spaces with dots)
    parts = email.split('@', 1)
    local = parts[0].strip().replace(' ', '.')
    domain = parts[1].strip()
    
    # Clean up consecutive dots
    while '..' in local:
        local = local.replace('..', '.')
    local = local.strip('.')
    
    return f"{local}@{domain}"


def strengthen_password(value: str) -> str:
    """Add missing special characters and uppercase to password"""
    # Add special character if missing
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
        if ' ' in value:
            value = value.replace(' ', '@', 1)
        else:
            value = value + '@'
    
    # Add uppercase if missing - capitalize first letter
    if not re.search(r'[A-Z]', value):
        value = value[0].upper() + value[1:] if value else value
    
    return value


def title_case(value: str) -> str:
    """Convert to title case"""
    return value.strip().title()


def lowercase(value: str) -> str:
    """Convert to lowercase"""
    return value.strip().lower()


# === Reusable Validators ===

def validate_email_format(value: str) -> Tuple[bool, str]:
    """Check if email has valid format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.match(pattern, value):
        return True, ""
    return False, "Invalid email format (must be like user@domain.com)"


def validate_password_strength(value: str) -> Tuple[bool, str]:
    """Check password meets common requirements"""
    errors = []
    
    if len(value) < 8:
        errors.append("at least 8 characters")
    if not re.search(r'[A-Z]', value):
        errors.append("one uppercase letter")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
        errors.append("one special character")
    
    if errors:
        return False, f"Password must have {', '.join(errors)}"
    return True, ""


def create_pattern_validator(pattern: str) -> Callable:
    """Create a validator from a regex pattern"""
    def validator(value: str) -> Tuple[bool, str]:
        if re.match(pattern, value):
            return True, ""
        return False, f"Value must match pattern: {pattern}"
    return validator


def create_length_validator(min_len: int = None, max_len: int = None) -> Callable:
    """Create a length validator"""
    def validator(value: str) -> Tuple[bool, str]:
        # Skip invalid values (e.g., -1 from scraper)
        if min_len and min_len > 0 and len(value) < min_len:
            return False, f"Must be at least {min_len} characters"
        if max_len and max_len > 0 and len(value) > max_len:
            return False, f"Must be at most {max_len} characters"
        return True, ""
    return validator


# === Helper Detectors ===

def is_name_field(field_name: str, field_label: str = "") -> bool:
    """Detect if field is a name field"""
    name_keywords = ['name', 'firstname', 'lastname', 'middlename', 'surname', 'fullname']
    text = f"{field_name} {field_label}".lower()
    return any(keyword in text for keyword in name_keywords)


def is_email_field(field_type: str, field_name: str, field_label: str = "") -> bool:
    """Detect if field is an email field"""
    if field_type == 'email':
        return True
    text = f"{field_name} {field_label}".lower()
    return 'email' in text or 'e-mail' in text


def is_password_field(field_type: str, field_name: str, field_label: str = "") -> bool:
    """Detect if field is a password field"""
    if field_type == 'password':
        return True
    text = f"{field_name} {field_label}".lower()
    return 'password' in text or 'pwd' in text


def is_confirm_password(field_name: str, field_label: str = "") -> bool:
    """Detect if field is a confirm password field"""
    text = f"{field_name} {field_label}".lower()
    return any(keyword in text for keyword in ['confirm', 'verify', 'repeat', 'retype', 'cpassword'])


# === Schema Classes ===

@dataclass
class FieldConvention:
    """Defines validation and formatting rules for a single field"""
    name: str
    type: str  # 'text', 'email', 'password', etc.
    required: bool = False
    validators: List[Callable] = field(default_factory=list)
    formatters: List[Callable] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self, value: str) -> Tuple[bool, str]:
        """Validate value against field conventions"""
        if self.required and not value:
            return False, f"{self.name} is required"
        
        if self.validators:
            for validator in self.validators:
                valid, error = validator(value)
                if not valid:
                    return False, error
        
        return True, ""
    
    def format(self, value: str) -> str:
        """Apply formatting rules to value"""
        if self.formatters:
            for formatter in self.formatters:
                value = formatter(value)
        return value


class FormSchema:
    """Defines complete form structure and conventions"""
    
    def __init__(self, form_id: str, fields: List[FieldConvention]):
        self.form_id = form_id
        self.fields = {f.name: f for f in fields}
    
    def validate_all(self, data: Dict[str, str]) -> Tuple[bool, List[str]]:
        """Validate only fields present in user data"""
        errors = []
        
        for field_name, value in data.items():
            if field_name in self.fields:
                field_convention = self.fields[field_name]
                valid, error = field_convention.validate(value)
                if not valid:
                    errors.append(error)
        
        return len(errors) == 0, errors
    
    def format_all(self, data: Dict[str, str]) -> Dict[str, str]:
        """Format all fields according to conventions and sync dependencies"""
        formatted = {}
        
        # 1. Apply individual formatting
        for field_name, value in data.items():
            if field_name in self.fields:
                formatted[field_name] = self.fields[field_name].format(value)
            else:
                # Unknown field, pass through
                formatted[field_name] = value
        
        # 2. Synchronize Confirm Password fields
        # Find password fields
        main_password_value = None
        main_passwords = []
        confirm_passwords = []
        
        for name, value in formatted.items():
            if name in self.fields:
                conv = self.fields[name]
                # Check if it's a password type
                if is_password_field(conv.type, conv.name):
                    if is_confirm_password(conv.name):
                        confirm_passwords.append(name)
                    else:
                        main_passwords.append(name)
        
        # If we found exactly one main password, sync all confirm fields to it
        # This handles the common case: Password + Confirm Password
        if len(main_passwords) == 1 and confirm_passwords:
            main_pwd_val = formatted[main_passwords[0]]
            for conf_name in confirm_passwords:
                print(f"🔄 Syncing {conf_name} to match {main_passwords[0]}")
                formatted[conf_name] = main_pwd_val
                
        return formatted


# === Dynamic Schema Building ===


def build_field_convention(field_info: Dict[str, Any]) -> FieldConvention:
    """
    Dynamically build field convention from scraped field metadata.
    
    Args:
        field_info: Field metadata from form_parser (includes type, name, label, validation, etc.)
    
    Returns:
        FieldConvention with appropriate formatters and validators
    """
    field_type = field_info.get('type', 'text')
    field_name = field_info.get('name', '')
    field_label = field_info.get('label', '')
    validation = field_info.get('validation', {})
    
    formatters = [strip_whitespace]  # Always strip whitespace
    validators = []
    
    # Auto-detect field purpose and add formatters/validators
    
    # Email fields
    if is_email_field(field_type, field_name, field_label):
        formatters.append(normalize_email)
        validators.append(validate_email_format)
    
    # Password fields
    elif is_password_field(field_type, field_name, field_label):
        if not is_confirm_password(field_name, field_label):
            # Main password field - strengthen it
            formatters.append(strengthen_password)
            validators.append(validate_password_strength)
        # else: confirm password - no special formatting
    
    # Name fields
    elif is_name_field(field_name, field_label):
        formatters.append(title_case)
    
    # Add pattern validator if pattern exists
    if validation.get('pattern'):
        validators.append(create_pattern_validator(validation['pattern']))
    
    # Add length validator if min/max length exists
    min_len = validation.get('minLength')
    max_len = validation.get('maxLength')
    if min_len or max_len:
        validators.append(create_length_validator(
            int(min_len) if min_len else None,
            int(max_len) if max_len else None
        ))
    
    return FieldConvention(
        name=field_name,
        type=field_type,
        required=validation.get('required', False),
        formatters=formatters,
        validators=validators,
        constraints=validation
    )


def build_form_schema(form_data: Any) -> FormSchema:
    """
    Dynamically build FormSchema from scraped form data.
    
    Args:
        form_data: Form schema from form_parser (list of forms or single form dict)
    
    Returns:
        FormSchema with dynamically built field conventions
    """
    # Handle list of forms (standard output from form_parser)
    if isinstance(form_data, list):
        if not form_data:
            return FormSchema(form_id='unknown_form', fields=[])
        
        # Use first form's action as form_id
        form_id = form_data[0].get('action', 'unknown_form')
        fields = []
        
        # Build field conventions from all forms
        for form in form_data:
            for field_info in form.get('fields', []):
                if field_info.get('type') not in ['submit', 'button', 'reset', 'image', 'hidden']:
                    convention = build_field_convention(field_info)
                    fields.append(convention)
    else:
        # Handle single form dict
        form_id = form_data.get('action', 'unknown_form')
        fields = []
        
        for field_info in form_data.get('fields', []):
            if field_info.get('type') not in ['submit', 'button', 'reset', 'image', 'hidden']:
                convention = build_field_convention(field_info)
                fields.append(convention)
    
    return FormSchema(form_id=form_id, fields=fields)


# === Backwards Compatibility ===

# Schema cache to avoid rebuilding
_schema_cache: Dict[str, FormSchema] = {}


def get_form_schema(url: str, form_data: Optional[Dict[str, Any]] = None) -> Optional[FormSchema]:
    """
    Get or build form schema.
    
    Args:
        url: Form URL
        form_data: Optional scraped form data to build schema from
    
    Returns:
        FormSchema if available, None otherwise
    """
    # Check cache first
    if url in _schema_cache:
        return _schema_cache[url]
    
    # Build schema from form_data if provided
    if form_data:
        schema = build_form_schema(form_data)
        _schema_cache[url] = schema
        return schema
    
    # No schema available
    return None


def clear_schema_cache():
    """Clear cached schemas"""
    global _schema_cache
    _schema_cache = {}
