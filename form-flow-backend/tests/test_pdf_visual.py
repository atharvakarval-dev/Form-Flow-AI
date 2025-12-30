
import pytest
from unittest.mock import MagicMock, patch, ANY
import io
from services.pdf.pdf_parser import _parse_visual_form, PdfField, FieldType

class TestVisualParser:
    """Tests for visual form parsing logic."""

    @patch('services.pdf.pdf_parser.pdfplumber.open')
    def test_visual_field_detection(self, mock_open):
        """Test detection of fields based on visual patterns."""
        
        # Mock PDF page with words
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.height = 800
        mock_page.width = 600
        
        # Simulate "Name: ____________" visual pattern
        # Words: "Name", ":", "_______"
        mock_words = [
            {'text': 'Name', 'x0': 50, 'x1': 100, 'top': 100, 'bottom': 114, 'height': 14},
            {'text': ':', 'x0': 100, 'x1': 105, 'top': 100, 'bottom': 114, 'height': 14},
            {'text': '__________', 'x0': 110, 'x1': 200, 'top': 110, 'bottom': 114, 'height': 4} # Underscore is lower
        ]
        
        mock_page.extract_words.return_value = mock_words
        mock_pdf.pages = [mock_page]
        mock_open.return_value = mock_pdf
        
        fields = _parse_visual_form("dummy.pdf")
        
        assert len(fields) == 1
        field = fields[0]
        assert field.label == "Name"
        assert field.field_type == FieldType.TEXT
        # Check generalized coordinate logic
        assert field.position.x >= 110 # Should start around the underscore
        assert field.position.y < 114 # Should be above the bottom line

    @patch('services.pdf.pdf_parser.pdfplumber.open')
    def test_visual_field_no_underscore(self, mock_open):
        """Test detection of "Label:" pattern without underscores."""
        
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.height = 800
        mock_page.width = 600
        
        mock_words = [
            {'text': 'Email', 'x0': 50, 'x1': 90, 'top': 200, 'bottom': 214, 'height': 14},
            {'text': ':', 'x0': 90, 'x1': 95, 'top': 200, 'bottom': 214, 'height': 14},
            # No underscores, just empty space implied
        ]
        
        mock_page.extract_words.return_value = mock_words
        mock_pdf.pages = [mock_page]
        mock_open.return_value = mock_pdf
        
        # We need to ensure the pattern matches. 
        # The current patterns expect underscores or similar.
        # If I want to support "Label:" with no underscores, I might need to verify the regex.
        # "Label: ____" is standard. "Label:" might be ignored if there are no underscores 
        # unless it matches a specific "Label:" pattern which might have been removed or kept.
        # Let's check the code... 
        # (r'^([A-Za-z][A-Za-z\s&/-]{2,50}):\s*$', 'text'), # "Label: "
        # This generic pattern exists!
        
        fields = _parse_visual_form("dummy.pdf")
        
        assert len(fields) == 1
        assert fields[0].label == "Email"
        assert fields[0].purpose == "email" # Should detect purpose
        
