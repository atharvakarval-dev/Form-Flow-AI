"""
Authentication Utilities Module

Provides password hashing, JWT token management, and user authentication.
Uses bcrypt for password hashing and python-jose for JWT.

Usage:
    from auth import verify_password, get_password_hash, create_access_token
    
    # Hash a password
    hashed = get_password_hash("my_password")
    
    # Verify a password
    if verify_password("my_password", hashed):
        token = create_access_token({"sub": user.email})
"""

from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from config.settings import settings
from core import schemas, models, database
from utils.logging import get_logger
from utils.exceptions import AuthenticationError

logger = get_logger(__name__)

# OAuth2 scheme for token extraction from Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# =============================================================================
# Password Hashing
# =============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.
    
    Args:
        plain_password: The plain text password to verify
        hashed_password: The bcrypt hashed password to compare against
        
    Returns:
        bool: True if password matches, False otherwise
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception as e:
        logger.error(f"Password verification failed: {e}")
        return False


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password to hash
        
    Returns:
        str: Bcrypt hashed password
        
    Note:
        Uses default bcrypt salt rounds (12).
        For production, consider increasing to 14+ for better security.
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


# =============================================================================
# JWT Token Management
# =============================================================================

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Payload data to encode in the token.
              Should include "sub" (subject) with user identifier.
        expires_delta: Optional custom expiration time.
                       Defaults to ACCESS_TOKEN_EXPIRE_MINUTES from settings.
    
    Returns:
        str: Encoded JWT token
        
    Example:
        token = create_access_token(
            data={"sub": user.email},
            expires_delta=timedelta(hours=24)
        )
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT access token.
    
    Args:
        token: JWT token string
        
    Returns:
        dict: Decoded token payload, or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None


# =============================================================================
# User Authentication Dependencies
# =============================================================================

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(database.get_db)
) -> models.User:
    """
    FastAPI dependency to get the current authenticated user.
    
    Extracts and validates the JWT token from the Authorization header,
    then fetches the corresponding user from the database.
    
    Args:
        token: JWT token from Authorization header (injected)
        db: Database session (injected)
        
    Returns:
        User: Authenticated user model instance
        
    Raises:
        HTTPException: 401 if token is invalid or user not found
        
    Usage:
        @router.get("/me")
        async def get_me(user: User = Depends(get_current_user)):
            return user
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        email: str = payload.get("sub")
        
        if email is None:
            logger.warning("Token missing 'sub' claim")
            raise credentials_exception
            
        token_data = schemas.TokenData(email=email)
        
    except JWTError as e:
        logger.warning(f"JWT decode failed: {e}")
        raise credentials_exception
    
    # Fetch user from database
    result = await db.execute(
        select(models.User).filter(models.User.email == token_data.email)
    )
    user = result.scalars().first()
    
    if user is None:
        logger.warning(f"User not found for email: {token_data.email}")
        raise credentials_exception
    
    return user


async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(database.get_db)
) -> Optional[models.User]:
    """
    Optional version of get_current_user that returns None for unauthenticated requests.
    
    Useful for endpoints that work for both authenticated and anonymous users.
    
    Returns:
        Optional[User]: User if authenticated, None otherwise
    """
    if not token:
        return None
    
    try:
        return await get_current_user(token, db)
    except HTTPException:
        return None
