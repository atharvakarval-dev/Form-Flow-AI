"""
Correction Detector

World-class real-time correction detection for voice input.
Detects and parses inline corrections like "john... actually james".

Features:
- 15+ correction trigger patterns
- Partial/scope-aware corrections
- Nested correction handling
- Restart pattern detection
- Confidence scoring
"""

import re
from enum import Enum
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from utils.logging import get_logger

logger = get_logger(__name__)


class CorrectionType(str, Enum):
    """Types of corrections detected."""
    NONE = "none"           # No correction detected
    FULL = "full"           # Full value replacement
    PARTIAL = "partial"     # Partial value change (e.g., domain only)
    SPELLING = "spelling"   # Spelling correction (J-O-N → J-O-H-N)
    RESTART = "restart"     # Abandoned start and restart
    NESTED = "nested"       # Multiple corrections, use last


class CorrectionScope(str, Enum):
    """Scope of what's being corrected."""
    FULL_VALUE = "full_value"
    EMAIL_DOMAIN = "email_domain"
    EMAIL_LOCAL = "email_local"
    PHONE_PREFIX = "phone_prefix"
    PHONE_SUFFIX = "phone_suffix"
    UNKNOWN = "unknown"


@dataclass
class FieldContext:
    """Context about the field being filled."""
    field_type: str = "text"
    field_name: str = ""
    field_label: str = ""
    current_value: str = ""


@dataclass
class CorrectionResult:
    """Result of correction detection."""
    has_correction: bool = False
    correction_type: CorrectionType = CorrectionType.NONE
    original_segment: str = ""      # The part being corrected ("john@gmail")
    corrected_value: str = ""       # The correction ("james@gmail")
    final_value: str = ""           # Final complete value after applying correction
    correction_marker: str = ""     # Trigger word ("actually", "no wait")
    confidence: float = 0.0
    scope: CorrectionScope = CorrectionScope.FULL_VALUE
    pattern_matched: str = ""       # Which pattern triggered detection
    clean_transcript: str = ""      # LLM-generated clean sentence (populated downstream)


class CorrectionDetector:
    """
    World-class real-time correction detection.
    
    Detects inline corrections in voice input and extracts the corrected value.
    Handles explicit corrections ("actually"), negations ("not X, it's Y"),
    restarts ("j... james"), and partial corrections ("@gmail... @yahoo").
    """
    
    # =========================================================================
    # CORRECTION TRIGGER PATTERNS (Ordered by priority)
    # =========================================================================
    
    # Priority 1: Explicit strong correction markers
    EXPLICIT_STRONG_PATTERNS = [
        # "forget it" / "actually forget it" -> explicit restart
        (r'(?:actually\s+)?forget\s+it[,\s]+(.+)$', 'forget_it'),
        # "let me correct that, X"
        (r'let\s+me\s+correct(?:\s+that)?[,:\s]+(.+)$', 'let_me_correct'),
        (r'correction[:\s]+(.+)$', 'correction'),
        # "actually X"
        (r'\bactually[,\s]+(.+)$', 'actually'),
        # "scratch that, X"
        (r'scratch\s+that[,\s]+(.+)$', 'scratch_that'),
    ]
    
    # Priority 2: Medium strength correction markers
    EXPLICIT_MEDIUM_PATTERNS = [
        # "oh sorry, its X"
        (r'\boh\s+sorry[,\s]+(?:it\'?s\s+|its\s+)?(.+)$', 'oh_sorry'),
        # "sorry, it's X"
        (r'\bsorry[,\s]+(?:it\'?s\s+|its\s+)(.+)$', 'sorry_its'),
        # "sorry X"
        (r'(?:sorry|oops|my\s+bad)[,\s]+(.+)$', 'sorry'),
        # "I mean X"
        (r'\bi\s+mean[t]?[,\s]+(?:it\'?s\s+|its\s+)?(.+)$', 'i_mean'),
        # "no wait, X"
        (r'(?:no\s+)?wait[,\s]+(?:it\'?s\s+|its\s+)?(.+)$', 'no_wait'),
        # "rather X"
        (r'(?:or\s+)?rather[,\s]+(.+)$', 'rather'),
        # "make that X"
        (r'make\s+that[,\s]+(.+)$', 'make_that'),
        # "change that to X"
        (r'change\s+(?:that|it)\s+to[,\s]+(.+)$', 'change_to'),
        # "instead X"
        (r'\binstead[,\s]+(.+)$', 'instead'),
    ]
    
    # Priority 3: Negation patterns
    NEGATION_PATTERNS = [
        # "no its X"
        (r'\bno[,\s]+(?:it\'?s|its)\s+(.+)$', 'no_its'),
        # "no it is X"
        (r'\bno[,\s]+it\s+is\s+(.+)$', 'no_it_is'),
        # "not X, it's Y" - two capture groups!
        (r'not\s+(\S+)[,\s]+(?:it\'?s|its|it\s+is)\s+(.+)$', 'not_its'),
        # "No, <value>" - handles mid-sentence "Call 555. No, call..."
        (r'(?:^|[.!?]\s+)\b(?:no|nope)[,\s]+(?!problem|worries|thanks|thank|issue|way)(.+)$', 'no_value'),
    ]
    
    # Priority 4: Restart patterns (abandoned starts)
    RESTART_PATTERNS = [
        # "j... james" (Standard stutter)
        (r'(\w{1,3})\.{2,}\s*(\w{2,}.*)$', 'abandoned_start'),
        # "Janu- no February" (Hyphenated cut-off with optional correction word)
        (r'(\w+)-\s+(?:no\s+|sorry\s+|actually\s+)?(\w+.*)$', 'hyphen_restart'),
    ]
    
    # Priority 5: Partial correction patterns (field-type specific)
    PARTIAL_EMAIL_PATTERNS = [
        (r'(?:@|at\s+)(\w+)[,.\s]+(?:actually|no|I\s+mean)[,\s]+(?:@|at\s+)?(\w+)', 'email_domain'),
    ]
    
    PARTIAL_PHONE_PATTERNS = [
        (r'(\d{3,})[,.\s]+(?:actually|no|I\s+mean|wait)[,\s]+(\d{3,})$', 'phone_suffix'),
    ]
    
    # Words that look like corrections but shouldn't trigger
    FALSE_POSITIVE_GUARDS = [
        r'\bactually\s+(?:inc|llc|ltd|corp|co\.?)\b',
        r'\bno\s+(?:problem|worries|thanks|thank\s+you|issue)\b',
    ]
    
    def __init__(self):
        """Initialize with compiled patterns."""
        self._compile_patterns()
        self._correction_history: List[CorrectionResult] = []
    
    def _compile_patterns(self):
        """Pre-compile all regex patterns for performance."""
        self._compiled = {
            'explicit_strong': [(re.compile(p, re.IGNORECASE), name) for p, name in self.EXPLICIT_STRONG_PATTERNS],
            'explicit_medium': [(re.compile(p, re.IGNORECASE), name) for p, name in self.EXPLICIT_MEDIUM_PATTERNS],
            'negation': [(re.compile(p, re.IGNORECASE), name) for p, name in self.NEGATION_PATTERNS],
            'restart': [(re.compile(p, re.IGNORECASE), name) for p, name in self.RESTART_PATTERNS],
            'email_partial': [(re.compile(p, re.IGNORECASE), name) for p, name in self.PARTIAL_EMAIL_PATTERNS],
            'phone_partial': [(re.compile(p, re.IGNORECASE), name) for p, name in self.PARTIAL_PHONE_PATTERNS],
        }
        self._false_positive_guards = [re.compile(p, re.IGNORECASE) for p in self.FALSE_POSITIVE_GUARDS]
    
    def detect(self, text: str, field_context: Optional[FieldContext] = None) -> CorrectionResult:
        """
        Detect corrections in voice input.
        
        Args:
            text: Raw voice input text
            field_context: Context about the field being filled
            
        Returns:
            CorrectionResult with detection details
        """
        if not text or len(text.strip()) < 2:
            return CorrectionResult()
        
        text = text.strip()
        field_context = field_context or FieldContext()
        
        # Check for false positives first
        if self._is_false_positive(text):
            return CorrectionResult(final_value=text)
        
        # Check all pattern groups in priority order
        for group in ['explicit_strong', 'explicit_medium', 'negation']:
            result = self._check_pattern_group(group, text)
            if result:
                return result
        
        # Check restart patterns
        result = self._check_pattern_group('restart', text)
        if result:
            return result
        
        # Field-specific partial corrections
        if field_context.field_type in ['email', 'e-mail']:
            result = self._check_pattern_group('email_partial', text, scope=CorrectionScope.EMAIL_DOMAIN)
            if result:
                return result
        
        if field_context.field_type in ['tel', 'phone', 'mobile']:
            result = self._check_pattern_group('phone_partial', text, scope=CorrectionScope.PHONE_SUFFIX)
            if result:
                return result
        
        # Check for nested/multiple corrections
        result = self._check_nested_corrections(text)
        if result:
            return result
        
        # No correction detected
        return CorrectionResult(final_value=text)
    
    def _check_pattern_group(
        self, 
        group_name: str, 
        text: str, 
        scope: CorrectionScope = CorrectionScope.FULL_VALUE
    ) -> Optional[CorrectionResult]:
        """Generic pattern checker for all pattern groups."""
        for pattern, name in self._compiled[group_name]:
            match = pattern.search(text)
            if match:
                # Handle regex groups differently based on pattern complexity
                if group_name == 'restart':
                    # Restarts have (abandoned, kept)
                    original = match.group(1)
                    corrected = match.group(2).strip()
                    ctype = CorrectionType.RESTART
                elif name == 'not_its':
                    # "not X, it's Y" has two groups: (X, Y)
                    original = match.group(1)  # X (the wrong value)
                    corrected = match.group(2).strip()  # Y (the correct value)
                    ctype = CorrectionType.FULL
                elif group_name in ['email_partial', 'phone_partial']:
                    # Partial corrections have (old_part, new_part)
                    original = match.group(1)
                    corrected = match.group(2).strip()
                    ctype = CorrectionType.PARTIAL
                else:
                    # Standard: Group 1 is the corrected value
                    corrected = match.group(1).strip()
                    original = text[:match.start()].strip()
                    ctype = CorrectionType.FULL
                
                # Confidence based on pattern type
                confidence = 0.95 if group_name == 'explicit_strong' else 0.90
                
                return CorrectionResult(
                    has_correction=True,
                    correction_type=ctype,
                    original_segment=original,
                    corrected_value=corrected,
                    final_value=corrected,
                    correction_marker=name,
                    confidence=confidence,
                    scope=scope,
                    pattern_matched=name
                )
        return None
    
    def _is_false_positive(self, text: str) -> bool:
        """Check if text matches false positive patterns."""
        for guard in self._false_positive_guards:
            if guard.search(text):
                logger.debug(f"False positive guard matched: {text}")
                return True
        return False
    
    def _check_nested_corrections(self, text: str) -> Optional[CorrectionResult]:
        """
        Check for nested/multiple corrections - take the last one.
        
        Example: "John... James... actually Jake" → Jake
        """
        markers = ['actually', 'oh sorry', 'i mean', 'no wait', 'wait', 'sorry', 'no its', 'no,']
        text_lower = text.lower()
        
        # Find LAST marker position
        last_marker_info = None
        for marker in markers:
            pos = text_lower.rfind(marker)
            if pos != -1:
                if last_marker_info is None or pos > last_marker_info[0]:
                    last_marker_info = (pos, marker)
        
        if last_marker_info:
            pos, marker = last_marker_info
            # Heuristic: If marker is very early, it might not be a nested correction chain
            if pos > 5:
                corrected = text[pos + len(marker):].strip()
                corrected = re.sub(r'^[,\s]+', '', corrected)
                if corrected:
                    return CorrectionResult(
                        has_correction=True,
                        correction_type=CorrectionType.NESTED,
                        original_segment=text[:pos].strip(),
                        corrected_value=corrected,
                        final_value=corrected,
                        correction_marker=marker,
                        confidence=0.92,
                        scope=CorrectionScope.FULL_VALUE,
                        pattern_matched='nested_last'
                    )
        return None
    
    def record_correction(self, result: CorrectionResult):
        """Record a correction for learning."""
        if result.has_correction:
            self._correction_history.append(result)
            # Keep last 100 corrections
            if len(self._correction_history) > 100:
                self._correction_history = self._correction_history[-100:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get detection statistics."""
        pattern_counts: Dict[str, int] = {}
        type_counts: Dict[str, int] = {}
        
        for result in self._correction_history:
            pattern = result.pattern_matched
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
            ctype = result.correction_type.value
            type_counts[ctype] = type_counts.get(ctype, 0) + 1
        
        return {
            'total_corrections': len(self._correction_history),
            'pattern_usage': pattern_counts,
            'by_type': type_counts,
        }


# Singleton instance
_detector_instance: Optional[CorrectionDetector] = None


def get_correction_detector() -> CorrectionDetector:
    """Get or create the correction detector singleton."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = CorrectionDetector()
    return _detector_instance
