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

__all__ = [
    'detect_captcha',
    'detect_login_required',
    'detect_bot_protection',
    'map_conditional_fields',
    'detect_chained_selects',
]
