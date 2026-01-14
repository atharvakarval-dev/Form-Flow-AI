"""
Snippets Router - User-defined text expansion CRUD

Provides endpoints for managing user snippets that enable
WhisperFlow-like text expansion during voice processing.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import Snippet, User
from core.schemas import SnippetCreate, SnippetUpdate, SnippetResponse
from auth import get_current_user
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/snippets", tags=["Snippets"])


@router.post("", response_model=SnippetResponse, status_code=status.HTTP_201_CREATED)
async def create_snippet(
    snippet: SnippetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new snippet for the current user."""
    # Check for duplicate trigger phrase
    existing = db.query(Snippet).filter(
        Snippet.user_id == current_user.id,
        Snippet.trigger_phrase == snippet.trigger_phrase.lower()
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Snippet with trigger '{snippet.trigger_phrase}' already exists"
        )
    
    db_snippet = Snippet(
        user_id=current_user.id,
        trigger_phrase=snippet.trigger_phrase.lower(),
        expansion_value=snippet.expansion_value,
        is_active=snippet.is_active
    )
    db.add(db_snippet)
    db.commit()
    db.refresh(db_snippet)
    
    logger.info(f"Created snippet '{snippet.trigger_phrase}' for user {current_user.id}")
    return db_snippet


@router.get("", response_model=List[SnippetResponse])
async def list_snippets(
    active_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all snippets for the current user."""
    query = db.query(Snippet).filter(Snippet.user_id == current_user.id)
    
    if active_only:
        query = query.filter(Snippet.is_active == True)
    
    return query.order_by(Snippet.created_at.desc()).all()


@router.get("/{snippet_id}", response_model=SnippetResponse)
async def get_snippet(
    snippet_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific snippet by ID."""
    snippet = db.query(Snippet).filter(
        Snippet.id == snippet_id,
        Snippet.user_id == current_user.id
    ).first()
    
    if not snippet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snippet not found")
    
    return snippet


@router.put("/{snippet_id}", response_model=SnippetResponse)
async def update_snippet(
    snippet_id: int,
    update_data: SnippetUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an existing snippet."""
    snippet = db.query(Snippet).filter(
        Snippet.id == snippet_id,
        Snippet.user_id == current_user.id
    ).first()
    
    if not snippet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snippet not found")
    
    # Check for duplicate trigger if changing
    if update_data.trigger_phrase and update_data.trigger_phrase.lower() != snippet.trigger_phrase:
        existing = db.query(Snippet).filter(
            Snippet.user_id == current_user.id,
            Snippet.trigger_phrase == update_data.trigger_phrase.lower(),
            Snippet.id != snippet_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Snippet with trigger '{update_data.trigger_phrase}' already exists"
            )
    
    # Apply updates
    update_dict = update_data.model_dump(exclude_unset=True)
    if "trigger_phrase" in update_dict:
        update_dict["trigger_phrase"] = update_dict["trigger_phrase"].lower()
    
    for field, value in update_dict.items():
        setattr(snippet, field, value)
    
    db.commit()
    db.refresh(snippet)
    
    logger.info(f"Updated snippet {snippet_id} for user {current_user.id}")
    return snippet


@router.delete("/{snippet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_snippet(
    snippet_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a snippet."""
    snippet = db.query(Snippet).filter(
        Snippet.id == snippet_id,
        Snippet.user_id == current_user.id
    ).first()
    
    if not snippet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snippet not found")
    
    db.delete(snippet)
    db.commit()
    
    logger.info(f"Deleted snippet {snippet_id} for user {current_user.id}")
    return None
