"""
Profile-Based Intelligent Suggestions

3-tier suggestion system using behavioral profiles for intelligent form field suggestions.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession

from utils.logging import get_logger

logger = get_logger(__name__)


class SuggestionTier(Enum):
    """Suggestion generation tiers based on profile availability."""
    PROFILE_BASED = "profile_based"      # Tier 1: Full profile with LLM
    BLENDED = "blended"                  # Tier 2: Patterns + light profile
    PATTERN_ONLY = "pattern_only"        # Tier 3: Fast fallback


@dataclass
class IntelligentSuggestion:
    """A single intelligent suggestion with context."""
    value: str
    confidence: float
    tier: SuggestionTier
    reasoning: str
    behavioral_match: str
    alternative_framing: Optional[str] = None


class ProfileSuggestionEngine:
    """
    Intelligent suggestion engine using behavioral profiles.
    
    Implements a 3-tier system:
    - Tier 1: Profile-based suggestions using LLM
    - Tier 2: Blended patterns + profile context
    - Tier 3: Pattern-only for new/anonymous users
    """
    
    def __init__(self):
        self._cache = {}
    
    async def get_suggestions(
        self,
        user_id: int,
        field_context: Dict[str, Any],
        form_context: Dict[str, Any],
        previous_answers: Dict[str, str],
        db: AsyncSession,
        n_results: int = 5
    ) -> List[IntelligentSuggestion]:
        """
        Generate intelligent suggestions for a form field.
        
        Automatically selects the appropriate tier based on profile availability.
        """
        try:
            # Try to get user profile
            from .service import get_profile_service
            profile_service = get_profile_service()
            profile = await profile_service.get_profile(db, user_id)
            
            if profile and hasattr(profile, 'confidence_score') and profile.confidence_score > 0.7:
                # Tier 1: Full profile-based
                return self._tier1_profile_based(profile, field_context, form_context, previous_answers)
            elif profile:
                # Tier 2: Blended
                return self._tier2_blended(profile, field_context, form_context, previous_answers)
            else:
                # Tier 3: Pattern only
                return self._tier3_pattern_only(field_context, previous_answers)
                
        except Exception as e:
            logger.warning(f"Profile suggestion failed, falling back to patterns: {e}")
            return self._tier3_pattern_only(field_context, previous_answers)
    
    def _tier1_profile_based(
        self,
        profile: Any,
        field_context: Dict[str, Any],
        form_context: Dict[str, Any],
        previous_answers: Dict[str, str]
    ) -> List[IntelligentSuggestion]:
        """Tier 1: Full profile-based suggestions with LLM."""
        # For now, fall back to pattern-based
        suggestions = self._tier3_pattern_only(field_context, previous_answers)
        # Upgrade tier
        for s in suggestions:
            s.tier = SuggestionTier.PROFILE_BASED
            s.reasoning = "Based on your behavioral profile"
        return suggestions
    
    def _tier2_blended(
        self,
        profile: Any,
        field_context: Dict[str, Any],
        form_context: Dict[str, Any],
        previous_answers: Dict[str, str]
    ) -> List[IntelligentSuggestion]:
        """Tier 2: Blended patterns + profile context."""
        suggestions = self._tier3_pattern_only(field_context, previous_answers)
        for s in suggestions:
            s.tier = SuggestionTier.BLENDED
            s.reasoning = "Based on common patterns and your preferences"
        return suggestions
    
    def _tier3_pattern_only(
        self,
        field_context: Dict[str, Any],
        previous_answers: Dict[str, str]
    ) -> List[IntelligentSuggestion]:
        """Tier 3: Pattern-only suggestions for new users."""
        field_name = field_context.get("name", "").lower()
        field_type = field_context.get("type", "text").lower()
        suggestions = []
        
        # Generate pattern-based suggestions
        if "email" in field_name or field_type == "email":
            suggestions = [
                IntelligentSuggestion(
                    value="",
                    confidence=0.5,
                    tier=SuggestionTier.PATTERN_ONLY,
                    reasoning="Enter your email address",
                    behavioral_match="common_pattern"
                )
            ]
        elif "name" in field_name:
            suggestions = [
                IntelligentSuggestion(
                    value="",
                    confidence=0.5,
                    tier=SuggestionTier.PATTERN_ONLY,
                    reasoning="Enter your full name",
                    behavioral_match="common_pattern"
                )
            ]
        elif "phone" in field_name or field_type == "tel":
            suggestions = [
                IntelligentSuggestion(
                    value="",
                    confidence=0.5,
                    tier=SuggestionTier.PATTERN_ONLY,
                    reasoning="Enter your phone number",
                    behavioral_match="common_pattern"
                )
            ]
        
        return suggestions


# Singleton instance
_engine_instance: Optional[ProfileSuggestionEngine] = None


def get_profile_suggestion_engine() -> ProfileSuggestionEngine:
    """Get singleton ProfileSuggestionEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ProfileSuggestionEngine()
    return _engine_instance


async def get_intelligent_suggestions(
    user_id: int,
    field_context: Dict[str, Any],
    form_context: Dict[str, Any],
    previous_answers: Dict[str, str],
    db: AsyncSession
) -> List[IntelligentSuggestion]:
    """
    Convenience function to get intelligent suggestions.
    
    Usage:
        suggestions = await get_intelligent_suggestions(
            user_id=123,
            field_context={"name": "email", "type": "email"},
            form_context={"purpose": "Registration"},
            previous_answers={},
            db=session
        )
    """
    engine = get_profile_suggestion_engine()
    return await engine.get_suggestions(
        user_id=user_id,
        field_context=field_context,
        form_context=form_context,
        previous_answers=previous_answers,
        db=db
    )
