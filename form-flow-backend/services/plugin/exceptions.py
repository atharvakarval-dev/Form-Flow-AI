"""
Plugin Exceptions Module

Custom exceptions for the plugin system.
Inherits from existing FormFlowError hierarchy for consistency.

All exceptions include:
- HTTP status code
- Error message
- Optional details dict
"""

from typing import Optional, Dict, Any
from utils.exceptions import FormFlowError


class PluginError(FormFlowError):
    """Base exception for all plugin errors."""
    
    def __init__(
        self,
        message: str = "Plugin error",
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500
    ):
        super().__init__(message=message, details=details, status_code=status_code)


class PluginNotFoundError(PluginError):
    """Plugin does not exist or user lacks access."""
    
    def __init__(self, plugin_id: int, user_id: Optional[int] = None):
        super().__init__(
            message=f"Plugin not found: {plugin_id}",
            details={"plugin_id": plugin_id, "user_id": user_id},
            status_code=404
        )


class PluginInactiveError(PluginError):
    """Plugin is disabled."""
    
    def __init__(self, plugin_id: int):
        super().__init__(
            message=f"Plugin is inactive: {plugin_id}",
            details={"plugin_id": plugin_id},
            status_code=403
        )


class PluginLimitExceededError(PluginError):
    """Plugin has exceeded its configured limits."""
    
    def __init__(self, plugin_id: int, limit_type: str, current: int, maximum: int):
        super().__init__(
            message=f"Plugin limit exceeded: {limit_type}",
            details={
                "plugin_id": plugin_id,
                "limit_type": limit_type,
                "current": current,
                "maximum": maximum
            },
            status_code=429
        )


class APIKeyInvalidError(PluginError):
    """API key is invalid, expired, or revoked."""
    
    def __init__(self, reason: str = "Invalid API key"):
        super().__init__(
            message=reason,
            status_code=401
        )


class APIKeyRateLimitError(PluginError):
    """API key has exceeded rate limit."""
    
    def __init__(self, key_prefix: str, limit: int):
        super().__init__(
            message=f"Rate limit exceeded for key {key_prefix}",
            details={"key_prefix": key_prefix, "limit_per_minute": limit},
            status_code=429
        )


class DatabaseConnectionError(PluginError):
    """Failed to connect to external database."""
    
    def __init__(self, database_type: str, error: str):
        super().__init__(
            message=f"Database connection failed: {error}",
            details={"database_type": database_type},
            status_code=502
        )


class SchemaValidationError(PluginError):
    """Target database schema doesn't match plugin config."""
    
    def __init__(self, table: str, column: str, error: str):
        super().__init__(
            message=f"Schema mismatch in {table}.{column}: {error}",
            details={"table": table, "column": column},
            status_code=400
        )


class DataExtractionError(PluginError):
    """Failed to extract data from voice input."""
    
    def __init__(self, session_id: str, fields: list, error: str):
        super().__init__(
            message=f"Data extraction failed: {error}",
            details={"session_id": session_id, "fields": fields},
            status_code=500
        )


class DataValidationError(PluginError):
    """Extracted data failed validation."""
    
    def __init__(self, field: str, value: Any, rule: str):
        super().__init__(
            message=f"Validation failed for {field}: {rule}",
            details={"field": field, "value": str(value)[:100], "rule": rule},
            status_code=422
        )


class WebhookDeliveryError(PluginError):
    """Failed to deliver webhook."""
    
    def __init__(self, url: str, status_code_received: Optional[int], error: str):
        super().__init__(
            message=f"Webhook delivery failed: {error}",
            details={"url": url, "status_code_received": status_code_received},
            status_code=502
        )
