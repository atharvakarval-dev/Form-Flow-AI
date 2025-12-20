"""
Unit Tests for Authentication

Tests for auth utilities and authentication endpoints.
"""

import pytest
from auth import get_password_hash, verify_password, create_access_token, decode_access_token


class TestPasswordHashing:
    """Tests for password hashing utilities."""
    
    def test_password_hash_creates_different_hashes(self):
        """Same password should create different hashes each time."""
        password = "test_password_123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        assert hash1 != hash2
        assert hash1 != password
    
    def test_verify_password_correct(self):
        """Correct password should verify successfully."""
        password = "my_secret_password"
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Incorrect password should fail verification."""
        password = "correct_password"
        hashed = get_password_hash(password)
        
        assert verify_password("wrong_password", hashed) is False


class TestJWTTokens:
    """Tests for JWT token utilities."""
    
    def test_create_and_decode_token(self):
        """Token should encode and decode correctly."""
        data = {"sub": "test@example.com"}
        token = create_access_token(data)
        
        decoded = decode_access_token(token)
        
        assert decoded is not None
        assert decoded["sub"] == "test@example.com"
        assert "exp" in decoded
    
    def test_invalid_token_returns_none(self):
        """Invalid token should return None."""
        result = decode_access_token("invalid.token.here")
        
        assert result is None
    
    def test_empty_token_returns_none(self):
        """Empty token should return None."""
        result = decode_access_token("")
        
        assert result is None
