"""
Conversation Router

API endpoints for the conversational form-filling agent.
Provides session management and multi-turn conversation handling.

Endpoints:
    POST /conversation/session - Create new conversation session
    POST /conversation/message - Process user message
    GET /conversation/session/{id} - Get session status
    DELETE /conversation/session/{id} - End session
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, List, Any, Optional

from services.ai.conversation_agent import ConversationAgent, AgentResponse
from services.ai.session_manager import get_session_manager, SessionManager
from utils.logging import get_logger
from utils.rate_limit import limiter

logger = get_logger(__name__)

router = APIRouter(prefix="/conversation", tags=["Conversation Agent"])


# =============================================================================
# Pydantic Models
# =============================================================================

class CreateSessionRequest(BaseModel):
    """Request to create a new conversation session."""
    form_schema: List[Dict[str, Any]]
    form_url: str = ""
    initial_data: Optional[Dict[str, str]] = None
    client_type: Optional[str] = "extension"  # Defaults to 'extension' for backward compat


class CreateSessionResponse(BaseModel):
    """Response after creating a session."""
    session_id: str
    greeting: str
    next_questions: List[Dict[str, Any]]
    remaining_fields_count: int


class MessageRequest(BaseModel):
    """Request to process a user message."""
    session_id: str
    message: str


class MessageResponse(BaseModel):
    """Response after processing a message."""
    response: str
    extracted_values: Dict[str, str]
    confidence_scores: Dict[str, float]
    needs_confirmation: List[str]
    remaining_fields_count: int
    is_complete: bool
    next_questions: List[Dict[str, Any]]


class ConfirmValueRequest(BaseModel):
    """Request to confirm a low-confidence value."""
    session_id: str
    field_name: str
    confirmed_value: str


class SessionSummary(BaseModel):
    """Summary of a conversation session."""
    session_id: str
    form_url: str
    extracted_fields: Dict[str, str]
    remaining_count: int
    is_complete: bool
    conversation_turns: int


# =============================================================================
# Dependency Injection
# =============================================================================

# Singleton agent instance
_conversation_agent: Optional[ConversationAgent] = None


async def get_conversation_agent() -> ConversationAgent:
    """Get or create the conversation agent singleton with SessionManager."""
    global _conversation_agent
    if _conversation_agent is None:
        session_manager = await get_session_manager()
        _conversation_agent = ConversationAgent(session_manager=session_manager)
    return _conversation_agent


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/session",
    response_model=CreateSessionResponse,
    summary="Create conversation session",
    description="Start a new conversation session for form filling"
)
async def create_session(
    request: CreateSessionRequest,
    background_tasks: BackgroundTasks
):
    """
    Create a new conversation session for a form.
    
    Returns the session ID and an initial greeting with the first
    batch of questions.
    """
    try:
        agent = await get_conversation_agent()
        
        # Create session (async - persisted to Redis)
        session = await agent.create_session(
            form_schema=request.form_schema,
            form_url=request.form_url,
            initial_data=request.initial_data,
            client_type=request.client_type or "extension"
        )
        
        # Generate initial greeting
        greeting_response = await agent.generate_initial_greeting(session)
        
        # Schedule cleanup of expired sessions
        background_tasks.add_task(agent.cleanup_expired_sessions)
        
        logger.info(f"Created session {session.id} for {request.form_url}")
        
        return CreateSessionResponse(
            session_id=session.id,
            greeting=greeting_response.message,
            next_questions=greeting_response.next_questions,
            remaining_fields_count=len(greeting_response.remaining_fields)
        )
        
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create conversation session: {str(e)}"
        )


@router.post(
    "/message",
    response_model=MessageResponse,
    summary="Process user message",
    description="Send a user message and receive extracted values + next questions"
)
async def process_message(
    request: MessageRequest
):
    """
    Process a user message in an active session.
    
    Extracts field values from the user's speech and generates
    the next batch of questions.
    """
    try:
        agent = await get_conversation_agent()
        result = await agent.process_user_input(
            session_id=request.session_id,
            user_input=request.message
        )
        
        return MessageResponse(
            response=result.message,
            extracted_values=result.extracted_values,
            confidence_scores=result.confidence_scores,
            needs_confirmation=result.needs_confirmation,
            remaining_fields_count=len(result.remaining_fields),
            is_complete=result.is_complete,
            next_questions=result.next_questions
        )
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Session not found or expired")
        logger.error(f"Failed to process message: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process message: {str(e)}"
        )


@router.post(
    "/confirm",
    summary="Confirm a value",
    description="Confirm a low-confidence extracted value"
)
async def confirm_value(
    request: ConfirmValueRequest
):
    """Confirm a value that had low confidence."""
    try:
        agent = await get_conversation_agent()
        await agent.confirm_value(
            session_id=request.session_id,
            field_name=request.field_name,
            confirmed_value=request.confirmed_value
        )
        
        return {"success": True, "message": f"Confirmed {request.field_name}"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ContextUpdateRequest(BaseModel):
    """Request to update context (current field focus) without user input."""
    session_id: str
    current_field: str
    field_label: Optional[str] = None


@router.post(
    "/context",
    summary="Update conversation context",
    description="Update the agent's focus on the current field (e.g. after manual skip)"
)
async def update_context(
    request: ContextUpdateRequest
):
    """
    Update context (current field).
    This tells the agent which field the user is currently looking at.
    """
    try:
        agent = await get_conversation_agent()
        
        # Use agent to get proper session object (not raw dict)
        session = await agent.get_session(request.session_id)
        
        if not session:
            logger.warning(f"Session {request.session_id} not found for context update")
            return {"success": False}
        
        # Update context window using the new API
        session.set_active_field(request.current_field)
        
        # Update timestamp
        session.update_activity()
        
        # Save session through agent to ensure cache consistency
        await agent._save_session(session)
        
        logger.info(f"Context updated: Session {request.session_id} -> Field {request.current_field}")
            
        return {"success": True, "field": request.current_field}
        
    except Exception as e:
        logger.error(f"Context update failed: {e}")
        # Don't fail hard, this is a sync signal
        return {"success": False, "error": str(e)}


@router.get(
    "/session/{session_id}",
    response_model=SessionSummary,
    summary="Get session status",
    description="Get the current state of a conversation session"
)
async def get_session_status(
    session_id: str
):
    """Get the current status of a conversation session."""
    agent = await get_conversation_agent()
    summary = await agent.get_session_summary(session_id)
    
    if "error" in summary:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    return SessionSummary(
        session_id=summary["session_id"],
        form_url=summary["form_url"],
        extracted_fields=summary["extracted_fields"],
        remaining_count=summary["remaining_count"],
        is_complete=summary["is_complete"],
        conversation_turns=summary["conversation_turns"]
    )


@router.delete(
    "/session/{session_id}",
    summary="End session",
    description="End a conversation session and get final data"
)
async def end_session(
    session_id: str
):
    """End a conversation session and return final extracted data."""
    agent = await get_conversation_agent()
    summary = await agent.get_session_summary(session_id)
    
    if "error" in summary:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get final data before deleting
    session = await agent.get_session(session_id)
    final_data = session.extracted_fields.copy() if session else {}
    
    # Remove session from storage
    await agent.delete_session(session_id)
    
    logger.info(f"Ended session {session_id} with {len(final_data)} fields")
    
    return {
        "success": True,
        "session_id": session_id,
        "final_data": final_data,
        "fields_collected": len(final_data)
    }
