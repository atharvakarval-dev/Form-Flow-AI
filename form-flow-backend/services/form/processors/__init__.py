"""
Processors package init.
"""

from .enrichment import (
    process_forms,
    detect_purpose,
    generate_display_name,
    generate_speech,
    create_template,
    validate_field_value,
    get_form_summary,
    get_required_fields,
    get_mcq_fields,
    get_dropdown_fields,
    format_field_value,
    format_email_input,
    get_field_speech,
)

from .conditional_handler import (
    detect_conditional_triggers,
    trigger_cascade_fields,
    get_suggested_fill_order,
    TriggerStrategy,
    ConditionalFieldResult,
)

__all__ = [
    'process_forms',
    'detect_purpose',
    'generate_display_name',
    'generate_speech',
    'create_template',
    'validate_field_value',
    'get_form_summary',
    'get_required_fields',
    'get_mcq_fields',
    'get_dropdown_fields',
    'format_field_value',
    'format_email_input',
    'get_field_speech',
    # Conditional field handling
    'detect_conditional_triggers',
    'trigger_cascade_fields',
    'get_suggested_fill_order',
    'TriggerStrategy',
    'ConditionalFieldResult',
]

