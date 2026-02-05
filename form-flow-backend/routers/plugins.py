"""
Plugin Router Module

FastAPI endpoints for plugin management.
Features:
- Full CRUD for plugins
- API key generation and management
- Rate limiting per endpoint type
- Proper error handling with structured responses

All endpoints require authentication via JWT token.
External integration uses API keys (separate auth path).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Header
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any

from core.database import get_db
from core.models import User
from core.plugin_schemas import (
    PluginCreate, PluginUpdate, PluginResponse, PluginSummary,
    APIKeyCreate, APIKeyResponse, APIKeyCreated,
    ErrorResponse,
    # SDK Session schemas
    PluginSessionStart, PluginSessionResponse, PluginSessionInput,
    PluginSessionInputResponse, PluginSessionCompleteResponse, PluginSessionStatus
)
from services.plugin import (
    PluginService,
    PluginNotFoundError,
    APIKeyInvalidError,
)
from auth import get_current_user
from utils.rate_limit import limiter
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/plugins", tags=["Plugins"])


# =============================================================================
# Exception Handlers (registered in main.py)
# =============================================================================

async def plugin_exception_handler(request: Request, exc):
    """Handle plugin exceptions with structured response."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


# =============================================================================
# Plugin CRUD Endpoints
# =============================================================================

@router.post(
    "",
    response_model=PluginResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    }
)
@limiter.limit("10/minute")
async def create_plugin(
    request: Request,  # Required for rate limiter
    data: PluginCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new plugin.
    
    Creates plugin with tables, fields, and encrypted database credentials.
    """
    service = PluginService(db)
    plugin = await service.create_plugin(current_user.id, data)
    return plugin


@router.get(
    "",
    response_model=List[PluginSummary],
)
async def list_plugins(
    include_inactive: bool = Query(False, description="Include deactivated plugins"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all plugins for the current user.
    
    Returns lightweight summaries for efficient listing.
    """
    service = PluginService(db)
    plugins = await service.get_user_plugins(current_user.id, include_inactive)
    return [
        PluginSummary(
            id=p.id,
            name=p.name,
            database_type=p.database_type,
            is_active=p.is_active,
            field_count=p.field_count,
            created_at=p.created_at
        )
        for p in plugins
    ]


@router.get(
    "/{plugin_id}",
    response_model=PluginResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_plugin(
    plugin_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a plugin by ID.
    
    Returns full plugin with tables, fields, and API key counts.
    """
    service = PluginService(db)
    try:
        plugin = await service.get_plugin(plugin_id, current_user.id)
        return plugin
    except PluginNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.patch(
    "/{plugin_id}",
    response_model=PluginResponse,
    responses={404: {"model": ErrorResponse}}
)
async def update_plugin(
    plugin_id: int,
    data: PluginUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a plugin.
    
    Only provided fields are updated.
    """
    service = PluginService(db)
    try:
        plugin = await service.update_plugin(plugin_id, current_user.id, data)
        return plugin
    except PluginNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.delete(
    "/{plugin_id}",
    status_code=204,
    responses={404: {"model": ErrorResponse}}
)
async def delete_plugin(
    plugin_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete (deactivate) a plugin.
    
    Soft delete - plugin remains in database but is marked inactive.
    """
    service = PluginService(db)
    try:
        await service.delete_plugin(plugin_id, current_user.id)
        return None
    except PluginNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)


# =============================================================================
# API Key Endpoints
# =============================================================================

@router.post(
    "/{plugin_id}/api-keys",
    response_model=APIKeyCreated,
    status_code=201,
    responses={404: {"model": ErrorResponse}}
)
@limiter.limit("5/minute")
async def create_api_key(
    request: Request,  # Required for rate limiter
    plugin_id: int,
    data: APIKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a new API key.
    
    **IMPORTANT**: The full API key is returned only once!
    Store it securely - it cannot be retrieved again.
    """
    service = PluginService(db)
    try:
        api_key, plain_key = await service.create_api_key(plugin_id, current_user.id, data)
        return APIKeyCreated(
            id=api_key.id,
            plugin_id=api_key.plugin_id,
            key_prefix=api_key.key_prefix,
            name=api_key.name,
            rate_limit=api_key.rate_limit,
            is_active=api_key.is_active,
            last_used_at=api_key.last_used_at,
            expires_at=api_key.expires_at,
            created_at=api_key.created_at,
            api_key=plain_key
        )
    except PluginNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.get(
    "/{plugin_id}/api-keys",
    response_model=List[APIKeyResponse],
    responses={404: {"model": ErrorResponse}}
)
async def list_api_keys(
    plugin_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all API keys for a plugin.
    
    Returns key metadata only - full keys are never returned after creation.
    """
    service = PluginService(db)
    try:
        keys = await service.list_api_keys(plugin_id, current_user.id)
        return keys
    except PluginNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.delete(
    "/{plugin_id}/api-keys/{key_id}",
    status_code=204,
    responses={404: {"model": ErrorResponse}}
)
async def revoke_api_key(
    plugin_id: int,
    key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Revoke an API key.
    
    The key is immediately invalidated and cannot be used.
    """
    service = PluginService(db)
    try:
        await service.revoke_api_key(plugin_id, key_id, current_user.id)
        return None
    except (PluginNotFoundError, APIKeyInvalidError) as e:
        raise HTTPException(status_code=404, detail=e.message)


# =============================================================================
# Stats Endpoint
# =============================================================================

@router.get("/stats/summary")
async def get_plugin_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get aggregate statistics for user's plugins."""
    service = PluginService(db)
    return await service.get_plugin_stats(current_user.id)


# =============================================================================
# API Key Rotation
# =============================================================================

@router.post(
    "/{plugin_id}/api-keys/{key_id}/rotate",
    response_model=APIKeyCreated,
    responses={404: {"model": ErrorResponse}}
)
@limiter.limit("3/minute")
async def rotate_api_key(
    request: Request,  # Required for rate limiter
    plugin_id: int,
    key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Rotate an API key.
    
    The old key is immediately revoked and a new key with the 
    same configuration is generated.
    
    **IMPORTANT**: The new API key is returned only once!
    """
    service = PluginService(db)
    try:
        api_key, plain_key = await service.rotate_api_key(plugin_id, key_id, current_user.id)
        return APIKeyCreated(
            id=api_key.id,
            plugin_id=api_key.plugin_id,
            key_prefix=api_key.key_prefix,
            name=api_key.name,
            rate_limit=api_key.rate_limit,
            is_active=api_key.is_active,
            last_used_at=api_key.last_used_at,
            expires_at=api_key.expires_at,
            created_at=api_key.created_at,
            api_key=plain_key
        )
    except (PluginNotFoundError, APIKeyInvalidError) as e:
        raise HTTPException(status_code=404, detail=e.message)


# =============================================================================
# GDPR Compliance Endpoints
# =============================================================================

@router.get("/gdpr/export")
async def export_user_data(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export all user data (GDPR Article 15 - Right of access).
    
    Returns all plugin data, API keys, and audit logs for the user.
    """
    from services.plugin.security.gdpr import GDPRService
    
    # Get client IP for audit
    ip_address = request.client.host if request.client else None
    
    gdpr = GDPRService(db)
    return await gdpr.export_user_data(current_user.id, ip_address)


@router.delete(
    "/gdpr/delete-all",
    status_code=200,
    responses={200: {"description": "Deletion report"}}
)
@limiter.limit("1/hour")
async def delete_user_data(
    request: Request,  # Required for rate limiter
    confirm: bool = Query(..., description="Must be true to confirm deletion"),
    keep_audit_logs: bool = Query(True, description="Keep audit logs for compliance"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete all user data (GDPR Article 17 - Right to erasure).
    
    **IRREVERSIBLE**: This deletes all plugins, tables, fields, and API keys.
    Set confirm=true to proceed.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Set confirm=true to delete all data. This is irreversible."
        )
    
    from services.plugin.security.gdpr import GDPRService
    
    ip_address = request.client.host if request.client else None
    
    gdpr = GDPRService(db)
    return await gdpr.delete_user_data(current_user.id, ip_address, keep_audit_logs)


@router.get("/gdpr/retention-status")
async def get_retention_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get data retention status for user's data.
    
    Shows current retention settings and data counts.
    """
    from services.plugin.security.gdpr import GDPRService
    
    gdpr = GDPRService(db)
    return await gdpr.get_retention_status(current_user.id)


# =============================================================================
# SDK Session Endpoints (API Key Authentication)
# =============================================================================

async def validate_api_key_dependency(
    request: Request,
    x_api_key: str = Header(..., alias="X-API-Key"),
    x_plugin_id: str = Header(..., alias="X-Plugin-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Dependency to validate API key and plugin ID from headers.
    Returns tuple of (api_key_record, plugin).
    """
    service = PluginService(db)
    try:
        api_key, plugin = await service.validate_api_key(x_api_key)
        
        # Verify plugin ID matches
        if str(plugin.id) != x_plugin_id:
            raise HTTPException(
                status_code=403,
                detail="Plugin ID mismatch"
            )
        
        return api_key, plugin
    except APIKeyInvalidError as e:
        raise HTTPException(status_code=401, detail=e.message)


# In-memory session cache (for MVP - use Redis in production)
_plugin_sessions: Dict[str, Dict[str, Any]] = {}


@router.post(
    "/sessions",
    response_model=PluginSessionResponse,
    tags=["Plugin SDK"],
    summary="Start a data collection session"
)
@limiter.limit("30/minute")
async def start_plugin_session(
    request: Request,
    body: PluginSessionStart = None,
    auth: tuple = Depends(validate_api_key_dependency),
    db: AsyncSession = Depends(get_db)
):
    """
    Start a new voice data collection session.
    
    Requires X-API-Key and X-Plugin-ID headers.
    Returns session ID and first questions based on plugin schema.
    """
    import uuid
    from datetime import datetime
    
    api_key, plugin = auth
    
    # Build form schema from plugin tables/fields
    form_schema = []
    for table in plugin.tables:
        table_fields = []
        for field in sorted(table.fields, key=lambda f: f.display_order):
            table_fields.append({
                "name": f"{table.table_name}.{field.column_name}",
                "label": field.question_text,
                "type": field.column_type,
                "required": field.is_required,
                "group": field.question_group,
                "order": field.display_order
            })
        form_schema.append({
            "table": table.table_name,
            "fields": table_fields
        })
    
    # Flatten fields for questions
    all_fields = []
    for table_schema in form_schema:
        all_fields.extend(table_schema.get("fields", []))
    
    # Create session
    session_id = str(uuid.uuid4())
    session_data = {
        "session_id": session_id,
        "plugin_id": plugin.id,
        "form_schema": form_schema,
        "extracted_fields": {},
        "created_at": datetime.now(),
        "last_activity": datetime.now(),
        "status": "active",
        "source_url": body.source_url if body else None
    }
    
    _plugin_sessions[session_id] = session_data
    
    # Get first questions (up to 3)
    questions = all_fields[:3] if all_fields else []
    current_question = questions[0].get("label") if questions else None
    
    logger.info(f"Started plugin session {session_id} for plugin {plugin.id}")
    
    return PluginSessionResponse(
        session_id=session_id,
        plugin_id=plugin.id,
        questions=questions,
        total_fields=len(all_fields),
        current_question=current_question
    )


@router.post(
    "/sessions/{session_id}/input",
    response_model=PluginSessionInputResponse,
    tags=["Plugin SDK"],
    summary="Submit user input"
)
@limiter.limit("60/minute")
async def submit_session_input(
    request: Request,
    session_id: str,
    body: PluginSessionInput,
    auth: tuple = Depends(validate_api_key_dependency),
    db: AsyncSession = Depends(get_db)
):
    """
    Submit user voice/text input to an active session.
    
    Processes input, extracts field values, and returns next questions.
    """
    from datetime import datetime
    from services.ai.conversation_agent import ConversationAgent
    from services.ai.session_manager import get_session_manager
    
    api_key, plugin = auth
    
    # Get session
    session_data = _plugin_sessions.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    if session_data["plugin_id"] != plugin.id:
        raise HTTPException(status_code=403, detail="Session does not belong to this plugin")
    
    # Update activity
    session_data["last_activity"] = datetime.now()
    
    # Get or create conversation agent session
    session_manager = await get_session_manager()
    agent = ConversationAgent(session_manager=session_manager)
    
    # Check if we have an agent session
    agent_session = await agent.get_session(session_id)
    if not agent_session:
        # Create agent session from plugin schema
        agent_session = await agent.create_session(
            form_schema=session_data["form_schema"],
            form_url=session_data.get("source_url", ""),
            initial_data=session_data.get("extracted_fields", {}),
            client_type="sdk"
        )
        # Replace session ID to match plugin session
        agent_session.id = session_id
        await agent._save_session(agent_session)
    
    # Process input
    result = await agent.process_user_input(session_id, body.input)
    
    # Update session data
    session_data["extracted_fields"].update(result.extracted_values)
    
    # Get remaining fields
    remaining = result.remaining_fields if hasattr(result, 'remaining_fields') else []
    total_fields = sum(len(t.get("fields", [])) for t in session_data["form_schema"])
    filled_count = len(session_data["extracted_fields"])
    progress = (filled_count / total_fields * 100) if total_fields > 0 else 0
    
    # Get next question
    next_q = None
    if result.next_questions:
        next_q = result.next_questions[0].get("label") if result.next_questions else None
    
    return PluginSessionInputResponse(
        session_id=session_id,
        extracted_values=result.extracted_values,
        next_question=next_q,
        progress=progress,
        is_complete=result.is_complete,
        remaining_fields=len(remaining) if isinstance(remaining, list) else 0
    )


@router.post(
    "/sessions/{session_id}/complete",
    response_model=PluginSessionCompleteResponse,
    tags=["Plugin SDK"],
    summary="Complete session and save data"
)
@limiter.limit("10/minute")
async def complete_plugin_session(
    request: Request,
    session_id: str,
    auth: tuple = Depends(validate_api_key_dependency),
    db: AsyncSession = Depends(get_db)
):
    """
    Complete the session and save collected data to the external database.
    
    Triggers the database connector to insert records.
    """
    from services.plugin.connector import PluginConnector
    
    api_key, plugin = auth
    
    # Get session
    session_data = _plugin_sessions.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    if session_data["plugin_id"] != plugin.id:
        raise HTTPException(status_code=403, detail="Session does not belong to this plugin")
    
    # Connect and insert data
    try:
        connector = PluginConnector(plugin, db)
        records_created = await connector.insert_collected_data(
            session_data["extracted_fields"],
            session_data["form_schema"]
        )
        
        # Mark session as completed
        session_data["status"] = "completed"
        
        # Clean up session
        del _plugin_sessions[session_id]
        
        logger.info(f"Completed plugin session {session_id}, created {records_created} records")
        
        return PluginSessionCompleteResponse(
            session_id=session_id,
            plugin_id=plugin.id,
            success=True,
            records_created=records_created,
            message=f"Successfully created {records_created} record(s)"
        )
    except Exception as e:
        logger.error(f"Failed to complete session {session_id}: {e}")
        session_data["status"] = "failed"
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save data: {str(e)}"
        )


@router.get(
    "/sessions/{session_id}",
    response_model=PluginSessionStatus,
    tags=["Plugin SDK"],
    summary="Get session status"
)
async def get_plugin_session(
    session_id: str,
    auth: tuple = Depends(validate_api_key_dependency),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the current status of a data collection session.
    """
    api_key, plugin = auth
    
    # Get session
    session_data = _plugin_sessions.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    if session_data["plugin_id"] != plugin.id:
        raise HTTPException(status_code=403, detail="Session does not belong to this plugin")
    
    # Calculate progress
    total_fields = sum(len(t.get("fields", [])) for t in session_data["form_schema"])
    filled_count = len(session_data["extracted_fields"])
    progress = (filled_count / total_fields * 100) if total_fields > 0 else 0
    
    return PluginSessionStatus(
        session_id=session_id,
        plugin_id=plugin.id,
        status=session_data.get("status", "active"),
        progress=progress,
        extracted_fields=session_data["extracted_fields"],
        remaining_fields=total_fields - filled_count,
        created_at=session_data["created_at"],
        last_activity=session_data["last_activity"]
    )
