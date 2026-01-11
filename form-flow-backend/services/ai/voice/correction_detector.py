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
- Learning from user patterns
"""

import re
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

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
    FULL_VALUE = "full_value"       # Entire value replaced
    EMAIL_DOMAIN = "email_domain"   # Just the domain part
    EMAIL_LOCAL = "email_local"     # Just the local part
    PHONE_PREFIX = "phone_prefix"   # Country/area code
    PHONE_SUFFIX = "phone_suffix"   # Last digits
    NAME_FIRST = "name_first"       # First name only
    NAME_LAST = "name_last"         # Last name only
    UNKNOWN = "unknown"


@dataclass
class FieldContext:
    """Context about the field being filled."""
    field_type: str = "text"
    field_name: str = ""
    field_label: str = ""
    current_value: str = ""  # Value before this input
    

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


class CorrectionDetector:
    """
    World-class real-time correction detection.
    
    Detects inline corrections in voice input and extracts the corrected value.
    Handles explicit corrections ("actually"), negations ("not X, it's Y"),
    restarts ("j... james"), and partial corrections ("@gmail... @yahoo").
    """
    
    # =========================================================================
    # CORRECTION TRIGGER PATTERNS
    # Ordered by priority - first match wins
    # =========================================================================
    
    # Priority 1: Explicit strong correction markers
    EXPLICIT_STRONG_PATTERNS = [
        # "let me correct that, X" / "correction: X"  
        (r'let\s+me\s+correct(?:\s+that)?[,:\s]+(.+)$', 'let_me_correct'),
        (r'correction[:\s]+(.+)$', 'correction'),
        # "actually X" at word boundary
        (r'\bactually[,\s]+(.+)$', 'actually'),
        # "scratch that, X"
        (r'scratch\s+that[,\s]+(.+)$', 'scratch_that'),
    ]
    
    # Priority 2: Medium strength correction markers
    EXPLICIT_MEDIUM_PATTERNS = [
        # "oh sorry, its X" / "oh sorry its X" - COMMON in natural speech!
        (r'\boh\s+sorry[,\s]+(?:it\'?s\s+|its\s+)?(.+)$', 'oh_sorry'),
        # "sorry, it's X" / "sorry its X"
        (r'\bsorry[,\s]+(?:it\'?s\s+|its\s+)(.+)$', 'sorry_its'),
        # "sorry, X" / "oops, X" / "my bad, X"
        (r'(?:sorry|oops|my\s+bad)[,\s]+(.+)$', 'sorry'),
        # "I mean X" / "I meant X" (with optional "its")
        (r'\bi\s+mean[t]?[,\s]+(?:it\'?s\s+|its\s+)?(.+)$', 'i_mean'),
        # "no wait, X" / "wait, X" (with optional "its")
        (r'(?:no\s+)?wait[,\s]+(?:it\'?s\s+|its\s+)?(.+)$', 'no_wait'),
        # "rather X" / "or rather X"
        (r'(?:or\s+)?rather[,\s]+(.+)$', 'rather'),
        # "make that X"
        (r'make\s+that[,\s]+(.+)$', 'make_that'),
        # "change that to X"
        (r'change\s+(?:that|it)\s+to[,\s]+(.+)$', 'change_to'),
    ]
    
    # Priority 3: Negation patterns  
    NEGATION_PATTERNS = [
        # "no its X" / "no it's X" - VERY COMMON!
        (r'\bno[,\s]+(?:it\'?s|its)\s+(.+)$', 'no_its'),
        # "no it is X" - slightly different pattern
        (r'\bno[,\s]+it\s+is\s+(.+)$', 'no_it_is'),
        # "not X, it's Y" / "not X, its Y"
        (r'not\s+(\S+)[,\s]+(?:it\'?s|its|it\s+is)\s+(.+)$', 'not_its'),
        # "no, X" / "nope, X" (fallback - not followed by problem/worries/etc)
        (r'^(?:no|nope)[,\s]+(?!problem|worries|thanks|thank|issue|way)(.+)$', 'no_value'),
    ]
    
    # Priority 4: Restart patterns (abandoned starts)
    RESTART_PATTERNS = [
        # "j... james" (1-3 chars followed by ellipsis)
        (r'(\w{1,3})\.{2,}\s*(\w{2,}.*)$', 'abandoned_start'),
        # "jo- james" (hyphen interruption)
        (r'(\w{1,4})-\s*(\w{2,}.*)$', 'hyphen_restart'),
    ]
    
    # Priority 5: Partial correction patterns (field-type specific)
    PARTIAL_EMAIL_PATTERNS = [
        # "@gmail... @yahoo" or "at gmail... at yahoo"
        (r'(?:@|at\s+)(\w+)[,.\s]+(?:actually|no|I\s+mean)[,\s]+(?:@|at\s+)?(\w+)', 'email_domain'),
    ]
    
    PARTIAL_PHONE_PATTERNS = [
        # "1234... 4321" (suffix correction)
        (r'(\d{3,})[,.\s]+(?:actually|no|I\s+mean|wait)[,\s]+(\d{3,})$', 'phone_suffix'),
    ]
    
    # Words that look like corrections but shouldn't trigger
    FALSE_POSITIVE_GUARDS = [
        # "Actually" as company name
        r'\bactually\s+(?:inc|llc|ltd|corp|co\.?)\b',
        # "No" in expected phrases
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
    
    def detect(
        self, 
        text: str, 
        field_context: Optional[FieldContext] = None
    ) -> CorrectionResult:
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
        
        # Check patterns in priority order
        result = self._check_explicit_strong(text, field_context)
        if result.has_correction:
            return result
        
        result = self._check_explicit_medium(text, field_context)
        if result.has_correction:
            return result
        
        result = self._check_negation(text, field_context)
        if result.has_correction:
            return result
        
        # Check partial corrections based on field type
        if field_context.field_type in ['email', 'e-mail']:
            result = self._check_email_partial(text, field_context)
            if result.has_correction:
                return result
        
        if field_context.field_type in ['tel', 'phone', 'mobile']:
            result = self._check_phone_partial(text, field_context)
            if result.has_correction:
                return result
        
        # Check restart patterns
        result = self._check_restart(text, field_context)
        if result.has_correction:
            return result
        
        # Check for nested/multiple corrections
        result = self._check_nested_corrections(text, field_context)
        if result.has_correction:
            return result
        
        # No correction detected
        return CorrectionResult(final_value=text)
    
    def _is_false_positive(self, text: str) -> bool:
        """Check if text matches false positive patterns."""
        for guard in self._false_positive_guards:
            if guard.search(text):
                logger.debug(f"False positive guard matched: {text}")
                return True
        return False
    
    def _check_explicit_strong(self, text: str, ctx: FieldContext) -> CorrectionResult:
        """Check for strong explicit correction markers."""
        for pattern, name in self._compiled['explicit_strong']:
            match = pattern.search(text)
            if match:
                corrected = match.group(1).strip()
                original = text[:match.start()].strip()
                
                return CorrectionResult(
                    has_correction=True,
                    correction_type=CorrectionType.FULL,
                    original_segment=original,
                    corrected_value=corrected,
                    final_value=corrected,
                    correction_marker=name,
                    confidence=0.95,
                    scope=CorrectionScope.FULL_VALUE,
                    pattern_matched=name
                )
        return CorrectionResult()
    
    def _check_explicit_medium(self, text: str, ctx: FieldContext) -> CorrectionResult:
        """Check for medium strength correction markers."""
        for pattern, name in self._compiled['explicit_medium']:
            match = pattern.search(text)
            if match:
                corrected = match.group(1).strip()
                original = text[:match.start()].strip()
                
                return CorrectionResult(
                    has_correction=True,
                    correction_type=CorrectionType.FULL,
                    original_segment=original,
                    corrected_value=corrected,
                    final_value=corrected,
                    correction_marker=name,
                    confidence=0.90,
                    scope=CorrectionScope.FULL_VALUE,
                    pattern_matched=name
                )
        return CorrectionResult()
    
    def _check_negation(self, text: str, ctx: FieldContext) -> CorrectionResult:
        """Check for negation patterns."""
        for pattern, name in self._compiled['negation']:
            match = pattern.search(text)
            if match:
                groups = match.groups()
                
                if name == 'not_its':
                    # "not X, it's Y" - groups are (X, Y)
                    original = groups[0]
                    corrected = groups[1].strip()
                else:
                    # "no, X" - single group
                    corrected = groups[0].strip()
                    original = ""
                
                return CorrectionResult(
                    has_correction=True,
                    correction_type=CorrectionType.FULL,
                    original_segment=original,
                    corrected_value=corrected,
                    final_value=corrected,
                    correction_marker=name,
                    confidence=0.88,
                    scope=CorrectionScope.FULL_VALUE,
                    pattern_matched=name
                )
        return CorrectionResult()
    
    def _check_restart(self, text: str, ctx: FieldContext) -> CorrectionResult:
        """Check for restart patterns (abandoned starts)."""
        for pattern, name in self._compiled['restart']:
            match = pattern.search(text)
            if match:
                abandoned = match.group(1)
                completed = match.group(2).strip()
                
                # Verify the completed value starts similarly (it's a restart, not two values)
                if completed.lower().startswith(abandoned.lower()[:1]):
                    return CorrectionResult(
                        has_correction=True,
                        correction_type=CorrectionType.RESTART,
                        original_segment=abandoned,
                        corrected_value=completed,
                        final_value=completed,
                        correction_marker=name,
                        confidence=0.80,
                        scope=CorrectionScope.FULL_VALUE,
                        pattern_matched=name
                    )
        return CorrectionResult()
    
    def _check_email_partial(self, text: str, ctx: FieldContext) -> CorrectionResult:
        """Check for partial email corrections (domain changes)."""
        for pattern, name in self._compiled['email_partial']:
            match = pattern.search(text)
            if match:
                old_domain = match.group(1)
                new_domain = match.group(2)
                
                # Extract the local part (before the correction)
                before_match = text[:match.start()].strip()
                local_part = self._extract_email_local(before_match)
                
                if local_part:
                    # Construct corrected email
                    corrected_email = f"{local_part}@{new_domain}.com"
                    
                    return CorrectionResult(
                        has_correction=True,
                        correction_type=CorrectionType.PARTIAL,
                        original_segment=f"@{old_domain}",
                        corrected_value=f"@{new_domain}",
                        final_value=corrected_email,
                        correction_marker=name,
                        confidence=0.85,
                        scope=CorrectionScope.EMAIL_DOMAIN,
                        pattern_matched=name
                    )
        return CorrectionResult()
    
    def _check_phone_partial(self, text: str, ctx: FieldContext) -> CorrectionResult:
        """Check for partial phone corrections (suffix changes)."""
        for pattern, name in self._compiled['phone_partial']:
            match = pattern.search(text)
            if match:
                old_suffix = match.group(1)
                new_suffix = match.group(2)
                
                # Get prefix from context or extract from text
                prefix = self._extract_phone_prefix(text[:match.start()], ctx)
                
                if prefix:
                    corrected_phone = prefix + new_suffix
                    return CorrectionResult(
                        has_correction=True,
                        correction_type=CorrectionType.PARTIAL,
                        original_segment=old_suffix,
                        corrected_value=new_suffix,
                        final_value=corrected_phone,
                        correction_marker=name,
                        confidence=0.85,
                        scope=CorrectionScope.PHONE_SUFFIX,
                        pattern_matched=name
                    )
        return CorrectionResult()
    
    def _check_nested_corrections(self, text: str, ctx: FieldContext) -> CorrectionResult:
        """
        Check for nested/multiple corrections - take the last one.
        
        Example: "John... James... actually Jake" → Jake
        """
        # Count correction markers (including 'oh sorry')
        markers = ['actually', 'oh sorry', 'i mean', 'no wait', 'wait', 'sorry', 'no its', 'no,']
        marker_positions = []
        
        text_lower = text.lower()
        for marker in markers:
            pos = text_lower.rfind(marker)  # Find LAST occurrence
            if pos != -1:
                marker_positions.append((pos, marker))
        
        if len(marker_positions) >= 2:
            # Multiple corrections - use the last one
            marker_positions.sort(key=lambda x: x[0], reverse=True)
            last_pos, last_marker = marker_positions[0]
            
            # Extract value after last marker
            after_marker = text[last_pos + len(last_marker):].strip()
            # Clean up leading punctuation/whitespace
            after_marker = re.sub(r'^[,\s]+', '', after_marker)
            
            if after_marker:
                return CorrectionResult(
                    has_correction=True,
                    correction_type=CorrectionType.NESTED,
                    original_segment=text[:last_pos].strip(),
                    corrected_value=after_marker,
                    final_value=after_marker,
                    correction_marker=last_marker,
                    confidence=0.92,  # High confidence when multiple corrections
                    scope=CorrectionScope.FULL_VALUE,
                    pattern_matched='nested_last'
                )
        
        return CorrectionResult()
    
    def _extract_email_local(self, text: str) -> Optional[str]:
        """Extract email local part from text."""
        # Look for email-like patterns
        patterns = [
            r'([a-zA-Z0-9._+-]+)\s*(?:@|at)',
            r'(?:email\s+(?:is\s+)?)?([a-zA-Z0-9._+-]+)\s*$',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).lower()
        
        # Fallback: take last word-like segment
        words = text.split()
        if words:
            last = words[-1].strip('.,!?')
            if re.match(r'^[a-zA-Z0-9._+-]+$', last):
                return last.lower()
        
        return None
    
    def _extract_phone_prefix(self, text: str, ctx: FieldContext) -> Optional[str]:
        """Extract phone prefix from text or context."""
        # First try context
        if ctx.current_value:
            digits = re.sub(r'\D', '', ctx.current_value)
            if len(digits) >= 6:
                return digits[:-4]  # All but last 4 digits
        
        # Extract from text
        digits = re.sub(r'\D', '', text)
        if len(digits) >= 6:
            return digits[:6]  # First 6 digits as prefix
        
        return None
    
    def record_correction(self, result: CorrectionResult):
        """Record a correction for learning."""
        if result.has_correction:
            self._correction_history.append(result)
            # Keep last 100 corrections
            if len(self._correction_history) > 100:
                self._correction_history = self._correction_history[-100:]
    
    def get_user_patterns(self) -> Dict[str, int]:
        """Get statistics on user's correction patterns."""
        pattern_counts: Dict[str, int] = {}
        for result in self._correction_history:
            pattern = result.pattern_matched
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
        return pattern_counts
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get detection statistics."""
        return {
            'total_corrections': len(self._correction_history),
            'pattern_usage': self.get_user_patterns(),
            'by_type': self._count_by_type(),
        }
    
    def _count_by_type(self) -> Dict[str, int]:
        """Count corrections by type."""
        counts: Dict[str, int] = {}
        for result in self._correction_history:
            ctype = result.correction_type.value
            counts[ctype] = counts.get(ctype, 0) + 1
        return counts


# Singleton instance
_detector_instance: Optional[CorrectionDetector] = None


def get_correction_detector() -> CorrectionDetector:
    """Get or create the correction detector singleton."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = CorrectionDetector()
    return _detector_instance
