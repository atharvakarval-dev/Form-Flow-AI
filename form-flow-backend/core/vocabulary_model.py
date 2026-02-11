"""
Vocabulary Correction Model

Database model for storing user-specific vocabulary corrections
"""

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from core.database import Base


class VocabularyCorrection(Base):
    """User vocabulary corrections for STT improvements"""
    __tablename__ = "vocabulary_corrections"
    
    id = Column(Integer, primary_key=True, index=True)
    heard = Column(String(255), nullable=False, index=True)
    correct = Column(String(255), nullable=False)
    context = Column(String(255), nullable=True)
    phonetic = Column(String(255), nullable=True)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used = Column(DateTime(timezone=True), nullable=True)
