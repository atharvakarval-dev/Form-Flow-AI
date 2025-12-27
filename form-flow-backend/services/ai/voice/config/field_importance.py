"""
Field Importance Configuration

Field importance mappings for confidence calibration.
"""

from enum import Enum


class FieldImportance(Enum):
    """Importance levels for field accuracy."""
    CRITICAL = "critical"  # Email, phone - MUST be correct
    HIGH = "high"          # Name - important but minor typos ok
    MEDIUM = "medium"      # Company - can be corrected later
    LOW = "low"            # Notes, comments - very flexible


# Field importance by name pattern
FIELD_IMPORTANCE_MAP = {
    'email': FieldImportance.CRITICAL,
    'phone': FieldImportance.CRITICAL,
    'tel': FieldImportance.CRITICAL,
    'mobile': FieldImportance.CRITICAL,
    'name': FieldImportance.HIGH,
    'first_name': FieldImportance.HIGH,
    'last_name': FieldImportance.HIGH,
    'full_name': FieldImportance.HIGH,
    'company': FieldImportance.MEDIUM,
    'organization': FieldImportance.MEDIUM,
    'title': FieldImportance.MEDIUM,
    'message': FieldImportance.LOW,
    'notes': FieldImportance.LOW,
    'comments': FieldImportance.LOW,
}

# Base confidence thresholds by importance
BASE_THRESHOLDS = {
    FieldImportance.CRITICAL: 0.90,
    FieldImportance.HIGH: 0.80,
    FieldImportance.MEDIUM: 0.65,
    FieldImportance.LOW: 0.50,
}

# Fields that are difficult for voice input
DIFFICULT_VOICE_FIELDS = {
    'email',
    'url',
    'password',
    'website',
    'address',
}


def get_field_importance(field_name: str, field_type: str) -> FieldImportance:
    """
    Determine importance level for a field.
    
    Args:
        field_name: Name of the field
        field_type: Type of the field
        
    Returns:
        FieldImportance level
    """
    name_lower = field_name.lower()
    
    # Check direct mapping
    for key, importance in FIELD_IMPORTANCE_MAP.items():
        if key in name_lower:
            return importance
    
    # Check by type
    if field_type in ['email', 'tel']:
        return FieldImportance.CRITICAL
    elif field_type == 'textarea':
        return FieldImportance.LOW
    
    return FieldImportance.MEDIUM


def get_threshold(importance: FieldImportance) -> float:
    """Get base threshold for importance level."""
    return BASE_THRESHOLDS.get(importance, 0.75)


def is_difficult_voice_field(field_name: str, field_type: str) -> bool:
    """Check if field is difficult for voice input."""
    name_lower = field_name.lower()
    return (
        field_type in DIFFICULT_VOICE_FIELDS or
        any(df in name_lower for df in DIFFICULT_VOICE_FIELDS)
    )
