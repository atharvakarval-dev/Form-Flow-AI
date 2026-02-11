"""
Vocabulary Correction Service

Handles logic for managing and applying vocabulary corrections.
Supports Async DB operations for management and Sync caching for high-performance application.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
import re
from datetime import datetime
from threading import Lock

from core.vocabulary_model import VocabularyCorrection
from utils.logging import get_logger

logger = get_logger(__name__)

class VocabularyService:
    """Service for managing vocabulary corrections."""
    
    def __init__(self):
        # Cache is a list of dicts: {'pattern': regex_obj, 'correct': str, 'heard': str}
        self._cache = []
        self._cache_lock = Lock()
        self._initialized = False
    
    async def initialize(self, db: AsyncSession):
        """Load corrections into cache on startup."""
        if self._initialized:
            return
            
        logger.info("Initializing Vocabulary Service Cache...")
        await self._refresh_cache(db)
        self._initialized = True
        logger.info(f"Vocabulary Service Cache Initialized with {len(self._cache)} rules.")

    async def _refresh_cache(self, db: AsyncSession):
        """Reload cache from DB."""
        result = await db.execute(select(VocabularyCorrection))
        corrections = result.scalars().all()
        
        new_cache = []
        for c in corrections:
            try:
                new_cache.append({
                    "heard": c.heard,
                    "correct": c.correct,
                    "pattern": re.compile(re.escape(c.heard), re.IGNORECASE)
                })
            except Exception as e:
                logger.error(f"Failed to compile regex for correction {c.heard}: {e}")
                
        with self._cache_lock:
            self._cache = new_cache

    async def get_corrections(self, db: AsyncSession, limit: int = 100) -> List[VocabularyCorrection]:
        """Get all vocabulary corrections, ordered by usage."""
        result = await db.execute(
            select(VocabularyCorrection)
            .order_by(VocabularyCorrection.usage_count.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def add_correction(self, db: AsyncSession, heard: str, correct: str, context: Optional[str] = None) -> VocabularyCorrection:
        """Add or update a vocabulary correction."""
        heard_lower = heard.lower().strip()
        
        result = await db.execute(
            select(VocabularyCorrection).filter(VocabularyCorrection.heard == heard_lower)
        )
        existing = result.scalars().first()
        
        phonetic = self._generate_phonetic(heard)
        
        if existing:
            existing.correct = correct
            existing.context = context
            existing.phonetic = phonetic
            await db.commit()
            await db.refresh(existing)
            logger.info(f"Updated correction: '{heard}' -> '{correct}'")
            correction = existing
        else:
            new_correction = VocabularyCorrection(
                heard=heard_lower,
                correct=correct,
                context=context,
                phonetic=phonetic,
                usage_count=0
            )
            db.add(new_correction)
            await db.commit()
            await db.refresh(new_correction)
            logger.info(f"Added correction: '{heard}' -> '{correct}'")
            correction = new_correction
            
        # Refresh cache
        await self._refresh_cache(db)
        return correction
    
    async def delete_correction(self, db: AsyncSession, correction_id: int) -> bool:
        """Delete a correction by ID."""
        result = await db.execute(
            select(VocabularyCorrection).filter(VocabularyCorrection.id == correction_id)
        )
        correction = result.scalars().first()
        
        if not correction:
            return False
            
        await db.delete(correction)
        await db.commit()
        
        # Refresh cache
        await self._refresh_cache(db)
        return True

    def apply_corrections(self, text: str) -> Dict[str, Any]:
        """
        Apply all corrections to the given text using IN-MEMORY CACHE.
        Synchronous method safe for high-performance loops.
        """
        if not text:
            return {"original": "", "corrected": "", "applied": []}
            
        corrected_text = text
        applied_corrections = []
        
        # Thread-safe read
        with self._cache_lock:
            current_cache = list(self._cache)
        
        for item in current_cache:
            pattern = item['pattern']
            if pattern.search(corrected_text):
                count = len(pattern.findall(corrected_text))
                corrected_text = pattern.sub(item['correct'], corrected_text)
                
                applied_corrections.append({
                    "heard": item['heard'],
                    "correct": item['correct'],
                    "count": count
                })
        
        # Note: We are NOT updating usage_count in DB here to avoid async requirements in this sync method.
        # Usage stats can be approximated or handled via a background queue if strict accuracy is needed.
        # For now, we prioritize performance and interface compatibility.
            
        return {
            "original": text,
            "corrected": corrected_text,
            "applied": applied_corrections
        }

    async def get_analytics(self, db: AsyncSession) -> Dict[str, Any]:
        """Get usage analytics."""
        total_corrections = await db.scalar(select(func.count(VocabularyCorrection.id)))
        total_usage = await db.scalar(select(func.sum(VocabularyCorrection.usage_count))) or 0
        
        result = await db.execute(
            select(VocabularyCorrection)
            .order_by(VocabularyCorrection.usage_count.desc())
            .limit(10)
        )
        most_used = result.scalars().all()
        
        return {
            "total_corrections": total_corrections,
            "total_usage": total_usage,
            "most_used": [
                {
                    "heard": c.heard,
                    "correct": c.correct,
                    "usage_count": c.usage_count
                }
                for c in most_used
            ]
        }

    def _generate_phonetic(self, text: str) -> str:
        """Generate phonetic code (simple wrapper)."""
        try:
            import phonetics
            return phonetics.metaphone(text)
        except ImportError:
            return text.lower()
        except Exception:
            return text.lower()

# Singleton instance
_vocabulary_service = VocabularyService()

def get_vocabulary_service() -> VocabularyService:
    return _vocabulary_service
