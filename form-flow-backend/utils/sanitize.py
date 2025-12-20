"""
Input Sanitization Utilities

Provides validation and sanitization for user inputs, especially URLs.
Helps prevent SSRF attacks and validates input formats.

Usage:
    from utils.sanitize import validate_form_url, sanitize_string
    
    clean_url = validate_form_url(user_input)
"""

import re
from urllib.parse import urlparse
from typing import Optional

from utils.logging import get_logger
from utils.exceptions import FormValidationError

logger = get_logger(__name__)


# =============================================================================
# URL Validation
# =============================================================================

# Allowed URL schemes
ALLOWED_SCHEMES = {"http", "https"}

# Blocked hosts (prevent SSRF to internal services)
BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "169.254.169.254",  # AWS metadata
    "metadata.google.internal",  # GCP metadata
}

# Blocked host patterns
BLOCKED_PATTERNS = [
    r"^10\.",           # Private IP range
    r"^172\.(1[6-9]|2[0-9]|3[01])\.",  # Private IP range
    r"^192\.168\.",     # Private IP range
]


def validate_form_url(url: str) -> str:
    """
    Validate and sanitize a form URL.
    
    Ensures the URL is safe to scrape:
    - Uses HTTP or HTTPS scheme
    - Not pointing to internal/private addresses
    - Properly formatted
    
    Args:
        url: URL to validate
        
    Returns:
        str: Validated URL
        
    Raises:
        FormValidationError: If URL is invalid or unsafe
    """
    if not url or not isinstance(url, str):
        raise FormValidationError("URL is required", field="url")
    
    url = url.strip()
    
    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise FormValidationError(f"Invalid URL format: {e}", field="url")
    
    # Check scheme
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise FormValidationError(
            f"Invalid URL scheme: {parsed.scheme}. Use http or https.",
            field="url"
        )
    
    # Check for host
    if not parsed.netloc:
        raise FormValidationError("URL must include a host", field="url")
    
    # Extract hostname (without port)
    hostname = parsed.hostname or ""
    hostname_lower = hostname.lower()
    
    # Check blocked hosts
    if hostname_lower in BLOCKED_HOSTS:
        logger.warning(f"Blocked URL attempt: {url}")
        raise FormValidationError(
            "This URL is not allowed",
            field="url"
        )
    
    # Check blocked patterns
    for pattern in BLOCKED_PATTERNS:
        if re.match(pattern, hostname_lower):
            logger.warning(f"Blocked private IP URL: {url}")
            raise FormValidationError(
                "Private/internal URLs are not allowed",
                field="url"
            )
    
    logger.debug(f"URL validated: {url[:50]}...")
    return url


def is_google_form_url(url: str) -> bool:
    """
    Check if URL is a Google Form.
    
    Args:
        url: URL to check
        
    Returns:
        bool: True if it's a Google Form URL
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    
    return (
        "docs.google.com" in hostname and "/forms/" in parsed.path
    ) or (
        "forms.gle" in hostname
    )


# =============================================================================
# String Sanitization
# =============================================================================

def sanitize_string(
    value: str,
    max_length: int = 1000,
    allow_html: bool = False
) -> str:
    """
    Sanitize a string input.
    
    - Strips whitespace
    - Limits length
    - Optionally strips HTML tags
    
    Args:
        value: String to sanitize
        max_length: Maximum allowed length
        allow_html: Whether to allow HTML tags
        
    Returns:
        str: Sanitized string
    """
    if not value:
        return ""
    
    # Strip whitespace
    value = value.strip()
    
    # Limit length
    if len(value) > max_length:
        value = value[:max_length]
    
    # Strip HTML if not allowed
    if not allow_html:
        value = re.sub(r'<[^>]+>', '', value)
    
    return value


def sanitize_field_name(name: str) -> str:
    """
    Sanitize a form field name.
    
    Removes special characters that could cause issues.
    
    Args:
        name: Field name to sanitize
        
    Returns:
        str: Sanitized field name
    """
    if not name:
        return ""
    
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>"\']', '', name)
    
    # Limit length
    return sanitized[:200]
