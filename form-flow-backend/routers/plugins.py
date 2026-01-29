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

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from core.database import get_db
from core.models import User
from core.plugin_schemas import (
    PluginCreate, PluginUpdate, PluginResponse, PluginSummary,
    APIKeyCreate, APIKeyResponse, APIKeyCreated,
    ErrorResponse
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

async def plugin_exception_handler(request, exc):
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
    request,  # Required for rate limiter
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
    request,  # Required for rate limiter
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
    request,  # Required for rate limiter
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
    request,
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
    request,  # Required for rate limiter
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

