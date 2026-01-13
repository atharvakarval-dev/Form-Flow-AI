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
    from services.ai.profile import ProfileService
    
    service = ProfileService()
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
import time

from . import prompts as profile_prompts
from .config import profile_config
from .validator import ProfileValidator
from .prompt_manager import prompt_manager

logger = get_logger(__name__)


# =============================================================================
# Configuration Constants
# =============================================================================

# All configuration is now centralized in profile_config.py
# Constants are kept here as aliases if needed, or we rely directly on profile_config

# LLM Configuration
PROFILE_MODEL = "gemini-2.5-pro"  # Deeper analysis for profiles
PROFILE_TEMPERATURE = 0.3  # Consistent outputs
MAX_PROFILE_WORDS = profile_config.MAX_PROFILE_WORDS

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
            logger.info("ProfileService initialized with Gemini API (fallback)")
        
        if settings.OPENROUTER_API_KEY:
            logger.info("ProfileService: OpenRouter (Gemma 3) configured as primary")
    
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
            1. Form Quality Check (via Validator)
            2. Update Interval (Variable, default every form)
            3. Stale Profile (30+ days)
            
        Args:
            form_data: Completed form responses
            user_profile: Existing profile (None for new users)
            total_questions: Total questions in the form
            
        Returns:
            True if profile should be updated
        """
        # Rule 1: Form Quality Check
        is_valid, reason = ProfileValidator.validate_form_quality(form_data)
        if not is_valid:
            logger.debug(f"Profile update skipped: {reason}")
            return False
        
        # Rule 2: New user - always create profile
        if user_profile is None:
            logger.info("Profile update triggered: new user")
            return True
        
        # Rule 3: Update Interval
        if user_profile.form_count % profile_config.UPDATE_FORM_INTERVAL == 0:
            logger.info(f"Profile update triggered: {user_profile.form_count} forms analyzed (Interval: {profile_config.UPDATE_FORM_INTERVAL})")
            return True
        
        # Rule 4: Update if stale
        if user_profile.updated_at:
            days_since_update = (datetime.now(timezone.utc) - user_profile.updated_at.replace(tzinfo=timezone.utc)).days
            if days_since_update >= profile_config.UPDATE_DAYS_INTERVAL:
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
        if not self.llm and not settings.OPENROUTER_API_KEY:
            logger.warning("Profile generation skipped: No LLM available (neither OpenRouter nor Gemini)")
            return None
        
        start_time = time.time()
        
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
            raw_response = None
            if existing_profile:
                # Extract history
                try:
                    metadata = json.loads(existing_profile.metadata_json or '{}')
                    forms_history = metadata.get('forms_analyzed', [])
                except Exception:
                    forms_history = []
                
                # Use PromptManager for versioned prompts
                raw_response = await self._call_llm(
                    prompt_manager.build_update_prompt(
                        existing_profile.profile_text,
                        form_data,
                        existing_profile.form_count,
                        form_type,
                        form_purpose,
                        forms_history
                    )
                )
            else:
                raw_response = await self._call_llm(
                    prompt_manager.build_create_prompt(
                        form_data, form_type, form_purpose
                    )
                )
            
            # Validate LLM Output
            is_valid_output, parsed_profile, validation_error = ProfileValidator.validate_llm_output(raw_response)
            
            if not is_valid_output:
                logger.error(f"Profile generation: LLM output invalid: {validation_error}")
                return None
            
            # Re-serialize to Ensure Clean JSON string for storage
            profile_text = json.dumps(parsed_profile)
            
            # Calculate confidence score
            existing_profile_dict = None
            if existing_profile and existing_profile.profile_text:
                 try:
                     existing_profile_dict = json.loads(existing_profile.profile_text)
                 except: 
                     existing_profile_dict = None

            # Calculate quality score of input form (simple proxy)
            valid_ans_count = sum(1 for v in form_data.values() if v and len(str(v)) >= 2)
            quality_score = min(valid_ans_count / (profile_config.MIN_QUESTIONS_FOR_PROFILE * 2), 1.0)
            
            confidence = ProfileValidator.calculate_confidence(existing_profile_dict, parsed_profile, quality_score)
            
            # Save to database
            if existing_profile:
                profile = await self._update_profile_in_db(
                    db, existing_profile, profile_text, confidence, form_type
                )
            else:
                profile = await self._create_profile_in_db(
                    db, user_id, profile_text, confidence, form_type
                )
            
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
        prompt = prompt_manager.build_create_prompt(form_data, form_type, form_purpose)
        return await self._call_llm(prompt)
    
    async def _update_profile_text(
        self,
        existing_text: str,
        form_data: Dict[str, Any],
        previous_form_count: int,
        form_type: str,
        form_purpose: str,
        forms_history: List[str]
    ) -> Optional[str]:
        """Update existing profile text via LLM."""
        prompt = prompt_manager.build_update_prompt(
            existing_text, form_data, previous_form_count, form_type, form_purpose, forms_history
        )
        return await self._call_llm(prompt)
    
    async def _enforce_word_limit(self, profile_text: str) -> str:
        """Condense profile if over 500 words."""
        word_count = len(profile_text.split())
        
        if word_count <= MAX_PROFILE_WORDS:
            return profile_text
        
        logger.info(f"Condensing profile: {word_count} -> {MAX_PROFILE_WORDS} words")
        prompt = prompt_manager.build_condense_prompt(profile_text)
        condensed = await self._call_llm(prompt)
        
        return condensed if condensed else profile_text[:MAX_PROFILE_WORDS * 7]  # Fallback
    
    async def _call_llm(self, prompt: str) -> Optional[str]:
        """Make LLM call with error handling. Priority: OpenRouter (Gemma) -> Gemini."""
        
        # 1. Try OpenRouter (Gemma 3) first - preferred for profile generation
        if settings.OPENROUTER_API_KEY:
            or_result = await self._call_openrouter(prompt)
            if or_result:
                return or_result
            logger.warning("OpenRouter (Gemma) failed, falling back to Gemini...")

        # 2. Fallback to Gemini
        if not self.llm:
            logger.error("No LLM available: OpenRouter failed and Gemini not configured")
            return None

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
            logger.error("Gemini LLM call timed out")
            return None
        except Exception as e:
            logger.error(f"Gemini LLM call failed: {e}")
            return None

    async def _call_openrouter(self, prompt: str) -> Optional[str]:
        """Call OpenRouter API (Gemma 3) as fallback."""
        import os
        api_key = settings.OPENROUTER_API_KEY or os.getenv("OPENROUTER_API_KEY")
        
        if not api_key:
            logger.warning("OpenRouter API call skipped: OPENROUTER_API_KEY not found")
            return None
            
        try:
            import httpx
            
            logger.info("Calling OpenRouter API (Gemma 3)...")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://formflow.ai", # Optional but good practice
                        "X-Title": "Form Flow AI"
                    },
                    json={
                        "model": "google/gemma-3-27b-it",
                        "messages": [
                            {"role": "system", "content": "You are an expert behavioral analyst."},
                            {"role": "user", "content": prompt}
                        ],
                        "stream": False,
                        "temperature": 0.3
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # OpenRouter response format mimics OpenAI
                    content = data['choices'][0]['message']['content'].strip()
                    logger.info("OpenRouter API call successful")
                    return content
                else:
                    logger.warning(f"OpenRouter API error {response.status_code}: {response.text}")
                    return None
        except Exception as e:
            logger.error(f"OpenRouter API call failed: {e}")
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
        new_confidence: float,
        form_type: str
    ) -> UserProfile:
        """Update existing profile in database."""
        profile.profile_text = new_text
        profile.confidence_score = new_confidence
        profile.form_count += 1
        profile.version += 1
        
        # Update metadata with new form type
        try:
            metadata = json.loads(profile.metadata_json or '{}')
            forms_analyzed = metadata.get('forms_analyzed', [])
            forms_analyzed.append(form_type)
            metadata['forms_analyzed'] = forms_analyzed
            metadata['last_form_type'] = form_type
            profile.metadata_json = json.dumps(metadata)
        except Exception:
            # Fallback if metadata is corrupt
            metadata = {
                "forms_analyzed": [form_type],
                "last_form_type": form_type
            }
            profile.metadata_json = json.dumps(metadata)
        
        await db.commit()
        await db.refresh(profile)
        
        return profile
    
    async def update_profile_text(
        self,
        db: AsyncSession,
        user_id: int,
        new_text: str
    ) -> Optional[UserProfile]:
        """
        Update profile text from user edit (manual correction).
        
        Marks the profile as user-edited and preserves form count.
        """
        profile = await self._get_profile_from_db(db, user_id)
        
        if not profile:
            return None
        
        profile.profile_text = new_text
        profile.version += 1
        
        # Mark as user-edited in metadata
        try:
            metadata = json.loads(profile.metadata_json or '{}')
            metadata['user_edited'] = True
            metadata['last_edit'] = datetime.now(timezone.utc).isoformat()
            profile.metadata_json = json.dumps(metadata)
        except json.JSONDecodeError:
            pass
        
        await db.commit()
        await db.refresh(profile)
        
        # Update cache
        await self._cache_profile(user_id, profile)
        
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
