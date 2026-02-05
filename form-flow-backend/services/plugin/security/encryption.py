"""
Encryption Service Module

Centralized encryption service using Fernet symmetric encryption.
Singleton pattern ensures key derivation happens once.

Features:
- Fernet encryption (AES-128-CBC with HMAC-SHA256)
- Key derived from SECRET_KEY
- Thread-safe singleton instance
"""

import hashlib
import base64
import json
from typing import Dict, Any, Optional
from functools import lru_cache
from cryptography.fernet import Fernet, InvalidToken

from config.settings import settings
from utils.logging import get_logger

logger = get_logger(__name__)


class EncryptionService:
    """
    Fernet-based encryption service.
    
    Uses singleton pattern to avoid repeated key derivation.
    All operations are synchronous (crypto is CPU-bound).
    
    Usage:
        service = get_encryption_service()
        encrypted = service.encrypt({"password": "secret"})
        decrypted = service.decrypt(encrypted)
    """
    
    def __init__(self, secret_key: str):
        """Initialize with secret key for key derivation."""
        # Derive 32-byte key from secret using SHA-256
        derived_key = hashlib.sha256(secret_key.encode()).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(derived_key))
    
    def encrypt(self, data: Dict[str, Any]) -> str:
        """
        Encrypt a dictionary to a string.
        
        Args:
            data: Dictionary to encrypt
            
        Returns:
            Base64-encoded encrypted string
        """
        plaintext = json.dumps(data, separators=(',', ':'))  # Compact JSON
        return self._fernet.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, encrypted: str) -> Dict[str, Any]:
        """
        Decrypt a string back to dictionary.
        
        Args:
            encrypted: Encrypted string from encrypt()
            
        Returns:
            Original dictionary
            
        Raises:
            ValueError: If decryption fails (invalid token or corrupted)
        """
        try:
            plaintext = self._fernet.decrypt(encrypted.encode())
            return json.loads(plaintext)
        except InvalidToken:
            logger.error("Decryption failed: invalid token")
            raise ValueError("Decryption failed: invalid or corrupted data")
        except json.JSONDecodeError:
            logger.error("Decryption failed: invalid JSON")
            raise ValueError("Decryption failed: corrupted data")
    
    def encrypt_string(self, plaintext: str) -> str:
        """Encrypt a plain string."""
        return self._fernet.encrypt(plaintext.encode()).decode()
    
    def decrypt_string(self, encrypted: str) -> str:
        """Decrypt to plain string."""
        try:
            return self._fernet.decrypt(encrypted.encode()).decode()
        except InvalidToken:
            raise ValueError("Decryption failed: invalid or corrupted data")


@lru_cache(maxsize=1)
def get_encryption_service() -> EncryptionService:
    """
    Get singleton encryption service.
    
    Cached to ensure key derivation happens only once.
    """
    return EncryptionService(settings.SECRET_KEY)
