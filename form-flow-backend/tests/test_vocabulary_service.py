"""
Tests for Vocabulary Service
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from core.vocabulary_model import VocabularyCorrection
from services.voice.vocabulary import VocabularyService
import shutil

# Use in-memory SQLite for testing to avoid messing with real DB
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture(loop_scope="function")
async def test_db():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    
    async with SessionLocal() as session:
        print(f"DEBUG: Session type: {type(session)}")
        yield session
        await session.rollback()
    
    await engine.dispose()

@pytest.mark.asyncio
async def test_add_and_retrieve_correction(test_db):
    service = VocabularyService()
    
    # Test Add
    added = await service.add_correction(test_db, "Karval", "Karwal", "name")
    assert added.id is not None
    assert added.heard == "karval"
    assert added.correct == "Karwal"
    
    # Test Retrieve
    corrections = await service.get_corrections(test_db)
    assert len(corrections) == 1
    assert corrections[0].heard == "karval"

@pytest.mark.asyncio
async def test_apply_corrections_logic(test_db):
    service = VocabularyService()
    
    # Add corrections
    await service.add_correction(test_db, "Karval", "Karwal")
    await service.add_correction(test_db, "Atharva", "Atharva") # Normalization test, though usually it corrects wrong to right
    await service.add_correction(test_db, "g mail", "gmail")
    
    # Test Application (Using the sync cache)
    # Important: The service cache is updated inside add_correction
    
    # Test 1: Simple replacement
    res = service.apply_corrections("My name is Karval")
    assert res['corrected'] == "My name is Karwal"
    assert len(res['applied']) == 1
    
    # Test 2: Multiple replacements
    res = service.apply_corrections("Karval uses g mail")
    assert res['corrected'] == "Karwal uses gmail"
    assert len(res['applied']) == 2
    
    # Test 3: Case insensitivity
    res = service.apply_corrections("Start karval end")
    assert res['corrected'] == "Start Karwal end" 

@pytest.mark.asyncio
async def test_update_existing_correction(test_db):
    service = VocabularyService()
    
    # Add initial
    await service.add_correction(test_db, "test", "wrong")
    
    # Update
    updated = await service.add_correction(test_db, "test", "right")
    
    assert updated.correct == "right"
    
    # Verify count
    corrections = await service.get_corrections(test_db)
    assert len(corrections) == 1
    assert corrections[0].correct == "right"

@pytest.mark.asyncio
async def test_delete_correction(test_db):
    service = VocabularyService()
    
    added = await service.add_correction(test_db, "todelete", "val")
    
    success = await service.delete_correction(test_db, added.id)
    assert success is True
    
    corrections = await service.get_corrections(test_db)
    assert len(corrections) == 0
    
    # Verify cache cleared
    res = service.apply_corrections("todelete")
    assert res['corrected'] == "todelete"
