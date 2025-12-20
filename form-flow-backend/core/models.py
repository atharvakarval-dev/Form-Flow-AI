"""
Database Models Module

Defines SQLAlchemy ORM models for the application.
All models inherit from Base defined in database.py.

Models:
    - User: Application user with profile information
    - FormSubmission: Record of form submissions by users
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from typing import Optional, List

from .database import Base


class User(Base):
    """
    User model representing an application user.
    
    Stores authentication credentials and profile information
    used for auto-filling forms.
    
    Attributes:
        id: Primary key
        email: Unique email address (used for login)
        password_hash: Bcrypt hashed password
        first_name: User's first name
        last_name: User's last name
        mobile: Phone number
        country: Country of residence
        state: State/Province
        city: City
        pincode: Postal/ZIP code
        created_at: Account creation timestamp
        submissions: Related form submissions
    """
    
    __tablename__ = "users"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True)
    
    # Authentication
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    
    # Profile - Name
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    
    # Profile - Contact
    mobile = Column(String(20), nullable=True)
    
    # Profile - Location
    country = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    pincode = Column(String(20), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    submissions = relationship(
        "FormSubmission",
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<User(id={self.id}, email='{self.email}')>"
    
    @property
    def full_name(self) -> str:
        """Get user's full name."""
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p) or "Unknown"


class FormSubmission(Base):
    """
    Form submission model tracking user form submissions.
    
    Records each form that a user has submitted through the application,
    including the URL and submission status.
    
    Attributes:
        id: Primary key
        user_id: Foreign key to User (nullable for anonymous)
        form_url: URL of the submitted form
        status: Submission status (Success, Failed, Pending)
        timestamp: Submission timestamp
        user: Related User object
    """
    
    __tablename__ = "form_submissions"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign Key
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Submission Data
    form_url = Column(String(2048), nullable=False)
    status = Column(String(50), default="Success", index=True)
    
    # Timestamps (indexed for history queries)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    user = relationship("User", back_populates="submissions")
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<FormSubmission(id={self.id}, url='{self.form_url[:30]}...', status='{self.status}')>"
