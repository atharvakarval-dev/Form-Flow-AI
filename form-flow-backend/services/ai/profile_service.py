"""
Profile Service - Behavioral Profile Generation & Management

Production-ready service for generating and managing user behavioral profiles
using LLM analysis of form interactions.

Features:
    - Async profile generation with Gemini
    - Smart update triggers (80%+ completion, every 3 forms, 30+ days)
    - 500-word limit enforcement
    - Redis caching with in-memory fallback
    - Privacy-compliant operations

Usage:
    from services.ai.profile_service import get_profile_service
    
    service = get_profile_service()
    await service.generate_profile(user_id, form_data)
"""

import json
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from core.models import User, UserProfile
from config.settings import settings
from utils.logging import get_logger
from utils.cache import get_cached, set_cached, delete_cached

from .prompts.profile_prompts import (
    build_create_prompt,
    build_update_prompt,
    build_condense_prompt,
)

logger = get_logger(__name__)


# =============================================================================
# Configuration Constants
# =============================================================================

# Profile Update Trigger Thresholds
MIN_COMPLETION_RATE = 0.8  # 80% form completion required
MIN_QUESTIONS_FOR_PROFILE = 5  # Minimum questions needed
UPDATE_FORM_INTERVAL = 3  # Update profile every N forms
UPDATE_DAYS_INTERVAL = 30  # Update if not updated in N days

# LLM Configuration
PROFILE_MODEL = "gemini-1.5-pro"  # Deeper analysis for profiles
PROFILE_TEMPERATURE = 0.3  # Consistent outputs
MAX_PROFILE_WORDS = 500

# Cache Configuration
PROFILE_CACHE_TTL = 3600  # 1 hour
PROFILE_READY_TTL = 86400  # 24 hours


# =============================================================================
# Profile Service
# =============================================================================

class ProfileService:
    """
    Service for managing user behavioral profiles.
    
    Handles profile generation, updates, caching, and privacy controls.
    Uses Gemini LLM for behavioral analysis.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize profile service.
        
        Args:
            api_key: Google API key. Falls back to GOOGLE_API_KEY env var.
        """
        self.api_key = api_key or settings.GOOGLE_API_KEY
        self._llm = None
        
        if self.api_key:
            logger.info("ProfileService initialized with Gemini API")
        else:
            logger.warning("ProfileService: No API key - profile generation disabled")
    
    @property
    def llm(self) -> Optional[ChatGoogleGenerativeAI]:
        """Lazy-load LLM instance."""
        if self._llm is None and self.api_key:
            self._llm = ChatGoogleGenerativeAI(
                model=PROFILE_MODEL,
                google_api_key=self.api_key,
                temperature=PROFILE_TEMPERATURE,
                convert_system_message_to_human=True
            )
        return self._llm
    
    # -------------------------------------------------------------------------
    # Smart Trigger Logic
    # -------------------------------------------------------------------------
    
    def should_update_profile(
        self,
        form_data: Dict[str, Any],
        user_profile: Optional[UserProfile],
        total_questions: int = 0
    ) -> bool:
        """
        Determine if profile should be updated based on smart triggers.
        
        Triggers:
            1. New user (no profile exists)
            2. Form completion rate >= 80%
            3. Minimum 5 questions answered
            4. Every 3 forms for existing users
            5. More than 30 days since last update
        
        Args:
            form_data: Completed form responses
            user_profile: Existing profile (None for new users)
            total_questions: Total questions in the form
            
        Returns:
            True if profile should be updated
        """
        # Count answered questions
        answered = sum(1 for v in form_data.values() if v and str(v).strip())
        
        # Calculate completion rate
        completion_rate = answered / total_questions if total_questions > 0 else 0
        
        # Rule 1: Too few questions answered
        if answered < MIN_QUESTIONS_FOR_PROFILE:
            logger.debug(f"Profile update skipped: only {answered} questions answered")
            return False
        
        # Rule 2: Poor completion rate
        if completion_rate < MIN_COMPLETION_RATE:
            logger.debug(f"Profile update skipped: completion rate {completion_rate:.0%}")
            return False
        
        # Rule 3: New user - always create profile
        if user_profile is None:
            logger.info("Profile update triggered: new user")
            return True
        
        # Rule 4: Update every N forms
        if user_profile.form_count % UPDATE_FORM_INTERVAL == 0:
            logger.info(f"Profile update triggered: {user_profile.form_count} forms analyzed")
            return True
        
        # Rule 5: Update if stale (30+ days)
        if user_profile.updated_at:
            days_since_update = (datetime.now(timezone.utc) - user_profile.updated_at.replace(tzinfo=timezone.utc)).days
            if days_since_update >= UPDATE_DAYS_INTERVAL:
                logger.info(f"Profile update triggered: {days_since_update} days stale")
                return True
        
        logger.debug("Profile update skipped: no trigger conditions met")
        return False
    
    # -------------------------------------------------------------------------
    # Profile Generation
    # -------------------------------------------------------------------------
    
    async def generate_profile(
        self,
        db: AsyncSession,
        user_id: int,
        form_data: Dict[str, Any],
        form_type: str = "General",
        form_purpose: str = "Data collection",
        force: bool = False
    ) -> Optional[UserProfile]:
        """
        Generate or update a user's behavioral profile.
        
        Args:
            db: Database session
            user_id: User ID
            form_data: Form responses
            form_type: Type of form
            form_purpose: Purpose of the form
            force: Force update even if triggers not met
            
        Returns:
            Updated UserProfile or None if skipped/failed
        """
        if not self.llm:
            logger.warning("Profile generation skipped: LLM not available")
            return None
        
        try:
            # Fetch user and check profiling enabled
            user = await db.get(User, user_id)
            if not user:
                logger.warning(f"Profile generation: user {user_id} not found")
                return None
            
            if not user.profiling_enabled:
                logger.info(f"Profile generation skipped: user {user_id} opted out")
                return None
            
            # Fetch existing profile
            existing_profile = await self._get_profile_from_db(db, user_id)
            
            # Check if update should happen
            if not force and not self.should_update_profile(
                form_data, existing_profile, len(form_data)
            ):
                # Still increment form count if profile exists
                if existing_profile:
                    existing_profile.form_count += 1
                    await db.commit()
                return existing_profile
            
            # Generate profile text via LLM
            if existing_profile:
                profile_text = await self._update_profile_text(
                    existing_profile.profile_text,
                    form_data,
                    existing_profile.form_count,
                    form_type,
                    form_purpose
                )
            else:
                profile_text = await self._create_profile_text(
                    form_data, form_type, form_purpose
                )
            
            if not profile_text:
                logger.error("Profile generation: LLM returned empty response")
                return None
            
            # Enforce 500-word limit
            profile_text = await self._enforce_word_limit(profile_text)
            
            # Calculate confidence score
            form_count = (existing_profile.form_count + 1) if existing_profile else 1
            confidence = self._calculate_confidence(form_count, len(form_data))
            
            # Save to database
            if existing_profile:
                profile = await self._update_profile_in_db(
                    db, existing_profile, profile_text, confidence
                )
            else:
                profile = await self._create_profile_in_db(
                    db, user_id, profile_text, confidence, form_type
                )
            
            # Update cache
            await self._cache_profile(user_id, profile)
            
            logger.info(f"Profile generated for user {user_id}: confidence={confidence:.2f}")
            return profile
            
        except Exception as e:
            logger.error(f"Profile generation failed for user {user_id}: {e}")
            return None
    
    async def _create_profile_text(
        self,
        form_data: Dict[str, Any],
        form_type: str,
        form_purpose: str
    ) -> Optional[str]:
        """Generate initial profile text via LLM."""
        prompt = build_create_prompt(form_data, form_type, form_purpose)
        return await self._call_llm(prompt)
    
    async def _update_profile_text(
        self,
        existing_text: str,
        form_data: Dict[str, Any],
        previous_form_count: int,
        form_type: str,
        form_purpose: str
    ) -> Optional[str]:
        """Update existing profile text via LLM."""
        prompt = build_update_prompt(
            existing_text, form_data, previous_form_count, form_type, form_purpose
        )
        return await self._call_llm(prompt)
    
    async def _enforce_word_limit(self, profile_text: str) -> str:
        """Condense profile if over 500 words."""
        word_count = len(profile_text.split())
        
        if word_count <= MAX_PROFILE_WORDS:
            return profile_text
        
        logger.info(f"Condensing profile: {word_count} -> {MAX_PROFILE_WORDS} words")
        prompt = build_condense_prompt(profile_text)
        condensed = await self._call_llm(prompt)
        
        return condensed if condensed else profile_text[:MAX_PROFILE_WORDS * 7]  # Fallback
    
    async def _call_llm(self, prompt: str) -> Optional[str]:
        """Make LLM call with error handling."""
        try:
            chain = ChatPromptTemplate.from_messages([
                ("human", "{prompt}")
            ]) | self.llm | StrOutputParser()
            
            result = await asyncio.wait_for(
                chain.ainvoke({"prompt": prompt}),
                timeout=30.0  # 30 second timeout
            )
            return result.strip()
            
        except asyncio.TimeoutError:
            logger.error("LLM call timed out")
            return None
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None
    
    def _calculate_confidence(self, form_count: int, question_count: int) -> float:
        """Calculate profile confidence score (0.0-1.0)."""
        # Base confidence from form count
        form_score = min(form_count / 5, 1.0) * 0.6  # Max 0.6 from forms
        
        # Additional confidence from question count
        question_score = min(question_count / 15, 1.0) * 0.4  # Max 0.4 from questions
        
        return round(min(form_score + question_score, 1.0), 2)
    
    # -------------------------------------------------------------------------
    # Database Operations
    # -------------------------------------------------------------------------
    
    async def _get_profile_from_db(
        self, db: AsyncSession, user_id: int
    ) -> Optional[UserProfile]:
        """Fetch profile from database."""
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def _create_profile_in_db(
        self,
        db: AsyncSession,
        user_id: int,
        profile_text: str,
        confidence: float,
        form_type: str
    ) -> UserProfile:
        """Create new profile in database."""
        metadata = {
            "forms_analyzed": [form_type],
            "last_form_type": form_type,
            "evolution_markers": []
        }
        
        profile = UserProfile(
            user_id=user_id,
            profile_text=profile_text,
            confidence_score=confidence,
            form_count=1,
            version=1,
            metadata_json=json.dumps(metadata)
        )
        
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        
        return profile
    
    async def _update_profile_in_db(
        self,
        db: AsyncSession,
        profile: UserProfile,
        new_text: str,
        new_confidence: float
    ) -> UserProfile:
        """Update existing profile in database."""
        profile.profile_text = new_text
        profile.confidence_score = new_confidence
        profile.form_count += 1
        profile.version += 1
        
        await db.commit()
        await db.refresh(profile)
        
        return profile
    
    # -------------------------------------------------------------------------
    # Cache Operations
    # -------------------------------------------------------------------------
    
    async def _cache_profile(self, user_id: int, profile: UserProfile) -> None:
        """Cache profile for fast retrieval."""
        await set_cached(
            f"profile:{user_id}",
            profile.to_dict(),
            ttl=PROFILE_CACHE_TTL
        )
        await set_cached(
            f"profile_ready:{user_id}",
            True,
            ttl=PROFILE_READY_TTL
        )
    
    async def get_cached_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get profile from cache (fast path)."""
        return await get_cached(f"profile:{user_id}")
    
    async def invalidate_cache(self, user_id: int) -> None:
        """Invalidate profile cache."""
        await delete_cached(f"profile:{user_id}")
        await delete_cached(f"profile_ready:{user_id}")
    
    # -------------------------------------------------------------------------
    # Public API Methods
    # -------------------------------------------------------------------------
    
    async def get_profile(
        self, db: AsyncSession, user_id: int
    ) -> Optional[UserProfile]:
        """
        Get user's profile (cache-first).
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            UserProfile or None
        """
        # Try cache first
        cached = await self.get_cached_profile(user_id)
        if cached:
            # Return cached data (already dict)
            return cached
        
        # Fallback to database
        profile = await self._get_profile_from_db(db, user_id)
        if profile:
            await self._cache_profile(user_id, profile)
        
        return profile
    
    async def delete_profile(self, db: AsyncSession, user_id: int) -> bool:
        """
        Delete user's profile (privacy compliance).
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            True if deleted, False if not found
        """
        profile = await self._get_profile_from_db(db, user_id)
        if not profile:
            return False
        
        await db.delete(profile)
        await db.commit()
        await self.invalidate_cache(user_id)
        
        logger.info(f"Profile deleted for user {user_id}")
        return True
    
    async def set_profiling_enabled(
        self, db: AsyncSession, user_id: int, enabled: bool
    ) -> bool:
        """
        Enable or disable profiling for a user.
        
        Args:
            db: Database session
            user_id: User ID
            enabled: Whether to enable profiling
            
        Returns:
            True if updated
        """
        user = await db.get(User, user_id)
        if not user:
            return False
        
        user.profiling_enabled = enabled
        await db.commit()
        
        # If disabling, invalidate cache
        if not enabled:
            await self.invalidate_cache(user_id)
        
        logger.info(f"Profiling {'enabled' if enabled else 'disabled'} for user {user_id}")
        return True


# =============================================================================
# Singleton & Dependency Injection
# =============================================================================

_service_instance: Optional[ProfileService] = None


def get_profile_service() -> ProfileService:
    """Get singleton ProfileService instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = ProfileService()
    return _service_instance


async def generate_profile_background(
    user_id: int,
    form_data: Dict[str, Any],
    form_type: str = "General",
    form_purpose: str = "Data collection"
) -> None:
    """
    Background task for async profile generation.
    
    Use with FastAPI BackgroundTasks:
        background_tasks.add_task(
            generate_profile_background,
            user_id, form_data
        )
    """
    from core.database import SessionLocal
    
    service = get_profile_service()
    
    async with SessionLocal() as db:
        try:
            await service.generate_profile(
                db, user_id, form_data, form_type, form_purpose
            )
        except Exception as e:
            logger.error(f"Background profile generation failed: {e}")
