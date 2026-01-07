from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

from services.ai.rag_service import get_rag_service, RagService
from services.ai.profile_suggestions import (
    get_intelligent_suggestions,
    IntelligentSuggestion,
    SuggestionTier,
)
from core import database
from sqlalchemy.ext.asyncio import AsyncSession
import auth

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Suggestions"])


# =============================================================================
# Pydantic Models
# =============================================================================

class SuggestionRequest(BaseModel):
    user_id: Optional[str] = None
    field_name: str
    field_label: Optional[str] = None
    field_type: Optional[str] = "text"
    current_value: Optional[str] = None
    n_results: int = 5


class SuggestionResponse(BaseModel):
    suggestions: List[str]
    field_name: str


class IntelligentSuggestionRequest(BaseModel):
    """Request for profile-based intelligent suggestions."""
    field_name: str
    field_label: Optional[str] = None
    field_type: Optional[str] = "text"
    form_purpose: Optional[str] = "General"
    previous_answers: Optional[Dict[str, str]] = None


class IntelligentSuggestionItem(BaseModel):
    """Single intelligent suggestion with behavioral context."""
    value: str
    confidence: float
    tier: str
    reasoning: str
    behavioral_match: str
    alternative_framing: Optional[str] = None


class IntelligentSuggestionResponse(BaseModel):
    """Response containing profile-aware intelligent suggestions."""
    suggestions: List[IntelligentSuggestionItem]
    field_name: str
    tier_used: str
    profile_confidence: Optional[float] = None


# =============================================================================
# Original Suggestions Endpoint (RAG-based)
# =============================================================================

@router.post("/suggestions", response_model=SuggestionResponse)
async def get_suggestions(
    data: SuggestionRequest,
    request: Request,
    db: AsyncSession = Depends(database.get_db),
    rag_service: RagService = Depends(get_rag_service),
):
    """
    Get real-time suggestions for a form field based on user history.
    
    Uses RAG database for pattern-based suggestions.
    For intelligent profile-based suggestions, use /smart-suggestions instead.
    """
    try:
        user_id = data.user_id
        if not user_id:
            try:
                token = request.headers.get("Authorization", "").replace("Bearer ", "")
                user = await auth.get_current_user(token, db)
                user_id = str(user.id)
            except:
                user_id = "anonymous"
        
        field_pattern = _infer_field_pattern(
            data.field_name, 
            data.field_label or "",
            data.field_type
        )
        
        suggestions = rag_service.get_suggested_values(
            user_id=user_id,
            field_pattern=field_pattern,
            n_results=data.n_results,
            partial_value=data.current_value if data.current_value and len(data.current_value) > 0 else None,
        )
        
        return SuggestionResponse(
            suggestions=suggestions,
            field_name=data.field_name
        )
        
    except Exception as e:
        logger.error(f"Error fetching suggestions: {e}")
        return SuggestionResponse(suggestions=[], field_name=data.field_name)


# =============================================================================
# Intelligent Profile-Based Suggestions (ChatGPT/Claude Level)
# =============================================================================

@router.post("/smart-suggestions", response_model=IntelligentSuggestionResponse)
async def get_smart_suggestions(
    data: IntelligentSuggestionRequest,
    request: Request,
    db: AsyncSession = Depends(database.get_db),
):
    """
    🧠 Get intelligent suggestions powered by user's behavioral profile.
    
    This endpoint uses a 3-tier system:
    - **Tier 1 (Profile-Based)**: Uses full behavioral profile with LLM
    - **Tier 2 (Blended)**: Combines patterns with light profile context
    - **Tier 3 (Pattern-Only)**: Fast fallback for new users
    
    Features:
    - Decision-style awareness
    - Communication preference matching
    - Personalized reasoning for each suggestion
    - Automatic tier selection based on profile confidence
    
    Requires: Bearer token authentication (for profile lookup)
    """
    try:
        # Get user from auth
        user_id = None
        profile_confidence = None
        
        try:
            token = request.headers.get("Authorization", "").replace("Bearer ", "")
            if token:
                user = await auth.get_current_user(token, db)
                user_id = user.id
                
                # Get profile confidence if available
                if hasattr(user, 'behavioral_profile') and user.behavioral_profile:
                    profile_confidence = user.behavioral_profile.confidence_score
        except Exception as e:
            logger.debug(f"Auth lookup failed: {e}")
        
        # Build field context
        field_context = {
            "name": data.field_name,
            "label": data.field_label or data.field_name,
            "type": data.field_type or "text",
        }
        
        form_context = {
            "purpose": data.form_purpose or "General",
        }
        
        # Get intelligent suggestions
        if user_id:
            suggestions = await get_intelligent_suggestions(
                user_id=user_id,
                field_context=field_context,
                form_context=form_context,
                previous_answers=data.previous_answers or {},
                db=db
            )
        else:
            # Anonymous user - use pattern-only tier
            from services.ai.profile_suggestions import get_profile_suggestion_engine
            engine = get_profile_suggestion_engine()
            suggestions = engine._tier3_pattern_only(field_context, data.previous_answers or {})
        
        # Determine tier used
        tier_used = suggestions[0].tier.value if suggestions else "pattern_only"
        
        return IntelligentSuggestionResponse(
            suggestions=[
                IntelligentSuggestionItem(
                    value=s.value,
                    confidence=s.confidence,
                    tier=s.tier.value,
                    reasoning=s.reasoning,
                    behavioral_match=s.behavioral_match,
                    alternative_framing=s.alternative_framing,
                )
                for s in suggestions
            ],
            field_name=data.field_name,
            tier_used=tier_used,
            profile_confidence=profile_confidence,
        )
        
    except Exception as e:
        logger.error(f"Smart suggestions failed: {e}")
        # Return empty but don't crash
        return IntelligentSuggestionResponse(
            suggestions=[],
            field_name=data.field_name,
            tier_used="error",
            profile_confidence=None,
        )


# =============================================================================
# Helper Functions
# =============================================================================

def _infer_field_pattern(field_name: str, field_label: str, field_type: str) -> str:
    """
    Infer the field pattern/category for RAG lookup.
    """
    combined = (field_name + " " + field_label).lower()
    
    if "email" in combined or field_type == "email":
        return "email"
    elif any(kw in combined for kw in ["phone", "mobile", "tel", "contact"]):
        return "phone"
    elif any(kw in combined for kw in ["first", "fname"]) and "name" in combined:
        return "first_name"
    elif any(kw in combined for kw in ["last", "lname", "surname"]) and "name" in combined:
        return "last_name"
    elif "name" in combined and "company" not in combined:
        return "name"
    elif "company" in combined or "organization" in combined:
        return "company"
    elif "address" in combined or "street" in combined:
        return "address"
    elif "city" in combined:
        return "city"
    elif "state" in combined or "province" in combined:
        return "state"
    elif any(kw in combined for kw in ["zip", "postal", "pincode"]):
        return "zipcode"
    elif "country" in combined:
        return "country"
    elif any(kw in combined for kw in ["job", "title", "position", "role"]):
        return "job_title"
    elif "linkedin" in combined:
        return "linkedin"
    elif "website" in combined or "portfolio" in combined:
        return "website"
    else:
        return field_name.lower()
