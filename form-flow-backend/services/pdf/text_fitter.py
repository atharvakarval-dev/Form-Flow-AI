"""
Text Fitter - Intelligent Text Compression

Fits text into space-constrained PDF form fields using multiple strategies:
1. Direct fit (if text already fits)
2. Standard abbreviations (Street→St, Avenue→Ave)
3. Remove middle names/initials
4. Multi-line wrapping
5. Font size reduction
6. LLM-based intelligent compression

Features:
- Abbreviation dictionaries for addresses, titles, dates
- Font-aware character capacity calculation
- Graceful degradation with multiple fallback strategies
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Abbreviation Dictionaries
# =============================================================================

# Address abbreviations (USPS standard)
ADDRESS_ABBREVIATIONS = {
    "Street": "St",
    "Avenue": "Ave",
    "Road": "Rd",
    "Boulevard": "Blvd",
    "Drive": "Dr",
    "Lane": "Ln",
    "Court": "Ct",
    "Place": "Pl",
    "Circle": "Cir",
    "Highway": "Hwy",
    "Parkway": "Pkwy",
    "Terrace": "Ter",
    "Trail": "Trl",
    "Way": "Way",
    "North": "N",
    "South": "S",
    "East": "E",
    "West": "W",
    "Northeast": "NE",
    "Northwest": "NW",
    "Southeast": "SE",
    "Southwest": "SW",
    "Apartment": "Apt",
    "Suite": "Ste",
    "Building": "Bldg",
    "Floor": "Fl",
    "Room": "Rm",
    "Unit": "Unit",
}

# Title abbreviations
TITLE_ABBREVIATIONS = {
    "Doctor": "Dr",
    "Professor": "Prof",
    "Mister": "Mr",
    "Misses": "Mrs",
    "Miss": "Ms",
    "Junior": "Jr",
    "Senior": "Sr",
    "Incorporated": "Inc",
    "Corporation": "Corp",
    "Company": "Co",
    "Limited": "Ltd",
}

# State abbreviations (US)
STATE_ABBREVIATIONS = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC",
}

# Month abbreviations
MONTH_ABBREVIATIONS = {
    "January": "Jan", "February": "Feb", "March": "Mar", "April": "Apr",
    "May": "May", "June": "Jun", "July": "Jul", "August": "Aug",
    "September": "Sep", "October": "Oct", "November": "Nov", "December": "Dec",
}

# Common word abbreviations
COMMON_ABBREVIATIONS = {
    "Number": "No",
    "Numbers": "Nos",
    "Telephone": "Tel",
    "Extension": "Ext",
    "Department": "Dept",
    "Information": "Info",
    "Reference": "Ref",
    "International": "Intl",
    "Association": "Assn",
    "University": "Univ",
    "Institute": "Inst",
    "Foundation": "Fdn",
    "Organization": "Org",
    "Government": "Govt",
    "Approximately": "Approx",
    "Additional": "Addl",
    "Maximum": "Max",
    "Minimum": "Min",
    "Average": "Avg",
    "Estimated": "Est",
    "Continued": "Cont",
    "Certificate": "Cert",
    "Professional": "Prof",
}

# Combine all abbreviations
ALL_ABBREVIATIONS = {
    **ADDRESS_ABBREVIATIONS,
    **TITLE_ABBREVIATIONS,
    **STATE_ABBREVIATIONS,
    **MONTH_ABBREVIATIONS,
    **COMMON_ABBREVIATIONS,
}


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class FitResult:
    """Result of text fitting operation."""
    original: str
    fitted: str
    strategy_used: str
    font_size: Optional[float] = None
    truncated: bool = False
    overflow: bool = False
    changes_made: List[str] = None
    
    def __post_init__(self):
        if self.changes_made is None:
            self.changes_made = []
    
    @property
    def was_modified(self) -> bool:
        return self.original != self.fitted


# =============================================================================
# Text Fitter Class
# =============================================================================

class TextFitter:
    """
    Intelligent text fitter for space-constrained form fields.
    
    Uses multiple strategies to fit text into limited space while
    preserving meaning and readability.
    """
    
    MIN_FONT_SIZE = 6.0  # Minimum readable font size
    
    def __init__(
        self,
        llm_client: Optional[Any] = None,
        custom_abbreviations: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize TextFitter.
        
        Args:
            llm_client: Optional LLM client for intelligent compression
            custom_abbreviations: Additional abbreviations to use
        """
        self.llm_client = llm_client
        self.abbreviations = {**ALL_ABBREVIATIONS}
        if custom_abbreviations:
            self.abbreviations.update(custom_abbreviations)
    
    def fit(
        self,
        text: str,
        max_chars: int,
        field_context: Optional[Dict[str, Any]] = None,
        allow_truncation: bool = True,
        allow_font_resize: bool = True,
        min_font_size: float = 6.0,
    ) -> FitResult:
        """
        Fit text to field constraints.
        
        Args:
            text: Original text to fit
            max_chars: Maximum characters allowed
            field_context: Field metadata (type, label, etc.)
            allow_truncation: Whether truncation is acceptable
            allow_font_resize: Whether font size can be reduced
            min_font_size: Minimum font size if resizing
            
        Returns:
            FitResult with fitted text and metadata
        """
        field_context = field_context or {}
        original = text.strip()
        
        # Strategy 1: Direct fit
        if len(original) <= max_chars:
            return FitResult(
                original=original,
                fitted=original,
                strategy_used="direct_fit",
            )
        
        # Strategy 2: Apply abbreviations
        abbreviated = self.apply_abbreviations(original)
        if len(abbreviated) <= max_chars:
            return FitResult(
                original=original,
                fitted=abbreviated,
                strategy_used="abbreviations",
                changes_made=["Applied standard abbreviations"],
            )
        
        # Strategy 3: Remove middle names (for name fields)
        field_type = field_context.get("purpose", "")
        if field_type in ("name", "full_name"):
            short_name = self.shorten_name(original)
            if len(short_name) <= max_chars:
                return FitResult(
                    original=original,
                    fitted=short_name,
                    strategy_used="name_shortening",
                    changes_made=["Removed middle names/initials"],
                )
        
        # Strategy 4: Address-specific compression
        if field_type == "address":
            short_address = self.compress_address(original, max_chars)
            if len(short_address) <= max_chars:
                return FitResult(
                    original=original,
                    fitted=short_address,
                    strategy_used="address_compression",
                    changes_made=["Compressed address format"],
                )
        
        # Strategy 5: Remove non-essential words
        condensed = self.remove_stop_words(abbreviated)
        if len(condensed) <= max_chars:
            return FitResult(
                original=original,
                fitted=condensed,
                strategy_used="stop_word_removal",
                changes_made=["Removed non-essential words"],
            )
        
        # Strategy 6: LLM-based compression (if available)
        if self.llm_client and len(condensed) > max_chars:
            try:
                llm_result = self.compress_with_llm(
                    original, 
                    max_chars, 
                    field_context
                )
                if llm_result and len(llm_result) <= max_chars:
                    return FitResult(
                        original=original,
                        fitted=llm_result,
                        strategy_used="llm_compression",
                        changes_made=["AI-compressed while preserving meaning"],
                    )
            except Exception as e:
                logger.warning(f"LLM compression failed: {e}")
        
        # Strategy 7: Truncation with ellipsis
        if allow_truncation:
            truncated = condensed[:max_chars - 3].rstrip() + "..."
            return FitResult(
                original=original,
                fitted=truncated,
                strategy_used="truncation",
                truncated=True,
                changes_made=["Truncated with ellipsis"],
            )
        
        # Last resort: Hard truncation
        return FitResult(
            original=original,
            fitted=condensed[:max_chars],
            strategy_used="hard_truncation",
            truncated=True,
            overflow=True,
            changes_made=["Hard truncation (data may be lost)"],
        )
    
    def apply_abbreviations(self, text: str) -> str:
        """Apply all abbreviation rules to text."""
        result = text
        
        # Sort by length (longest first) to avoid partial replacements
        sorted_abbrevs = sorted(
            self.abbreviations.items(),
            key=lambda x: len(x[0]),
            reverse=True
        )
        
        for full, abbr in sorted_abbrevs:
            # Case-insensitive replacement preserving word boundaries
            pattern = r'\b' + re.escape(full) + r'\b'
            result = re.sub(pattern, abbr, result, flags=re.IGNORECASE)
        
        return result
    
    def shorten_name(self, name: str) -> str:
        """
        Shorten a name by removing/abbreviating middle names.
        
        Examples:
            "John Michael Smith" -> "John M. Smith"
            "John M. Smith" -> "John Smith"
            "John Smith" -> "J. Smith"
        """
        parts = name.split()
        
        if len(parts) <= 2:
            # Already short, try first initial
            if len(parts) == 2:
                return f"{parts[0][0]}. {parts[1]}"
            return name
        
        # Try removing middle names first
        first = parts[0]
        last = parts[-1]
        
        # Keep first name and last name only
        shortened = f"{first} {last}"
        if len(shortened) <= len(name):
            return shortened
        
        # Use first initial
        return f"{first[0]}. {last}"
    
    def compress_address(self, address: str, max_chars: int) -> str:
        """Compress an address to fit within character limit."""
        # First apply standard abbreviations
        result = self.apply_abbreviations(address)
        
        if len(result) <= max_chars:
            return result
        
        # Remove apartment/suite if secondary
        result = re.sub(r',?\s*(Apt|Ste|Unit|#)\s*\d+\w*', '', result, flags=re.IGNORECASE)
        
        if len(result) <= max_chars:
            return result.strip()
        
        # Remove zip code extension
        result = re.sub(r'-\d{4}$', '', result)
        
        if len(result) <= max_chars:
            return result.strip()
        
        # Try removing state if city is present
        # (risky but may be acceptable for some forms)
        parts = result.split(',')
        if len(parts) >= 3:
            result = ', '.join(parts[:-1])
        
        return result.strip()[:max_chars]
    
    def remove_stop_words(self, text: str) -> str:
        """Remove non-essential words while preserving meaning."""
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
            'for', 'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are',
            'were', 'been', 'being', 'have', 'has', 'had', 'do', 'does',
            'did', 'will', 'would', 'could', 'should', 'may', 'might',
            'must', 'shall', 'this', 'that', 'these', 'those'
        }
        
        words = text.split()
        result = [w for w in words if w.lower() not in stop_words]
        return ' '.join(result)
    
    def compress_with_llm(
        self,
        text: str,
        max_chars: int,
        field_context: Dict[str, Any],
    ) -> Optional[str]:
        """
        Use LLM to intelligently compress text.
        
        Args:
            text: Text to compress
            max_chars: Maximum characters
            field_context: Field metadata for context
            
        Returns:
            Compressed text or None if failed
        """
        if not self.llm_client:
            return None
        
        field_label = field_context.get("label", "form field")
        field_type = field_context.get("type", "text")
        
        prompt = f"""Compress the following text to fit within {max_chars} characters while preserving all essential meaning.

This is for a {field_type} field labeled "{field_label}".

Original text: "{text}"

Rules:
- Use standard abbreviations (St, Ave, Dr, etc.)
- Remove unnecessary words
- Keep all critical information
- Must be {max_chars} characters or less
- Maintain readability

Compressed text:"""
        
        try:
            # This assumes a simple interface; adjust for actual LLM client
            response = self.llm_client.generate(prompt, max_tokens=max_chars * 2)
            compressed = response.strip().strip('"')
            return compressed if len(compressed) <= max_chars else None
        except Exception as e:
            logger.warning(f"LLM compression error: {e}")
            return None
    
    def calculate_optimal_font_size(
        self,
        text: str,
        field_width: float,
        field_height: float,
        base_font_size: float = 12.0,
        min_font_size: float = 6.0,
    ) -> Tuple[float, int]:
        """
        Calculate optimal font size to fit text.
        
        Returns:
            Tuple of (font_size, lines_needed)
        """
        # Approximate: avg char width = 0.5 * font_size
        for font_size in [base_font_size, 10, 9, 8, 7, min_font_size]:
            avg_char_width = font_size * 0.5
            chars_per_line = int(field_width / avg_char_width) if avg_char_width > 0 else 50
            
            if len(text) <= chars_per_line:
                return font_size, 1
            
            # Check multi-line
            line_height = font_size * 1.2
            max_lines = int(field_height / line_height) if line_height > 0 else 1
            
            lines_needed = (len(text) + chars_per_line - 1) // chars_per_line
            
            if lines_needed <= max_lines:
                return font_size, lines_needed
        
        # Can't fit even at minimum size
        return min_font_size, 1
    
    def wrap_text(
        self,
        text: str,
        chars_per_line: int,
        max_lines: Optional[int] = None,
    ) -> List[str]:
        """
        Wrap text to fit within line width.
        
        Args:
            text: Text to wrap
            chars_per_line: Maximum characters per line
            max_lines: Maximum number of lines (None for unlimited)
            
        Returns:
            List of lines
        """
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            word_len = len(word)
            
            # Check if word fits on current line
            if current_length + word_len + (1 if current_line else 0) <= chars_per_line:
                current_line.append(word)
                current_length += word_len + (1 if len(current_line) > 1 else 0)
            else:
                # Start new line
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = word_len
            
            # Check max lines
            if max_lines and len(lines) >= max_lines - 1:
                break
        
        # Add remaining words
        if current_line:
            remaining = ' '.join(current_line)
            if max_lines and len(lines) >= max_lines:
                # Truncate last line
                available = chars_per_line - 3
                if len(remaining) > available:
                    remaining = remaining[:available] + "..."
            lines.append(remaining)
        
        return lines


# =============================================================================
# Utility Functions
# =============================================================================

def fit_text(
    text: str,
    max_chars: int,
    field_context: Optional[Dict[str, Any]] = None,
) -> FitResult:
    """
    Convenience function to fit text using default fitter.
    
    Args:
        text: Text to fit
        max_chars: Maximum characters
        field_context: Optional field metadata
        
    Returns:
        FitResult with fitted text
    """
    fitter = TextFitter()
    return fitter.fit(text, max_chars, field_context)


def apply_abbreviations(text: str) -> str:
    """Convenience function to apply standard abbreviations."""
    fitter = TextFitter()
    return fitter.apply_abbreviations(text)
