"""
Unit Tests for URL Sanitization

Tests for input validation and sanitization utilities.
"""

import pytest
from utils.sanitize import (
    validate_form_url,
    is_google_form_url,
    sanitize_string,
    sanitize_field_name,
)
from utils.exceptions import FormValidationError


class TestURLValidation:
    """Tests for URL validation and sanitization."""
    
    def test_valid_https_url(self):
        """Valid HTTPS URL should pass validation."""
        url = "https://example.com/form"
        result = validate_form_url(url)
        assert result == url
    
    def test_valid_http_url(self):
        """Valid HTTP URL should pass validation."""
        url = "http://example.com/form"
        result = validate_form_url(url)
        assert result == url
    
    def test_google_form_url(self):
        """Google Form URL should pass validation."""
        url = "https://docs.google.com/forms/d/e/1FAIpQLSc_test/viewform"
        result = validate_form_url(url)
        assert result == url
    
    def test_strips_whitespace(self):
        """URL with whitespace should be stripped."""
        url = "  https://example.com/form  "
        result = validate_form_url(url)
        assert result == "https://example.com/form"
    
    def test_invalid_scheme_raises_error(self):
        """Invalid scheme (ftp, file) should raise error."""
        with pytest.raises(FormValidationError):
            validate_form_url("ftp://example.com/form")
        
        with pytest.raises(FormValidationError):
            validate_form_url("file:///etc/passwd")
    
    def test_localhost_blocked(self):
        """localhost URLs should be blocked (SSRF protection)."""
        with pytest.raises(FormValidationError):
            validate_form_url("http://localhost:8000/admin")
        
        with pytest.raises(FormValidationError):
            validate_form_url("http://127.0.0.1:8000/admin")
    
    def test_private_ip_blocked(self):
        """Private IP addresses should be blocked."""
        with pytest.raises(FormValidationError):
            validate_form_url("http://192.168.1.1/form")
        
        with pytest.raises(FormValidationError):
            validate_form_url("http://10.0.0.1/form")
    
    def test_aws_metadata_blocked(self):
        """AWS metadata endpoint should be blocked."""
        with pytest.raises(FormValidationError):
            validate_form_url("http://169.254.169.254/latest/meta-data")
    
    def test_empty_url_raises_error(self):
        """Empty URL should raise error."""
        with pytest.raises(FormValidationError):
            validate_form_url("")
        
        with pytest.raises(FormValidationError):
            validate_form_url(None)


class TestGoogleFormDetection:
    """Tests for Google Form URL detection."""
    
    def test_google_form_url_detected(self):
        """Standard Google Form URL should be detected."""
        url = "https://docs.google.com/forms/d/e/1FAIpQLSc_test/viewform"
        assert is_google_form_url(url) is True
    
    def test_forms_gle_url_detected(self):
        """Short Google Form URL (forms.gle) should be detected."""
        url = "https://forms.gle/abc123"
        assert is_google_form_url(url) is True
    
    def test_non_google_form_not_detected(self):
        """Non-Google Form URL should not be detected."""
        url = "https://typeform.com/myform"
        assert is_google_form_url(url) is False


class TestStringSanitization:
    """Tests for string sanitization."""
    
    def test_strips_whitespace(self):
        """Whitespace should be stripped."""
        assert sanitize_string("  hello  ") == "hello"
    
    def test_limits_length(self):
        """Long strings should be truncated."""
        long_string = "a" * 2000
        result = sanitize_string(long_string, max_length=100)
        assert len(result) == 100
    
    def test_strips_html_by_default(self):
        """HTML tags should be stripped by default."""
        result = sanitize_string("<script>alert('xss')</script>hello")
        assert "<script>" not in result
        assert "hello" in result
    
    def test_allows_html_when_specified(self):
        """HTML tags should be kept when allow_html=True."""
        result = sanitize_string("<b>hello</b>", allow_html=True)
        assert "<b>hello</b>" == result


class TestFieldNameSanitization:
    """Tests for field name sanitization."""
    
    def test_removes_dangerous_characters(self):
        """Dangerous characters should be removed."""
        result = sanitize_field_name('field<script>"name\'')
        assert "<" not in result
        assert ">" not in result
        assert '"' not in result
        assert "'" not in result
    
    def test_limits_length(self):
        """Field names should be limited to 200 characters."""
        long_name = "a" * 500
        result = sanitize_field_name(long_name)
        assert len(result) == 200
