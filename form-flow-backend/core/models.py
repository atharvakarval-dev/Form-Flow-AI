"""
Database Models Module

Defines SQLAlchemy ORM models for the application.
All models inherit from Base defined in database.py.

Models:
    - User: Application user with profile information
    - UserProfile: Behavioral profile for personalized suggestions
    - FormSubmission: Record of form submissions by users
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Boolean
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
        profiling_enabled: Whether behavioral profiling is enabled
        created_at: Account creation timestamp
        submissions: Related form submissions
        behavioral_profile: Related behavioral profile
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
    
    # Privacy Settings
    profiling_enabled = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    submissions = relationship(
        "FormSubmission",
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    behavioral_profile = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False,
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


class UserProfile(Base):
    """
    Behavioral profile model for personalized form suggestions.
    
    Stores LLM-generated psychological/behavioral insights extracted from
    user's form interactions. Used to provide intelligent, personalized
    suggestions that match user's decision-making style.
    
    Attributes:
        id: Primary key
        user_id: Foreign key to User (one-to-one)
        profile_text: LLM-generated behavioral summary (max 500 words)
        confidence_score: Profile reliability (0.0-1.0)
        form_count: Number of forms analyzed
        version: Profile evolution version
        metadata_json: Additional metadata (forms analyzed, evolution markers)
        created_at: Profile creation timestamp
        updated_at: Last update timestamp
        user: Related User object
        
    Privacy:
        - Users can view their profile via API
        - Users can delete/reset their profile
        - Respects User.profiling_enabled setting
    """
    
    __tablename__ = "user_profiles"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign Key (one-to-one with User)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    
    # Behavioral Profile Content
    profile_text = Column(Text, nullable=False)  # Max 500 words behavioral summary
    
    # Confidence & Metadata
    confidence_score = Column(Float, default=0.3, nullable=False)  # 0.0-1.0 (Low/Medium/High)
    form_count = Column(Integer, default=1, nullable=False)  # Forms analyzed
    version = Column(Integer, default=1, nullable=False)  # Evolution tracking
    
    # Extensible Metadata (JSON string)
    # Contains: forms_analyzed, last_form_type, evolution_markers
    metadata_json = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="behavioral_profile")
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<UserProfile(user_id={self.user_id}, confidence={self.confidence_score:.2f}, forms={self.form_count})>"
    
    @property
    def confidence_level(self) -> str:
        """Human-readable confidence level."""
        if self.confidence_score >= 0.7:
            return "High"
        elif self.confidence_score >= 0.4:
            return "Medium"
        return "Low"
    
    def to_dict(self) -> dict:
        """Convert profile to dictionary for API responses."""
        import json
        return {
            "user_id": self.user_id,
            "profile_text": self.profile_text,
            "confidence_score": self.confidence_score,
            "confidence_level": self.confidence_level,
            "form_count": self.form_count,
            "version": self.version,
            "metadata": json.loads(self.metadata_json) if self.metadata_json else {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
