"""
Database Migration: Add Vocabulary Corrections Table

Run this script to create the vocabulary_corrections table
for the self-learning vocabulary correction system.

Usage:
    python scripts/migrate_vocabulary.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.database import engine
from utils.logging import get_logger

logger = get_logger(__name__)


async def migrate():
    """Create vocabulary_corrections table"""
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS vocabulary_corrections (
        id SERIAL PRIMARY KEY,
        heard VARCHAR(255) NOT NULL,
        correct VARCHAR(255) NOT NULL,
        context VARCHAR(255),
        phonetic VARCHAR(255),
        usage_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_used TIMESTAMP
    );
    
    CREATE UNIQUE INDEX IF NOT EXISTS idx_heard_unique ON vocabulary_corrections(heard);
    CREATE INDEX IF NOT EXISTS idx_usage_count ON vocabulary_corrections(usage_count DESC);
    """
    
    try:
        async with engine.begin() as conn:
            logger.info("Creating vocabulary_corrections table...")
            await conn.execute(text(create_table_sql))
            logger.info("✓ Table created successfully")
            
            # Verify table exists
            result = await conn.execute(text("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_name = 'vocabulary_corrections'
            """))
            count = result.scalar()
            
            if count > 0:
                logger.info("✓ Migration verified")
                return True
            else:
                logger.error("✗ Table not found after creation")
                return False
                
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


async def rollback():
    """Drop vocabulary_corrections table"""
    
    drop_table_sql = """
    DROP TABLE IF EXISTS vocabulary_corrections CASCADE;
    """
    
    try:
        async with engine.begin() as conn:
            logger.info("Dropping vocabulary_corrections table...")
            await conn.execute(text(drop_table_sql))
            logger.info("✓ Table dropped successfully")
            return True
            
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        return False


async def seed_sample_data():
    """Add sample vocabulary corrections for testing"""
    
    sample_data = [
        ("karval", "Karwal", "name"),
        ("john dough", "John Doe", "name"),
        ("acme corp", "ACME Corporation", "company"),
        ("gmail dot com", "gmail.com", "email"),
        ("triple w", "www", "url"),
    ]
    
    insert_sql = """
    INSERT INTO vocabulary_corrections (heard, correct, context, usage_count)
    VALUES (:heard, :correct, :context, 0)
    ON CONFLICT DO NOTHING
    """
    
    try:
        async with engine.begin() as conn:
            logger.info("Seeding sample data...")
            
            for heard, correct, context in sample_data:
                await conn.execute(
                    text(insert_sql),
                    {"heard": heard, "correct": correct, "context": context}
                )
            
            logger.info(f"✓ Seeded {len(sample_data)} sample corrections")
            return True
            
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        return False


async def main():
    """Main migration script"""
    
    print("\n" + "="*60)
    print("FormFlow AI - Vocabulary Corrections Migration")
    print("="*60 + "\n")
    
    print("Options:")
    print("1. Migrate (create table)")
    print("2. Rollback (drop table)")
    print("3. Seed sample data")
    print("4. Exit")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == "1":
        success = await migrate()
        if success:
            print("\n✓ Migration completed successfully!")
            
            seed = input("\nSeed sample data? (y/n): ").strip().lower()
            if seed == 'y':
                await seed_sample_data()
        else:
            print("\n✗ Migration failed. Check logs for details.")
            
    elif choice == "2":
        confirm = input("\nAre you sure? This will delete all corrections. (yes/no): ").strip().lower()
        if confirm == "yes":
            success = await rollback()
            if success:
                print("\n✓ Rollback completed successfully!")
            else:
                print("\n✗ Rollback failed. Check logs for details.")
        else:
            print("\nRollback cancelled.")
            
    elif choice == "3":
        success = await seed_sample_data()
        if success:
            print("\n✓ Sample data seeded successfully!")
        else:
            print("\n✗ Seeding failed. Check logs for details.")
            
    elif choice == "4":
        print("\nExiting...")
        
    else:
        print("\nInvalid choice.")
    
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
