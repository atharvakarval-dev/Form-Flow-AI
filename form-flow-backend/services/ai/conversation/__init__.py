"""
Conversation Module

Handles conversation flow, session management, and response generation.
"""

from services.ai.conversation.session import ConversationSession, AgentResponse
from services.ai.conversation.prompts import SYSTEM_PROMPT, SmartContextBuilder

__all__ = [
    'ConversationSession',
    'AgentResponse', 
    'SYSTEM_PROMPT',
    'SmartContextBuilder',
]
