"""
Flow Engine Service - WhisperFlow Logic Layer

The core intelligence engine that processes voice input through:
1. Self-correction detection (handles "wait, no", "actually")
2. Snippet expansion (user-defined text shortcuts)
3. Smart formatting (lists, technical terms)
4. Action detection (Calendar, Jira integration)

Uses LangChain with Google Gemini for LLM processing.
"""

import json
import re
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from sqlalchemy.orm import Session
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from config.settings import settings
from core.models import Snippet, User
from services.ai.voice.correction_detector import get_correction_detector, FieldContext
from utils.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ActionPayload:
    """Detected action from voice input."""
    tool: str  # "calendar", "jira", "slack", "email"
    action_type: str  # "create_event", "create_issue", etc.
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FlowEngineResult:
    """Result of Flow Engine processing."""
    display_text: str
    intent: str  # "typing" | "command"
    detected_apps: List[str] = field(default_factory=list)
    actions: List[ActionPayload] = field(default_factory=list)
    corrections_applied: List[str] = field(default_factory=list)
    snippets_expanded: List[str] = field(default_factory=list)
    confidence: float = 1.0


# =============================================================================
# Flow Engine Service
# =============================================================================

class FlowEngine:
    """
    WhisperFlow Logic Layer.
    
    Orchestrates self-correction, snippet expansion, smart formatting,
    and action detection for voice input processing.
    
    Pipeline:
        1. Pre-process: Apply inline corrections (via CorrectionDetector)
        2. Fetch & expand user snippets
        3. LLM processing with master prompt
        4. Parse structured JSON output
    """
    
    SUPPORTED_APPS = ["calendar", "jira", "slack", "email"]
    
    # Technical vocabulary for proper capitalization
    TECH_VOCABULARY = [
        "Python", "FastAPI", "React", "TypeScript", "JavaScript", "Node.js",
        "PostgreSQL", "Redis", "Docker", "Kubernetes", "AWS", "GCP", "Azure",
        "Figma", "Miro", "Notion", "Asana", "Jira", "Slack", "GitHub", "GitLab",
        "TypeORM", "SQLAlchemy", "Prisma", "MongoDB", "GraphQL", "REST",
        "HTML", "CSS", "Tailwind", "Next.js", "Nest.js", "Vue.js", "Angular",
        "LangChain", "OpenAI", "Gemini", "HubSpot", "Salesforce", "Airtable",
    ]

    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.correction_detector = get_correction_detector()
        
        # Initialize LLM (prefer Gemini, fallback to available)
        api_key = settings.GEMMA_API_KEY or settings.GOOGLE_API_KEY
        if not api_key:
            logger.warning("No Gemini API key, FlowEngine LLM features disabled")
            self.llm = None
        else:
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                google_api_key=api_key,
                temperature=0.3,
                convert_system_message_to_human=True
            )

    async def process(
        self,
        raw_text: str,
        app_context: Optional[Dict[str, Any]] = None,
        vocabulary: Optional[List[str]] = None
    ) -> FlowEngineResult:
        """
        Main processing pipeline.
        
        Args:
            raw_text: Raw voice transcription
            app_context: Current app context (e.g., {"view": "DealPipeline"})
            vocabulary: Additional technical terms to recognize
            
        Returns:
            FlowEngineResult with processed text, intent, and actions
        """
        if not raw_text or not raw_text.strip():
            return FlowEngineResult(display_text="", intent="typing")
        
        corrections_applied = []
        snippets_expanded = []
        
        # Step 1: Apply inline corrections
        text = raw_text.strip()
        correction_result = self.correction_detector.detect(text, FieldContext())
        if correction_result.has_correction:
            text = correction_result.final_value
            corrections_applied.append(
                f"{correction_result.correction_type.value}: '{correction_result.original_segment}' → '{correction_result.corrected_value}'"
            )
            logger.debug(f"Correction applied: {corrections_applied[-1]}")
        
        # Step 2: Fetch and expand snippets
        snippets = self._get_user_snippets()
        text, expanded = self._expand_snippets(text, snippets)
        snippets_expanded.extend(expanded)
        
        # Step 3: LLM processing (if available)
        if self.llm:
            try:
                result = await self._process_with_llm(
                    text, 
                    snippets, 
                    app_context, 
                    vocabulary or []
                )
                result.corrections_applied = corrections_applied
                result.snippets_expanded = snippets_expanded
                return result
            except Exception as e:
                logger.error(f"LLM processing failed: {e}")
                # Fall through to rule-based processing
        
        # Fallback: Rule-based processing
        return self._process_with_rules(
            text, 
            corrections_applied, 
            snippets_expanded
        )

    def _get_user_snippets(self) -> Dict[str, str]:
        """Fetch active snippets for current user."""
        snippets = self.db.query(Snippet).filter(
            Snippet.user_id == self.user.id,
            Snippet.is_active == True
        ).all()
        return {s.trigger_phrase.lower(): s.expansion_value for s in snippets}

    def _expand_snippets(
        self, 
        text: str, 
        snippets: Dict[str, str]
    ) -> tuple[str, List[str]]:
        """Expand snippet triggers in text."""
        expanded = []
        text_lower = text.lower()
        
        for trigger, expansion in snippets.items():
            if trigger in text_lower:
                # Case-insensitive replacement
                pattern = re.compile(re.escape(trigger), re.IGNORECASE)
                text = pattern.sub(expansion, text)
                expanded.append(trigger)
                
        return text, expanded

    async def _process_with_llm(
        self,
        text: str,
        snippets: Dict[str, str],
        app_context: Optional[Dict[str, Any]],
        vocabulary: List[str]
    ) -> FlowEngineResult:
        """Process text through LLM with master prompt."""
        system_prompt = self._build_system_prompt(snippets, app_context, vocabulary)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=text)
        ]
        
        response = await self.llm.ainvoke(messages)
        content = response.content.strip()
        
        # Extract JSON from response (may be wrapped in markdown)
        json_match = re.search(r'\{[\s\S]*\}', content)
        if not json_match:
            logger.warning("No JSON found in LLM response, using raw text")
            return FlowEngineResult(display_text=text, intent="typing")
        
        try:
            data = json.loads(json_match.group())
            
            # Parse actions
            actions = []
            for action_data in data.get("actions", []):
                actions.append(ActionPayload(
                    tool=action_data.get("tool", ""),
                    action_type=action_data.get("type", ""),
                    payload=action_data.get("payload", {})
                ))
            
            return FlowEngineResult(
                display_text=data.get("display_text", text),
                intent=data.get("intent", "typing"),
                detected_apps=data.get("detected_apps", []),
                actions=actions,
                confidence=data.get("confidence", 1.0)
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON: {e}")
            return FlowEngineResult(display_text=text, intent="typing")

    def _build_system_prompt(
        self,
        snippets: Dict[str, str],
        app_context: Optional[Dict[str, Any]],
        vocabulary: List[str]
    ) -> str:
        """Build the master system prompt for LLM."""
        current_view = app_context.get("view", "General") if app_context else "General"
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Format snippets for prompt
        snippet_text = "\n".join([
            f'- "{trigger}" → "{value}"' 
            for trigger, value in snippets.items()
        ]) or "No snippets defined."
        
        # Combine vocabularies
        all_vocab = list(set(self.TECH_VOCABULARY + vocabulary))
        vocab_text = ", ".join(all_vocab[:30])  # Limit for prompt size
        
        return f"""# Role
You are the intelligence engine for "Form Flow AI". Process voice dictation into perfect, actionable text.

# Context
- User is in: {current_view}
- Date: {current_date}

# 1. Self-Correction (Already applied - maintain final intent)
If user changed their mind (e.g., "Wait, no", "Actually"), the correction has been applied. Preserve the corrected meaning.

# 2. Smart Formatting
- Detect implicit lists and format with Markdown bullets
- Capitalize technical terms: {vocab_text}
- Fix grammar and punctuation naturally

# 3. Snippet Expansion (Already applied - maintain expansions)
User snippets:
{snippet_text}

# 4. Action Detection
Detect commands directed at external tools. Supported apps: {", ".join(self.SUPPORTED_APPS)}
Examples:
- "Add a meeting to my calendar tomorrow at 3pm" → Calendar action
- "Create a Jira ticket for the login bug" → Jira action

# Output Format (Strict JSON)
{{
  "display_text": "The final polished text for display",
  "intent": "typing" or "command",
  "detected_apps": ["calendar"],
  "actions": [
    {{"tool": "calendar", "type": "create_event", "payload": {{"title": "...", "time": "..."}}}}
  ],
  "confidence": 0.95
}}

Output ONLY the JSON, no additional text."""

    def _process_with_rules(
        self,
        text: str,
        corrections_applied: List[str],
        snippets_expanded: List[str]
    ) -> FlowEngineResult:
        """Rule-based fallback processing without LLM."""
        # Detect lists
        list_markers = ["first", "second", "third", "1.", "2.", "3.", "- "]
        has_list = any(marker in text.lower() for marker in list_markers)
        
        # Detect action intent
        action_keywords = {
            "calendar": ["calendar", "meeting", "schedule", "appointment"],
            "jira": ["jira", "ticket", "issue", "bug", "task"],
            "slack": ["slack", "message", "dm", "channel"],
            "email": ["email", "mail", "send to"],
        }
        
        detected_apps = []
        actions = []
        text_lower = text.lower()
        
        for app, keywords in action_keywords.items():
            if any(kw in text_lower for kw in keywords):
                detected_apps.append(app)
                actions.append(ActionPayload(
                    tool=app,
                    action_type="detected",
                    payload={"raw_text": text}
                ))
        
        intent = "command" if actions else "typing"
        
        # Apply basic formatting
        display_text = self._apply_basic_formatting(text)
        
        return FlowEngineResult(
            display_text=display_text,
            intent=intent,
            detected_apps=detected_apps,
            actions=actions,
            corrections_applied=corrections_applied,
            snippets_expanded=snippets_expanded,
            confidence=0.7 if actions else 0.9
        )

    def _apply_basic_formatting(self, text: str) -> str:
        """Apply basic formatting rules."""
        # Capitalize first letter
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        
        # Add period if missing
        if text and text[-1] not in ".!?":
            text += "."
        
        # Capitalize known tech terms
        for term in self.TECH_VOCABULARY:
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            text = pattern.sub(term, text)
        
        return text


# =============================================================================
# Singleton
# =============================================================================

_engine_cache: Dict[int, FlowEngine] = {}


def get_flow_engine(db: Session, user: User) -> FlowEngine:
    """Get or create FlowEngine for user."""
    if user.id not in _engine_cache:
        _engine_cache[user.id] = FlowEngine(db, user)
    return _engine_cache[user.id]
