"""
Profile Router - User Behavioral Profile API

REST API endpoints for managing user behavioral profiles.
Provides privacy-compliant operations including view, delete, and opt-out.

Endpoints:
    GET /profile/me - View own profile
    DELETE /profile/me - Reset/delete profile
    POST /profile/opt-out - Disable profiling
    POST /profile/opt-in - Enable profiling
    POST /profile/generate - Manually trigger profile generation

Usage:
    All endpoints require authentication via Bearer token.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

from core import database, models
from services.ai.profile_service import get_profile_service, ProfileService
import auth
from utils.logging import get_logger
from sqlalchemy.future import select

logger = get_logger(__name__)

router = APIRouter(prefix="/profile", tags=["User Profile"])


# =============================================================================
# Pydantic Models
# =============================================================================

class ProfileResponse(BaseModel):
    """Response model for profile data."""
    user_id: int
    profile_text: str
    confidence_score: float
    confidence_level: str
    form_count: int
    version: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProfileStatusResponse(BaseModel):
    """Response model for profile status."""
    profiling_enabled: bool
    has_profile: bool
    message: str


class ProfileGenerateRequest(BaseModel):
    """Request model for manual profile generation."""
    form_data: Dict[str, Any]
    form_type: str = "General"
    form_purpose: str = "Data collection"


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str
    success: bool = True


# =============================================================================
# Helper: Get Current User
# =============================================================================

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(database.get_db)
) -> models.User:
    """
    Extract and validate current user from JWT token.
    
    Args:
        request: FastAPI request with Authorization header
        db: Database session
        
    Returns:
        User model instance
        
    Raises:
        HTTPException: If authentication fails
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header"
        )
    
    token = auth_header.split(" ")[1]
    
    try:
        payload = auth.decode_access_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        result = await db.execute(
            select(models.User).where(models.User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")


# =============================================================================
# Profile Endpoints
# =============================================================================

@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    request: Request,
    db: AsyncSession = Depends(database.get_db),
    profile_service: ProfileService = Depends(get_profile_service)
):
    """
    Get current user's behavioral profile.
    
    Returns the user's profile including:
    - Profile text (behavioral insights)
    - Confidence score
    - Number of forms analyzed
    - Version and timestamps
    
    Requires: Bearer token authentication
    """
    user = await get_current_user(request, db)
    
    # Get profile (cache-first)
    profile = await profile_service.get_profile(db, user.id)
    
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="No profile found. Complete some forms to generate your behavioral profile."
        )
    
    # Handle both dict (from cache) and model (from DB)
    if isinstance(profile, dict):
        return ProfileResponse(**profile)
    
    return ProfileResponse(
        user_id=profile.user_id,
        profile_text=profile.profile_text,
        confidence_score=profile.confidence_score,
        confidence_level=profile.confidence_level,
        form_count=profile.form_count,
        version=profile.version,
        created_at=profile.created_at.isoformat() if profile.created_at else None,
        updated_at=profile.updated_at.isoformat() if profile.updated_at else None,
    )


@router.delete("/me", response_model=MessageResponse)
async def delete_my_profile(
    request: Request,
    db: AsyncSession = Depends(database.get_db),
    profile_service: ProfileService = Depends(get_profile_service)
):
    """
    Delete current user's behavioral profile.
    
    This action:
    - Permanently deletes your profile data
    - Clears cached profile
    - Does NOT disable future profiling (use /opt-out for that)
    
    Use this for GDPR "right to be forgotten" compliance.
    
    Requires: Bearer token authentication
    """
    user = await get_current_user(request, db)
    
    deleted = await profile_service.delete_profile(db, user.id)
    
    if not deleted:
        return MessageResponse(
            message="No profile found to delete",
            success=True
        )
    
    logger.info(f"Profile deleted for user {user.id} (GDPR request)")
    
    return MessageResponse(
        message="Your behavioral profile has been deleted successfully",
        success=True
    )


@router.post("/opt-out", response_model=ProfileStatusResponse)
async def opt_out_profiling(
    request: Request,
    db: AsyncSession = Depends(database.get_db),
    profile_service: ProfileService = Depends(get_profile_service)
):
    """
    Disable behavioral profiling for current user.
    
    When disabled:
    - No new profile data will be collected
    - Existing profile remains until deleted
    - Suggestions will use pattern-based fallback
    
    Use /opt-in to re-enable profiling.
    
    Requires: Bearer token authentication
    """
    user = await get_current_user(request, db)
    
    await profile_service.set_profiling_enabled(db, user.id, enabled=False)
    
    # Check if profile exists
    profile = await profile_service.get_profile(db, user.id)
    has_profile = profile is not None
    
    logger.info(f"Profiling disabled for user {user.id}")
    
    return ProfileStatusResponse(
        profiling_enabled=False,
        has_profile=has_profile,
        message="Profiling disabled. Your existing profile data is preserved until you delete it."
    )


@router.post("/opt-in", response_model=ProfileStatusResponse)
async def opt_in_profiling(
    request: Request,
    db: AsyncSession = Depends(database.get_db),
    profile_service: ProfileService = Depends(get_profile_service)
):
    """
    Enable behavioral profiling for current user.
    
    When enabled:
    - Profile will be created/updated from form interactions
    - Personalized suggestions will be available
    
    Requires: Bearer token authentication
    """
    user = await get_current_user(request, db)
    
    await profile_service.set_profiling_enabled(db, user.id, enabled=True)
    
    # Check if profile exists
    profile = await profile_service.get_profile(db, user.id)
    has_profile = profile is not None
    
    logger.info(f"Profiling enabled for user {user.id}")
    
    return ProfileStatusResponse(
        profiling_enabled=True,
        has_profile=has_profile,
        message="Profiling enabled. Your profile will be updated as you complete forms."
    )


@router.get("/status", response_model=ProfileStatusResponse)
async def get_profile_status(
    request: Request,
    db: AsyncSession = Depends(database.get_db),
    profile_service: ProfileService = Depends(get_profile_service)
):
    """
    Get current user's profiling status.
    
    Returns:
    - Whether profiling is enabled
    - Whether a profile exists
    
    Requires: Bearer token authentication
    """
    user = await get_current_user(request, db)
    
    profile = await profile_service.get_profile(db, user.id)
    has_profile = profile is not None
    
    return ProfileStatusResponse(
        profiling_enabled=user.profiling_enabled,
        has_profile=has_profile,
        message=f"Profiling is {'enabled' if user.profiling_enabled else 'disabled'}. "
                f"{'Profile exists.' if has_profile else 'No profile yet.'}"
    )


@router.post("/generate", response_model=MessageResponse)
async def generate_profile_manually(
    data: ProfileGenerateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(database.get_db),
    profile_service: ProfileService = Depends(get_profile_service)
):
    """
    Manually trigger profile generation from form data.
    
    This is typically called automatically after form submission,
    but can be triggered manually for testing or special cases.
    
    Args:
        form_data: Dictionary of field names to values
        form_type: Type of form (e.g., "Application", "Survey")
        form_purpose: Purpose of the form
    
    Requires: Bearer token authentication
    """
    user = await get_current_user(request, db)
    
    if not user.profiling_enabled:
        return MessageResponse(
            message="Profiling is disabled for your account. Enable it first via /profile/opt-in",
            success=False
        )
    
    # Generate profile (force update regardless of triggers)
    profile = await profile_service.generate_profile(
        db=db,
        user_id=user.id,
        form_data=data.form_data,
        form_type=data.form_type,
        form_purpose=data.form_purpose,
        force=True
    )
    
    if profile:
        return MessageResponse(
            message=f"Profile generated successfully. Confidence: {profile.confidence_level if hasattr(profile, 'confidence_level') else 'Medium'}",
            success=True
        )
    
    return MessageResponse(
        message="Profile generation failed. Check if form data is sufficient.",
        success=False
    )
