"""
Routers Module

API routers for the Form Flow AI application.
"""

from .auth import router as auth_router
from .forms import router as forms_router
from .speech import router as speech_router
from .conversation import router as conversation_router

__all__ = ["auth_router", "forms_router", "speech_router", "conversation_router"]
