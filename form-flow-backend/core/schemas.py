"""
Pydantic Schemas Module

Defines request/response schemas for API endpoints.
Schemas are organized by domain: Auth, User, Form.

Usage:
    from core.schemas import UserCreate, UserResponse, Token
"""

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


# =============================================================================
# User Schemas
# =============================================================================

class UserBase(BaseModel):
    """
    Base user schema with common fields.
    
    Used as foundation for UserCreate and UserResponse.
    """
    email: EmailStr = Field(..., description="User's email address")
    first_name: Optional[str] = Field(None, max_length=100, description="First name")
    last_name: Optional[str] = Field(None, max_length=100, description="Last name")
    mobile: Optional[str] = Field(None, max_length=20, description="Phone number")
    country: Optional[str] = Field(None, max_length=100, description="Country")
    state: Optional[str] = Field(None, max_length=100, description="State/Province")
    city: Optional[str] = Field(None, max_length=100, description="City")
    pincode: Optional[str] = Field(None, max_length=20, description="Postal/ZIP code")


class UserCreate(UserBase):
    """
    Schema for user registration.
    
    Extends UserBase with password field.
    
    Example:
        {
            "email": "user@example.com",
            "password": "SecurePass123!",
            "first_name": "John",
            "last_name": "Doe"
        }
    """
    password: str = Field(
        ...,
        min_length=8,
        description="Password (min 8 characters)"
    )


class UserLogin(BaseModel):
    """
    Schema for user login.
    
    Example:
        {
            "email": "user@example.com",
            "password": "SecurePass123!"
        }
    """
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


# =============================================================================
# Form Submission Schemas
# =============================================================================

class FormSubmissionResponse(BaseModel):
    """
    Schema for form submission history response.
    
    Represents a single form submission record.
    """
    id: int = Field(..., description="Submission ID")
    form_url: str = Field(..., description="URL of the submitted form")
    status: str = Field(..., description="Submission status")
    timestamp: datetime = Field(..., description="Submission timestamp")
    
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# User Response Schemas
# =============================================================================

class UserResponse(UserBase):
    """
    Schema for user profile response.
    
    Returns user data with related submissions.
    Password is never included in responses.
    """
    id: int = Field(..., description="User ID")
    created_at: datetime = Field(..., description="Account creation timestamp")
    submissions: List[FormSubmissionResponse] = Field(
        default=[],
        description="User's form submission history"
    )
    
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Authentication Schemas
# =============================================================================

class Token(BaseModel):
    """
    Schema for JWT token response.
    
    Returned after successful login.
    
    Example:
        {
            "access_token": "eyJhbGciOiJIUzI1NiIs...",
            "token_type": "bearer"
        }
    """
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")


class TokenData(BaseModel):
    """
    Schema for decoded JWT token data.
    
    Used internally for token validation.
    """
    email: Optional[str] = Field(None, description="User email from token")


# =============================================================================
# Health Check Schemas
# =============================================================================

class HealthResponse(BaseModel):
    """
    Schema for health check endpoint response.
    """
    status: str = Field(..., description="Health status ('healthy' or 'unhealthy')")
    database: bool = Field(..., description="Database connection status")
    version: str = Field(..., description="Application version")
