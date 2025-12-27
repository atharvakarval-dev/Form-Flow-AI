"""
Base Normalizer

Abstract base class for all field-specific normalizers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple


@dataclass
class NormalizationResult:
    """Result from normalization."""
    value: str
    is_valid: bool
    confidence: float
    steps: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class BaseNormalizer(ABC):
    """
    Abstract base class for field-specific normalizers.
    
    All normalizers must implement:
    - normalize(): Transform raw input to normalized value
    - validate(): Check if value is valid for field type
    """
    
    @abstractmethod
    def normalize(
        self, 
        text: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Normalize text for this field type.
        
        Args:
            text: Raw input text
            context: Optional context dict
            
        Returns:
            Normalized text
        """
        pass
    
    @abstractmethod
    def validate(self, text: str) -> Tuple[bool, float]:
        """
        Validate normalized value.
        
        Args:
            text: Normalized value
            
        Returns:
            Tuple of (is_valid, confidence_score)
        """
        pass
    
    def process(
        self, 
        text: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> NormalizationResult:
        """
        Full processing pipeline: clean → normalize → validate.
        
        Args:
            text: Raw input text
            context: Optional context dict
            
        Returns:
            NormalizationResult with value, validity, confidence
        """
        steps = []
        
        # Clean input
        cleaned = self.clean_input(text)
        steps.append(f"Cleaned: '{text}' → '{cleaned}'")
        
        # Normalize
        normalized = self.normalize(cleaned, context)
        steps.append(f"Normalized: '{cleaned}' → '{normalized}'")
        
        # Validate
        is_valid, confidence = self.validate(normalized)
        steps.append(f"Validated: valid={is_valid}, confidence={confidence:.2f}")
        
        return NormalizationResult(
            value=normalized,
            is_valid=is_valid,
            confidence=confidence,
            steps=steps
        )
    
    def clean_input(self, text: str) -> str:
        """
        Common pre-processing for all normalizers.
        
        Args:
            text: Raw input
            
        Returns:
            Cleaned input
        """
        if not text:
            return ""
        return text.strip().lower()
    
    def strip_conversational_prefix(self, text: str, prefixes: List[str]) -> str:
        """
        Remove conversational prefixes from input.
        
        Args:
            text: Input text
            prefixes: List of regex patterns to remove
            
        Returns:
            Text with prefixes removed
        """
        import re
        result = text
        for prefix in prefixes:
            result = re.sub(prefix, '', result, flags=re.IGNORECASE)
        return result.strip()
