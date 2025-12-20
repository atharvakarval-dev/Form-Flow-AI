"""
Extractors package init.
"""

from .special_fields import (
    extract_rich_text_editors,
    extract_dropzones,
    extract_range_sliders,
    extract_autocomplete_fields,
    extract_custom_date_pickers,
)

from .wizard import (
    detect_wizard_form,
    get_current_step_info,
    click_next_button,
    click_previous_button,
    navigate_wizard_and_extract,
)

from .standard import (
    extract_standard_forms,
    STANDARD_FORMS_JS,
)

from .google_forms import (
    wait_for_google_form,
    extract_google_forms,
    GOOGLE_FORMS_JS,
)

from .alternative import (
    extract_from_shadow_dom,
    extract_formless_containers,
    extract_custom_dropdown_options,
    extract_all_frames,
    extract_with_beautifulsoup,
)

__all__ = [
    # Special fields
    'extract_rich_text_editors',
    'extract_dropzones',
    'extract_range_sliders',
    'extract_autocomplete_fields',
    'extract_custom_date_pickers',
    # Wizard
    'detect_wizard_form',
    'get_current_step_info',
    'click_next_button',
    'click_previous_button',
    'navigate_wizard_and_extract',
    # Standard
    'extract_standard_forms',
    'STANDARD_FORMS_JS',
    # Google Forms
    'wait_for_google_form',
    'extract_google_forms',
    'GOOGLE_FORMS_JS',
    # Alternative
    'extract_from_shadow_dom',
    'extract_formless_containers',
    'extract_custom_dropdown_options',
    'extract_all_frames',
    'extract_with_beautifulsoup',
]

