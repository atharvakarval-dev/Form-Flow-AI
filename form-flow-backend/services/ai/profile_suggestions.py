"""
Profile-Based Intelligent Suggestion Engine

ChatGPT/Claude-level intelligent suggestion system that leverages
behavioral profiles to generate deeply personalized form suggestions.

Architecture:
    THREE-TIER SUGGESTION SYSTEM
    ├── Tier 1: Profile-Based (LLM-powered, uses behavioral profile)
    │   └── High personalization, understands user's decision-making style
    ├── Tier 2: Profile-Blended (Pattern + Light profile context)
    │   └── Medium personalization for low-confidence profiles
    └── Tier 3: Smart Fallback (Pattern-only, no profile)
        └── Fast defaults for new users

Intelligence Features:
    - Behavioral Pattern Understanding (from profile)
    - Decision-Style Awareness (analytical vs intuitive)
    - Communication Preference Matching
    - Context-Aware Response Formatting
    - Confidence-Based Tier Selection

Usage:
    from services.ai.profile_suggestions import get_intelligent_suggestions
    
    suggestions = await get_intelligent_suggestions(
        user_id=user_id,
        field_context={"name": "company", "label": "Company Name", "type": "text"},
        form_context={"purpose": "Job Application", "field_count": 15}
    )
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser

from config.settings import settings
from utils.logging import get_logger
from utils.cache import get_cached, set_cached

logger = get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

# LLM Configuration for real-time suggestions (fast model)
SUGGESTION_MODEL = "gemini-1.5-flash"  # Fast for real-time
SUGGESTION_TEMPERATURE = 0.4  # Balanced creativity
SUGGESTION_TIMEOUT = 5.0  # Max 5 seconds

# Cache Configuration
SUGGESTION_CACHE_TTL = 1800  # 30 minutes

# Confidence Thresholds
HIGH_CONFIDENCE_THRESHOLD = 0.6
LOW_CONFIDENCE_THRESHOLD = 0.3


# =============================================================================
# Suggestion Tier Enum
# =============================================================================

class SuggestionTier(str, Enum):
    """Tier levels for suggestion generation."""
    PROFILE_BASED = "profile_based"      # Tier 1: Full LLM + Profile
    PROFILE_BLENDED = "profile_blended"  # Tier 2: Pattern + Light Profile
    PATTERN_ONLY = "pattern_only"        # Tier 3: Smart Fallback


# =============================================================================
# Intelligent Suggestion Result
# =============================================================================

@dataclass
class IntelligentSuggestion:
    """
    A deeply personalized suggestion with behavioral context.
    
    Unlike simple suggestions, these include reasoning that
    demonstrates understanding of the user's behavioral profile.
    """
    value: str                          # The suggested value
    confidence: float                   # 0.0 - 1.0
    tier: SuggestionTier                # Which tier generated this
    reasoning: str                      # Why this matches the user
    behavioral_match: str               # How it aligns with profile
    alternative_framing: Optional[str]  # Alternative way to present
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "confidence": self.confidence,
            "tier": self.tier.value,
            "reasoning": self.reasoning,
            "behavioral_match": self.behavioral_match,
            "alternative_framing": self.alternative_framing,
        }


# =============================================================================
# Profile-Based Suggestion Prompts (ChatGPT/Claude-Level)
# =============================================================================

TIER1_SUGGESTION_PROMPT = """You are an expert at understanding human behavior and providing personalized suggestions.

## USER'S BEHAVIORAL PROFILE
{profile_text}

## CURRENT QUESTION
Field: {field_name}
Label: {field_label}
Type: {field_type}
Form Purpose: {form_purpose}

## YOUR TASK
Based on the user's behavioral profile, generate 3 highly personalized suggestions for this field.

For each suggestion, consider:
1. **Decision-Making Style**: Does the user prefer detailed options or quick choices?
2. **Communication Style**: Formal vs casual, brief vs elaborate?
3. **Risk Tolerance**: Conservative choices or innovative ones?
4. **Goals & Motivations**: What outcome are they seeking?

## OUTPUT FORMAT
Return a JSON array with exactly 3 suggestions:
```json
[
  {{
    "value": "The actual suggestion value",
    "confidence": 0.85,
    "reasoning": "Why this matches their profile",
    "behavioral_match": "Aligns with [specific profile trait]",
    "alternative_framing": "Another way to phrase this"
  }}
]
```

## CRITICAL RULES
- Suggestions must be SPECIFIC to this field type
- Each suggestion must reference a specific behavioral insight
- Order by confidence (highest first)
- Keep values appropriate for form input (no long paragraphs)
- For name/email/phone fields, be realistic

Generate suggestions now:
"""


TIER2_BLENDED_PROMPT = """You are helping fill a form field with intelligent defaults.

## LIGHT BEHAVIORAL CONTEXT
Profile Summary: {profile_summary}
Confidence Level: {confidence_level}

## FIELD CONTEXT
Field: {field_name}
Label: {field_label}
Type: {field_type}
Common Values Seen: {pattern_suggestions}

## TASK
Generate 2 smart suggestions that blend pattern-based defaults with light personalization.

Return JSON:
```json
[
  {{"value": "...", "confidence": 0.7, "reasoning": "..."}}
]
```
"""


# =============================================================================
# Profile Suggestion Engine
# =============================================================================

class ProfileSuggestionEngine:
    """
    Intelligent suggestion engine that uses behavioral profiles
    to generate ChatGPT/Claude-level personalized suggestions.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with Gemini API key."""
        self.api_key = api_key or settings.GOOGLE_API_KEY
        self._llm = None
        self._pattern_engine = None
        
        if self.api_key:
            logger.info("ProfileSuggestionEngine initialized with Gemini Flash")
        else:
            logger.warning("ProfileSuggestionEngine: No API key - using pattern-only mode")
    
    @property
    def llm(self) -> Optional[ChatGoogleGenerativeAI]:
        """Lazy-load fast LLM for suggestions."""
        if self._llm is None and self.api_key:
            self._llm = ChatGoogleGenerativeAI(
                model=SUGGESTION_MODEL,
                google_api_key=self.api_key,
                temperature=SUGGESTION_TEMPERATURE,
                convert_system_message_to_human=True
            )
        return self._llm
    
    @property
    def pattern_engine(self):
        """Lazy-load pattern-based suggestion engine."""
        if self._pattern_engine is None:
            from services.ai.suggestion_engine import SuggestionEngine
            self._pattern_engine = SuggestionEngine()
        return self._pattern_engine
    
    # -------------------------------------------------------------------------
    # Main Suggestion Interface
    # -------------------------------------------------------------------------
    
    async def get_suggestions(
        self,
        user_id: int,
        field_context: Dict[str, Any],
        form_context: Optional[Dict[str, Any]] = None,
        previous_answers: Optional[Dict[str, str]] = None,
        db = None
    ) -> List[IntelligentSuggestion]:
        """
        Get intelligent suggestions using the tiered system.
        
        Automatically selects the appropriate tier based on:
        1. Profile availability and confidence
        2. LLM availability
        3. Cache hits
        
        Args:
            user_id: User ID
            field_context: Current field info (name, label, type)
            form_context: Form-level context (purpose, field_count)
            previous_answers: Already answered fields in this form
            db: Optional database session
            
        Returns:
            List of IntelligentSuggestion objects
        """
        form_context = form_context or {}
        previous_answers = previous_answers or {}
        
        # Step 1: Check cache first
        cache_key = self._build_cache_key(user_id, field_context)
        cached = await get_cached(cache_key)
        if cached:
            return [IntelligentSuggestion(**s) for s in cached]
        
        # Step 2: Get user profile
        profile = await self._get_user_profile(user_id, db)
        
        # Step 3: Select tier and generate suggestions
        if profile and profile.get("confidence_score", 0) >= HIGH_CONFIDENCE_THRESHOLD:
            # Tier 1: Full profile-based
            suggestions = await self._tier1_profile_based(
                profile, field_context, form_context, previous_answers
            )
        elif profile and profile.get("confidence_score", 0) >= LOW_CONFIDENCE_THRESHOLD:
            # Tier 2: Blended
            suggestions = await self._tier2_blended(
                profile, field_context, form_context, previous_answers
            )
        else:
            # Tier 3: Pattern only
            suggestions = self._tier3_pattern_only(
                field_context, previous_answers
            )
        
        # Step 4: Cache results
        if suggestions:
            await set_cached(
                cache_key,
                [s.to_dict() for s in suggestions],
                ttl=SUGGESTION_CACHE_TTL
            )
        
        return suggestions
    
    # -------------------------------------------------------------------------
    # Tier 1: Profile-Based (Full LLM Intelligence)
    # -------------------------------------------------------------------------
    
    async def _tier1_profile_based(
        self,
        profile: Dict[str, Any],
        field_context: Dict[str, Any],
        form_context: Dict[str, Any],
        previous_answers: Dict[str, str]
    ) -> List[IntelligentSuggestion]:
        """
        Generate suggestions using full behavioral profile.
        
        This is the ChatGPT/Claude-level intelligence tier.
        """
        if not self.llm:
            return self._tier3_pattern_only(field_context, previous_answers)
        
        try:
            prompt = TIER1_SUGGESTION_PROMPT.format(
                profile_text=profile.get("profile_text", "No profile available"),
                field_name=field_context.get("name", "unknown"),
                field_label=field_context.get("label", field_context.get("name", "")),
                field_type=field_context.get("type", "text"),
                form_purpose=form_context.get("purpose", "General form")
            )
            
            chain = ChatPromptTemplate.from_messages([
                ("human", "{prompt}")
            ]) | self.llm | StrOutputParser()
            
            result = await asyncio.wait_for(
                chain.ainvoke({"prompt": prompt}),
                timeout=SUGGESTION_TIMEOUT
            )
            
            # Parse JSON response
            suggestions = self._parse_llm_suggestions(result, SuggestionTier.PROFILE_BASED)
            
            logger.info(f"Tier 1: Generated {len(suggestions)} profile-based suggestions for {field_context.get('name')}")
            return suggestions
            
        except asyncio.TimeoutError:
            logger.warning("Tier 1 timed out, falling back to Tier 3")
            return self._tier3_pattern_only(field_context, previous_answers)
        except Exception as e:
            logger.error(f"Tier 1 failed: {e}, falling back to Tier 3")
            return self._tier3_pattern_only(field_context, previous_answers)
    
    # -------------------------------------------------------------------------
    # Tier 2: Profile-Blended (Pattern + Light Profile)
    # -------------------------------------------------------------------------
    
    async def _tier2_blended(
        self,
        profile: Dict[str, Any],
        field_context: Dict[str, Any],
        form_context: Dict[str, Any],
        previous_answers: Dict[str, str]
    ) -> List[IntelligentSuggestion]:
        """
        Generate suggestions blending patterns with light profile context.
        """
        # Get pattern-based suggestions first
        pattern_suggestions = self._get_pattern_suggestions(field_context, previous_answers)
        
        if not self.llm:
            # Just enhance pattern suggestions with generic behavioral framing
            return [
                IntelligentSuggestion(
                    value=s,
                    confidence=0.6,
                    tier=SuggestionTier.PROFILE_BLENDED,
                    reasoning="Based on common patterns and your profile",
                    behavioral_match="Matches typical user preferences",
                    alternative_framing=None
                )
                for s in pattern_suggestions[:3]
            ]
        
        try:
            # Extract profile summary (first 200 chars)
            profile_summary = profile.get("profile_text", "")[:200]
            
            prompt = TIER2_BLENDED_PROMPT.format(
                profile_summary=profile_summary,
                confidence_level=profile.get("confidence_level", "Medium"),
                field_name=field_context.get("name", "unknown"),
                field_label=field_context.get("label", ""),
                field_type=field_context.get("type", "text"),
                pattern_suggestions=", ".join(pattern_suggestions[:5]) if pattern_suggestions else "None"
            )
            
            chain = ChatPromptTemplate.from_messages([
                ("human", "{prompt}")
            ]) | self.llm | StrOutputParser()
            
            result = await asyncio.wait_for(
                chain.ainvoke({"prompt": prompt}),
                timeout=3.0  # Shorter timeout for Tier 2
            )
            
            suggestions = self._parse_llm_suggestions(result, SuggestionTier.PROFILE_BLENDED)
            
            logger.info(f"Tier 2: Generated {len(suggestions)} blended suggestions")
            return suggestions
            
        except Exception as e:
            logger.warning(f"Tier 2 failed: {e}, using pattern-only")
            return self._tier3_pattern_only(field_context, previous_answers)
    
    # -------------------------------------------------------------------------
    # Tier 3: Pattern-Only (Fast Fallback)
    # -------------------------------------------------------------------------
    
    def _tier3_pattern_only(
        self,
        field_context: Dict[str, Any],
        previous_answers: Dict[str, str]
    ) -> List[IntelligentSuggestion]:
        """
        Generate suggestions using pattern detection only.
        
        This is the fastest tier, suitable for new users or when LLM is unavailable.
        """
        suggestions = []
        
        field_name = field_context.get("name", "").lower()
        field_type = field_context.get("type", "text")
        
        # Smart defaults based on field type
        smart_defaults = self._get_smart_defaults(field_name, field_type, previous_answers)
        
        for value, confidence, reasoning in smart_defaults:
            suggestions.append(IntelligentSuggestion(
                value=value,
                confidence=confidence,
                tier=SuggestionTier.PATTERN_ONLY,
                reasoning=reasoning,
                behavioral_match="Common pattern detected",
                alternative_framing=None
            ))
        
        logger.debug(f"Tier 3: Generated {len(suggestions)} pattern-based suggestions")
        return suggestions[:3]
    
    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    
    async def _get_user_profile(self, user_id: int, db = None) -> Optional[Dict[str, Any]]:
        """Get user profile from cache or database."""
        # Try cache first
        cached = await get_cached(f"profile:{user_id}")
        if cached:
            return cached
        
        # Fallback to database if session provided
        if db:
            try:
                from services.ai.profile_service import get_profile_service
                service = get_profile_service()
                profile = await service.get_profile(db, user_id)
                return profile.to_dict() if hasattr(profile, 'to_dict') else profile
            except Exception as e:
                logger.debug(f"Profile lookup failed: {e}")
        
        return None
    
    def _build_cache_key(self, user_id: int, field_context: Dict[str, Any]) -> str:
        """Build cache key for suggestion."""
        field_name = field_context.get("name", "unknown")
        field_type = field_context.get("type", "text")
        return f"suggestion:{user_id}:{field_name}:{field_type}"
    
    def _parse_llm_suggestions(
        self, 
        response: str, 
        tier: SuggestionTier
    ) -> List[IntelligentSuggestion]:
        """Parse LLM JSON response into IntelligentSuggestion objects."""
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'\[[\s\S]*?\]', response)
            if not json_match:
                return []
            
            data = json.loads(json_match.group())
            
            suggestions = []
            for item in data[:3]:  # Max 3 suggestions
                suggestions.append(IntelligentSuggestion(
                    value=str(item.get("value", "")),
                    confidence=float(item.get("confidence", 0.7)),
                    tier=tier,
                    reasoning=str(item.get("reasoning", "Based on behavioral analysis")),
                    behavioral_match=str(item.get("behavioral_match", "Profile alignment")),
                    alternative_framing=item.get("alternative_framing")
                ))
            
            return suggestions
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse LLM suggestions: {e}")
            return []
    
    def _get_pattern_suggestions(
        self, 
        field_context: Dict[str, Any], 
        previous_answers: Dict[str, str]
    ) -> List[str]:
        """Get suggestions from pattern engine."""
        # Detect patterns from previous answers
        all_patterns = {}
        for field_name, value in previous_answers.items():
            patterns = self.pattern_engine.detect_patterns(
                field_name=field_name,
                field_value=value,
                field_type="text",
                field_label=""
            )
            all_patterns.update(patterns)
        
        # Generate suggestions based on patterns
        suggestions = self.pattern_engine.generate_suggestions(
            target_fields=[field_context],
            extracted_fields=previous_answers,
            detected_patterns=all_patterns
        )
        
        return [s.suggested_value for s in suggestions]
    
    def _get_smart_defaults(
        self, 
        field_name: str, 
        field_type: str,
        previous_answers: Dict[str, str]
    ) -> List[Tuple[str, float, str]]:
        """Get smart default values based on field semantics."""
        defaults = []
        
        # Name-related fields
        if "first" in field_name and "name" in field_name:
            if "full_name" in previous_answers:
                parts = previous_answers["full_name"].split()
                if parts:
                    defaults.append((parts[0], 0.85, "Extracted from full name"))
        
        elif "last" in field_name and "name" in field_name:
            if "full_name" in previous_answers:
                parts = previous_answers["full_name"].split()
                if len(parts) > 1:
                    defaults.append((parts[-1], 0.85, "Extracted from full name"))
        
        # Email suggestions
        elif "email" in field_name:
            if "work" in field_name and "personal_email" in previous_answers:
                personal = previous_answers.get("personal_email", "")
                if "@" in personal:
                    local_part = personal.split("@")[0]
                    defaults.append((f"{local_part}@company.com", 0.6, "Based on personal email format"))
        
        # Country from phone
        elif "country" in field_name:
            defaults.extend([
                ("United States", 0.5, "Common default"),
                ("India", 0.4, "Common default"),
                ("United Kingdom", 0.4, "Common default"),
            ])
        
        # Generic text defaults based on type
        elif field_type == "text":
            defaults.append(("", 0.3, "Start typing for suggestions"))
        
        return defaults


# =============================================================================
# Singleton & Factory
# =============================================================================

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
    form_context: Optional[Dict[str, Any]] = None,
    previous_answers: Optional[Dict[str, str]] = None,
    db = None
) -> List[IntelligentSuggestion]:
    """
    Convenience function to get intelligent suggestions.
    
    This is the main entry point for the profile-based suggestion system.
    """
    engine = get_profile_suggestion_engine()
    return await engine.get_suggestions(
        user_id=user_id,
        field_context=field_context,
        form_context=form_context,
        previous_answers=previous_answers,
        db=db
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "SuggestionTier",
    "IntelligentSuggestion",
    "ProfileSuggestionEngine",
    "get_profile_suggestion_engine",
    "get_intelligent_suggestions",
]
