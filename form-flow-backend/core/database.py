"""
Database Configuration Module

Provides async database connection and session management using SQLAlchemy.
All database operations should use async sessions from get_db().

Usage:
    from core.database import get_db
    
    async def my_endpoint(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(User))
        return result.scalars().all()
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import AsyncGenerator

from config.settings import settings


# =============================================================================
# Database URL Processing
# =============================================================================

def _process_database_url(url: str) -> str:
    """
    Process database URL for async compatibility.
    
    Converts:
        - postgresql:// to postgresql+asyncpg://
        - sslmode= to ssl= (asyncpg compatibility)
    
    Args:
        url: Original database URL
        
    Returns:
        Processed URL compatible with asyncpg
    """
    if not url:
        raise ValueError("DATABASE_URL is not configured")
    
    # Use async driver
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    # Fix SSL parameter for asyncpg
    if "sslmode=" in url:
        url = url.replace("sslmode=require", "ssl=require")
        url = url.replace("sslmode=verify-full", "ssl=verify-full")
    
    return url


# =============================================================================
# Engine & Session Configuration
# =============================================================================

DATABASE_URL = _process_database_url(settings.DATABASE_URL)

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG,  # Log SQL queries in debug mode
    pool_pre_ping=True,   # Verify connections before use
    pool_recycle=300,     # Recycle connections after 5 minutes
    pool_size=3,          # Reduced for small servers (was 5)
    max_overflow=5,       # Reduced for small servers (was 10)
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Declarative base for model definitions
Base = declarative_base()


# =============================================================================
# Dependency Injection
# =============================================================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session for dependency injection.
    
    Creates a new session for each request and ensures proper cleanup.
    
    Yields:
        AsyncSession: Database session for the request
        
    Example:
        @router.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
            return result.scalars().all()
    """
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# =============================================================================
# Health Check
# =============================================================================

async def check_database_health() -> bool:
    """
    Check if database connection is healthy.
    
    Returns:
        bool: True if database is accessible, False otherwise
    """
    try:
        from sqlalchemy import text
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception:
        return False
