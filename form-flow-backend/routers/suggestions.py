from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, List
import logging

from services.ai.rag_service import get_rag_service, RagService
from core import database
from sqlalchemy.ext.asyncio import AsyncSession
import auth

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Suggestions"])


# --- Pydantic Models ---
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


# --- Endpoints ---
@router.post("/suggestions", response_model=SuggestionResponse)
async def get_suggestions(
    data: SuggestionRequest,
    request: Request,
    db: AsyncSession = Depends(database.get_db),
    rag_service: RagService = Depends(get_rag_service),
):
    """
    Get real-time suggestions for a form field based on user history.
    
    Features:
    - Pulls from RAG database (user's previous responses)
    - Supports partial matching (autocomplete)
    - Field-type aware suggestions
    
    Args:
        data: Suggestion request with field info and optional partial value
        
    Returns:
        List of suggested values
    """
    try:
        # Get user_id from request if not provided
        user_id = data.user_id
        if not user_id:
            # Try to get from JWT token
            try:
                token = request.headers.get("Authorization", "").replace("Bearer ", "")
                user = await auth.get_current_user(token, db)
                user_id = str(user.id)
            except:
                # Use anonymous user ID from session or generate one
                user_id = "anonymous"
        
        # Infer field pattern from field name/label/type
        field_pattern = _infer_field_pattern(
            data.field_name, 
            data.field_label or "",
            data.field_type
        )
        
        # Get suggestions from RAG
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
        # Return empty suggestions on error (don't break the form)
        return SuggestionResponse(
            suggestions=[],
            field_name=data.field_name
        )


def _infer_field_pattern(field_name: str, field_label: str, field_type: str) -> str:
    """
    Infer the field pattern/category for RAG lookup.
    
    Maps field name/label to a semantic category (e.g., 'email', 'name', 'address').
    """
    combined = (field_name + " " + field_label).lower()
    
    # Pattern matching
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
        # Fallback: use field name as pattern
        return field_name.lower()
