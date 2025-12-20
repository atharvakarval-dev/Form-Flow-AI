"""
Authentication Router

Provides endpoints for user registration, login, and profile management.

Endpoints:
    POST /register - Create new user account
    POST /login - Authenticate and get JWT token
    GET /users/me - Get current user profile
    GET /history - Get user's form submission history
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from datetime import timedelta

from core import models, schemas, database
import auth as auth_utils
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Authentication & Users"])


# =============================================================================
# Registration
# =============================================================================

@router.post(
    "/register",
    response_model=schemas.UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    responses={
        201: {"description": "User created successfully"},
        400: {"description": "Email already registered"},
    }
)
async def register(
    user: schemas.UserCreate,
    db: AsyncSession = Depends(database.get_db)
):
    """
    Register a new user account.
    
    Creates a new user with the provided information. The password is
    securely hashed before storage. User profile fields (name, contact,
    location) are optional and used for auto-filling forms.
    
    Args:
        user: User registration data
        
    Returns:
        UserResponse: Created user profile (without password)
        
    Raises:
        HTTPException: 400 if email already registered
    """
    # Check if email exists
    result = await db.execute(
        select(models.User).filter(models.User.email == user.email)
    )
    existing_user = result.scalars().first()
    
    if existing_user:
        logger.warning(f"Registration attempt with existing email: {user.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user with hashed password
    hashed_password = auth_utils.get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        password_hash=hashed_password,
        first_name=user.first_name,
        last_name=user.last_name,
        mobile=user.mobile,
        country=user.country,
        state=user.state,
        city=user.city,
        pincode=user.pincode
    )
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    logger.info(f"New user registered: {user.email}")
    return db_user


# =============================================================================
# Login
# =============================================================================

@router.post(
    "/login",
    response_model=schemas.Token,
    summary="Login for access token",
    responses={
        200: {"description": "Login successful"},
        401: {"description": "Invalid credentials"},
    }
)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(database.get_db)
):
    """
    Authenticate user and return JWT access token.
    
    Accepts email as username and password. Returns a bearer token
    that must be included in the Authorization header for protected endpoints.
    
    Args:
        form_data: OAuth2 form with username (email) and password
        
    Returns:
        Token: JWT access token and token type
        
    Raises:
        HTTPException: 401 if credentials are invalid
        
    Example:
        ```
        POST /login
        Content-Type: application/x-www-form-urlencoded
        
        username=user@example.com&password=mypassword
        ```
    """
    # Find user by email
    result = await db.execute(
        select(models.User).filter(models.User.email == form_data.username)
    )
    user = result.scalars().first()
    
    # Verify credentials
    if not user or not auth_utils.verify_password(form_data.password, user.password_hash):
        logger.warning(f"Failed login attempt for: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(
        minutes=auth_utils.settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    access_token = auth_utils.create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )
    
    logger.info(f"User logged in: {user.email}")
    return {"access_token": access_token, "token_type": "bearer"}


# =============================================================================
# User Profile
# =============================================================================

@router.get(
    "/users/me",
    response_model=schemas.UserResponse,
    summary="Get current user profile",
    responses={
        200: {"description": "User profile retrieved"},
        401: {"description": "Not authenticated"},
    }
)
async def read_users_me(
    current_user: models.User = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(database.get_db)
):
    """
    Get the current authenticated user's profile.
    
    Returns full user profile including submission history.
    Requires valid JWT token in Authorization header.
    
    Returns:
        UserResponse: User profile with submissions
    """
    # Re-fetch user with submissions eagerly loaded
    result = await db.execute(
        select(models.User)
        .options(selectinload(models.User.submissions))
        .filter(models.User.id == current_user.id)
    )
    user = result.scalars().first()
    
    logger.debug(f"Profile accessed: {current_user.email}")
    return user


# =============================================================================
# Submission History
# =============================================================================

@router.get(
    "/history",
    response_model=List[schemas.FormSubmissionResponse],
    summary="Get submission history",
    responses={
        200: {"description": "History retrieved"},
        401: {"description": "Not authenticated"},
    }
)
async def get_history(
    current_user: models.User = Depends(auth_utils.get_current_user),
    db: AsyncSession = Depends(database.get_db)
):
    """
    Get the current user's form submission history.
    
    Returns list of all forms submitted by the user, ordered by
    submission time (newest first).
    
    Returns:
        List[FormSubmissionResponse]: List of form submissions
    """
    result = await db.execute(
        select(models.FormSubmission)
        .filter(models.FormSubmission.user_id == current_user.id)
        .order_by(models.FormSubmission.timestamp.desc())
    )
    submissions = result.scalars().all()
    
    logger.debug(f"History accessed: {current_user.email}, {len(submissions)} submissions")
    return submissions
