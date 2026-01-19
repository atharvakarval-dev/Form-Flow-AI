"""
Detectors package init.
"""

from .captcha import (
    detect_captcha,
    detect_login_required,
    detect_bot_protection,
)

from .dependencies import (
    map_conditional_fields,
    detect_chained_selects,
)

from .third_party import (
    detect_third_party_forms,
    analyze_iframe_accessibility,
    get_third_party_warnings,
    ThirdPartyFormInfo,
    ProviderAccessibility,
)

__all__ = [
    'detect_captcha',
    'detect_login_required',
    'detect_bot_protection',
    'map_conditional_fields',
    'detect_chained_selects',
    'detect_third_party_forms',
    'analyze_iframe_accessibility',
    'get_third_party_warnings',
    'ThirdPartyFormInfo',
    'ProviderAccessibility',
]
