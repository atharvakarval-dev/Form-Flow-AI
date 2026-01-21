"""
Profile-Based Intelligent Suggestions

3-tier suggestion system using behavioral profiles for intelligent form field suggestions.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import json

from utils.logging import get_logger

logger = get_logger(__name__)


class SuggestionTier(Enum):
    """Suggestion generation tiers based on profile availability."""
    PROFILE_BASED = "profile_based"      # Tier 1: Full profile with LLM
    BLENDED = "blended"                  # Tier 2: Patterns + light profile
    PATTERN_ONLY = "pattern_only"        # Tier 3: Fast fallback


from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

class SuggestionResponse(BaseModel):
    """Structured response for LLM suggestions."""
    suggestions: List[str] = Field(description="List of suggested values")
    reasoning: str = Field(description="Why these suggestions were made based on the profile")

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
        STRICT MODE: Only uses Tier 1 (Profile/LLM). Returns empty if no profile.
        """
        field_name = field_context.get('name', 'unknown')
        field_label = field_context.get('label', 'unknown')
        
        logger.info(f"🟢 [Lifecycle] START: Request for User={user_id} Field='{field_name}' ({field_label})")

        try:
            # Try to get user profile
            from .service import get_profile_service
            profile_service = get_profile_service()
            profile = await profile_service.get_profile(db, user_id)
            
            if profile:
                # STRICT: Always use Tier 1 if profile exists. Ignore confidence score.
                logger.info(f"👤 [Lifecycle] Profile Found. Confidence: {getattr(profile, 'confidence_score', 0)}")
                logger.info("🚀 [Lifecycle] FORCING Tier 1: PROFILE_BASED (Ignoring confidence score)")
                return await self._tier1_profile_based(profile, field_context, form_context, previous_answers)
            else:
                # STRICT: No profile = No suggestions.
                logger.warning("⛔ [Lifecycle] No Profile found. Skipping Tier 3 fallback (returning empty).")
                return []
                
        except Exception as e:
            logger.error(f"❌ [Lifecycle] CRITICAL ERROR: {str(e)}", exc_info=True)
            return []
    
    async def _tier1_profile_based(
        self,
        profile: Any,
        field_context: Dict[str, Any],
        form_context: Dict[str, Any],
        previous_answers: Dict[str, str]
    ) -> List[IntelligentSuggestion]:
        """Tier 1: Full profile-based suggestions with LLM."""
        logger.info(f"🧠 [Lifecycle] Tier 1: Initiating LLM generation for '{field_context.get('name')}'")
        
        # Try to generate suggestions via LLM
        try:
            llm_suggestions = await self._generate_llm_suggestions(profile, field_context, form_context)
            if llm_suggestions:
                logger.info(f"✅ [Lifecycle] Tier 1: LLM Success. Returned {len(llm_suggestions)} suggestions.")
                return llm_suggestions
            else:
                logger.warning("⚠️ [Lifecycle] Tier 1: LLM returned empty results.")
                return [] # STRICT: Return empty instead of fallback
        except Exception as e:
            logger.error(f"❌ [Lifecycle] Tier 1: LLM Failed ({str(e)})")
            return [] # STRICT: Return empty instead of fallback

    async def _generate_llm_suggestions(
        self,
        profile: Any,
        field_context: Dict[str, Any],
        form_context: Dict[str, Any]
    ) -> Optional[List[IntelligentSuggestion]]:
        """Generate suggestions using LLM and user profile."""
        from services.ai.gemini import get_gemini_service
        gemini = get_gemini_service()
        
        if not gemini or not gemini.llm:
            logger.error("❌ [Lifecycle] Gemini Service Unavailable")
            return None

        # Extract profile text safely
        profile_text = getattr(profile, 'profile_text', str(profile))
        
        # Context extraction
        field_name = field_context.get("name", "unknown")
        field_label = field_context.get("label", field_name)
        form_purpose = form_context.get("purpose", "General Form")
        
        logger.debug(f"🤖 [Lifecycle] LLM Prompting for '{field_label}'...")

        # ---------------------------------------------------------
        # 🧠 INTELLIGENT PROMPT ENGINEERING
        # ---------------------------------------------------------
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an intelligent form-filling assistant.
Your goal is to infer the correct value for a specific form field based on a User Profile.

CONTEXT:
- **Field Label:** "{field_label}" (Internal Name: {field_name})
- **Form Context:** {form_purpose}
- **User Profile:** {profile}

INSTRUCTIONS:
1. **Analyze the Field:** - If the field is "Position", "Role", or "Title", interpret it as **Job Title**.
   - If the field is "Company" or "Organization", look for the user's **Employer**.
   - If the field is "Address", look for the user's **Home Address**.

2. **Search Profile:** Look for direct matches or infer logical answers (e.g., infer State from City).

3. **Output:** Return a JSON object with a list of 1-3 suggestions and your reasoning.

FORMAT:
{{
  "suggestions": ["String Value 1", "String Value 2"],
  "reasoning": "Brief explanation of why this fits the profile"
}}
"""),
        ])

        parser = JsonOutputParser(pydantic_object=SuggestionResponse)
        chain = prompt | gemini.llm | parser

        try:
            start_time = datetime.now()
            
            # Execute the prompt
            result = await chain.ainvoke({
                "profile": profile_text,
                "form_purpose": form_purpose,
                "field_label": field_label,
                "field_name": field_name
            })
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"🤖 [Lifecycle] LLM Response ({duration:.2f}s): {json.dumps(result)}")

            if result and result.get("suggestions"):
                suggestions = []
                for val in result["suggestions"]:
                    suggestions.append(IntelligentSuggestion(
                        value=val,
                        confidence=0.85,
                        tier=SuggestionTier.PROFILE_BASED,
                        reasoning=result.get("reasoning", "Inferred from profile"),
                        behavioral_match="llm_inference"
                    ))
                return suggestions
            else:
                logger.warning(f"⚠️ [Lifecycle] LLM returned valid JSON but empty suggestions.")

        except Exception as e:
            logger.error(f"❌ [Lifecycle] LLM Invocation Exception: {str(e)}")
            logger.info("suggestion is", suggestions)
            return None
        
        return None
    
    def _tier2_blended(
        self,
        profile: Any,
        field_context: Dict[str, Any],
        form_context: Dict[str, Any],
        previous_answers: Dict[str, str]
    ) -> List[IntelligentSuggestion]:
        """Tier 2: Blended patterns + profile context."""
        # Since we disabled Tier 3 fallback, Tier 2 essentially becomes empty or needs its own logic.
        # For this request, we will return empty to be safe.
        logger.info("🎨 [Lifecycle] Tier 2 requested but disabled in strict mode.")
        return []
    
    def _tier3_pattern_only(
        self,
        field_context: Dict[str, Any],
        previous_answers: Dict[str, str]
    ) -> List[IntelligentSuggestion]:
        """Tier 3: Intelligent Pattern-only suggestions."""
        # DISABLED as per request
        logger.info("🧩 [Lifecycle] Tier 3 requested but DISABLED.")
        return []


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
    """
    engine = get_profile_suggestion_engine()
    return await engine.get_suggestions(
        user_id=user_id,
        field_context=field_context,
        form_context=form_context,
        previous_answers=previous_answers,
        db=db
    )