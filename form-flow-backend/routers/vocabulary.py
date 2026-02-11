"""
Vocabulary Correction Router

Vocabulary correction endpoints using VocabularyService.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime
from sqlalchemy.orm import Session

from core.database import get_db
from services.voice.vocabulary import get_vocabulary_service

router = APIRouter(tags=["Vocabulary"])
vocab_service = get_vocabulary_service()


class VocabularyCorrectionRequest(BaseModel):
    heard: str = Field(..., description="What Whisper/STT heard")
    correct: str = Field(..., description="What it should be")
    context: Optional[str] = Field(None, description="Context (field name, form type)")


class CorrectionResponse(BaseModel):
    id: int
    heard: str
    correct: str
    context: Optional[str]
    usage_count: int
    created_at: datetime
    last_used: Optional[datetime]
    phonetic: Optional[str]


@router.post("/vocabulary/correction", response_model=CorrectionResponse)
async def add_correction(correction: VocabularyCorrectionRequest, db: Session = Depends(get_db)):
    """Add a new vocabulary correction rule"""
    return await vocab_service.add_correction(
        db, 
        correction.heard, 
        correction.correct, 
        correction.context
    )


@router.get("/vocabulary/corrections", response_model=List[CorrectionResponse])
async def get_corrections(db: Session = Depends(get_db)):
    """Get all vocabulary corrections"""
    return await vocab_service.get_corrections(db)


@router.post("/vocabulary/apply")
async def apply_corrections(text: str, db: Session = Depends(get_db)):
    """Apply all corrections to text"""
    # Ensure cache is loaded (lazy load check)
    if not vocab_service._initialized:
        await vocab_service.initialize(db)

    result = vocab_service.apply_corrections(text)
    return {
        "original": result["original"],
        "corrected": result["corrected"],
        "corrections_applied": len(result["applied"]),
        "details": result["applied"]
    }


@router.delete("/vocabulary/correction/{correction_id}")
async def delete_correction(correction_id: int, db: Session = Depends(get_db)):
    """Delete a vocabulary correction"""
    success = await vocab_service.delete_correction(db, correction_id)
    if not success:
        raise HTTPException(status_code=404, detail="Correction not found")
    
    return {"success": True, "message": "Correction deleted"}


@router.get("/vocabulary/analytics")
async def get_analytics(db: Session = Depends(get_db)):
    """Get vocabulary correction analytics"""
    return await vocab_service.get_analytics(db)

