"""
Utils package init - exports all utility functions.
"""

from .constants import (
    STEALTH_SCRIPT,
    BROWSER_ARGS,
    FIELD_PATTERNS,
    CUSTOM_DROPDOWN_SELECTORS,
    DROPDOWN_OPTION_SELECTORS,
    CAPTCHA_SELECTORS,
    EXPANDABLE_SECTION_SELECTORS,
    WIZARD_INDICATORS,
    WIZARD_NEXT_BUTTON_SELECTORS,
    RICH_TEXT_EDITOR_SELECTORS,
    DATE_PICKER_SELECTORS,
    DROPZONE_SELECTORS,
    RANGE_SLIDER_SELECTORS,
    AUTOCOMPLETE_SELECTORS,
    FORM_LIKE_CONTAINER_SELECTORS,
    LABEL_SELECTORS,
    FIELD_WRAPPER_SELECTORS,
    GOOGLE_FORM_SELECTORS,
)

from .page_helpers import (
    wait_for_dom_stability,
    expand_hidden_sections,
    scroll_and_detect_lazy_fields,
    get_page_info,
)

__all__ = [
    # Constants
    'STEALTH_SCRIPT',
    'BROWSER_ARGS',
    'FIELD_PATTERNS',
    'CUSTOM_DROPDOWN_SELECTORS',
    'DROPDOWN_OPTION_SELECTORS',
    'CAPTCHA_SELECTORS',
    'EXPANDABLE_SECTION_SELECTORS',
    'WIZARD_INDICATORS',
    'WIZARD_NEXT_BUTTON_SELECTORS',
    'RICH_TEXT_EDITOR_SELECTORS',
    'DATE_PICKER_SELECTORS',
    'DROPZONE_SELECTORS',
    'RANGE_SLIDER_SELECTORS',
    'AUTOCOMPLETE_SELECTORS',
    'FORM_LIKE_CONTAINER_SELECTORS',
    'LABEL_SELECTORS',
    'FIELD_WRAPPER_SELECTORS',
    'GOOGLE_FORM_SELECTORS',
    # Page helpers
    'wait_for_dom_stability',
    'expand_hidden_sections',
    'scroll_and_detect_lazy_fields',
    'get_page_info',
]
