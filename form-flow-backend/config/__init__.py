"""
Configuration Module

Provides centralized access to application settings.
"""

from .settings import settings, get_settings, Settings

__all__ = ["settings", "get_settings", "Settings"]
