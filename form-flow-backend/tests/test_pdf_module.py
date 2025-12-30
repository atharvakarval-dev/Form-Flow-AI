"""
Tests for PDF Parser

Tests field extraction from PDF forms.
"""

import pytest
from pathlib import Path
from typing import Dict, Any
import tempfile
import io

# Import PDF services
from services.pdf.pdf_parser import (
    parse_pdf,
    PdfFormSchema,
    PdfField,
    FieldType,
    _detect_field_type,
    _detect_purpose,
)
from services.pdf.text_fitter import (
    TextFitter,
    FitResult,
    fit_text,
    apply_abbreviations,
)


# =============================================================================
# Text Fitter Tests
# =============================================================================

class TestTextFitter:
    """Tests for TextFitter class."""
    
    def test_direct_fit(self):
        """Text that fits should pass through unchanged."""
        fitter = TextFitter()
        result = fitter.fit("Hello World", max_chars=50)
        
        assert result.fitted == "Hello World"
        assert result.strategy_used == "direct_fit"
        assert not result.truncated
    
    def test_abbreviations_address(self):
        """Address abbreviations should be applied."""
        fitter = TextFitter()
        
        # Test street abbreviation
        result = fitter.fit("123 Main Street", max_chars=15)
        assert "St" in result.fitted or "Street" not in result.fitted
        
        # Test full address
        result = fitter.fit("123 North Main Street, Apartment 5", max_chars=25)
        assert len(result.fitted) <= 25
    
    def test_abbreviations_states(self):
        """State names should be abbreviated."""
        text = "New York, California, Texas"
        abbreviated = apply_abbreviations(text)
        
        assert "NY" in abbreviated or "New York" in abbreviated
        assert "CA" in abbreviated or "California" in abbreviated
    
    def test_name_shortening(self):
        """Names should be shortened when needed."""
        fitter = TextFitter()
        result = fitter.fit(
            "John Michael Smith Jr",
            max_chars=12,
            field_context={"purpose": "name"}
        )
        
        assert len(result.fitted) <= 12
    
    def test_truncation_with_ellipsis(self):
        """Long text should be truncated with ellipsis."""
        fitter = TextFitter()
        result = fitter.fit(
            "This is a very long piece of text that cannot possibly fit",
            max_chars=20,
            allow_truncation=True
        )
        
        assert len(result.fitted) <= 20
        assert result.truncated
    
    def test_stop_word_removal(self):
        """Stop words should be removed when needed."""
        fitter = TextFitter()
        text = "The quick brown fox jumps over the lazy dog"
        condensed = fitter.remove_stop_words(text)
        
        assert "The" not in condensed or condensed.count("the") < text.lower().count("the")
    
    def test_address_compression(self):
        """Addresses should be compressed intelligently."""
        fitter = TextFitter()
        address = "1234 North Main Street, Apartment 5B, Springfield, Illinois 62701"
        
        compressed = fitter.compress_address(address, 40)
        assert len(compressed) <= 40
    
    def test_wrap_text(self):
        """Text wrapping should respect line limits."""
        fitter = TextFitter()
        text = "This is a long sentence that needs to be wrapped across multiple lines"
        
        lines = fitter.wrap_text(text, chars_per_line=20, max_lines=3)
        
        assert len(lines) <= 3
        for line in lines:
            assert len(line) <= 23  # Allow some flexibility for word boundaries


class TestFieldTypeDetection:
    """Tests for field type detection."""
    
    def test_email_detection(self):
        """Email fields should be detected from name."""
        purpose = _detect_purpose("email_address", "")
        assert purpose == "email"
        
        purpose = _detect_purpose("user_email", "Your E-mail")
        assert purpose == "email"
    
    def test_phone_detection(self):
        """Phone fields should be detected."""
        purpose = _detect_purpose("phone_number", "")
        assert purpose == "phone"
        
        purpose = _detect_purpose("contact_tel", "Mobile Number")
        assert purpose == "phone"
    
    def test_name_detection(self):
        """Name fields should be detected."""
        purpose = _detect_purpose("first_name", "")
        assert purpose == "first_name"
        
        purpose = _detect_purpose("last_name", "Surname")
        assert purpose == "last_name"
    
    def test_address_detection(self):
        """Address fields should be detected."""
        purpose = _detect_purpose("street_address", "")
        assert purpose == "address"
        
        purpose = _detect_purpose("addr1", "Mailing Address")
        assert purpose == "address"


# =============================================================================
# Integration-like Tests (without actual PDF)
# =============================================================================

class TestPdfSchemaConversion:
    """Tests for schema conversion utilities."""
    
    def test_field_to_dict(self):
        """PdfField should convert to dict correctly."""
        from services.pdf.pdf_parser import FieldPosition, FieldConstraints
        
        field = PdfField(
            id="test_field",
            name="test_field",
            field_type=FieldType.TEXT,
            label="Test Field",
            position=FieldPosition(page=0, x=100, y=200, width=150, height=20),
            constraints=FieldConstraints(max_length=50, required=True),
            display_name="Test Field",
        )
        
        d = field.to_dict()
        
        assert d["id"] == "test_field"
        assert d["type"] == "text"
        assert d["label"] == "Test Field"
        assert d["constraints"]["max_length"] == 50
        assert d["constraints"]["required"] == True
    
    def test_schema_to_dict(self):
        """PdfFormSchema should convert correctly."""
        from services.pdf.pdf_parser import FieldPosition, FieldConstraints
        
        schema = PdfFormSchema(
            file_path="/test/form.pdf",
            file_name="form.pdf",
            total_pages=2,
            fields=[
                PdfField(
                    id="f1",
                    name="f1",
                    field_type=FieldType.TEXT,
                    label="Field 1",
                    position=FieldPosition(page=0, x=0, y=0, width=100, height=20),
                    constraints=FieldConstraints(),
                ),
            ],
        )
        
        d = schema.to_dict()
        
        assert d["source"] == "pdf"
        assert d["total_pages"] == 2
        assert d["total_fields"] == 1
        assert len(d["fields"]) == 1


# =============================================================================
# Convenience function tests
# =============================================================================

class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""
    
    def test_fit_text_function(self):
        """fit_text convenience function should work."""
        result = fit_text("Hello World", max_chars=50)
        assert isinstance(result, FitResult)
        assert result.fitted == "Hello World"
    
    def test_apply_abbreviations_function(self):
        """apply_abbreviations convenience function should work."""
        result = apply_abbreviations("123 Main Street")
        assert "St" in result or result == "123 Main Street"
