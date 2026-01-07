
import asyncio
import os
import sys

# Add parent directory to path to allow importing core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import engine, Base
from core.models import User, UserProfile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

async def run_migration():
    print("Starting database migration...")
    
    async with engine.begin() as conn:
        # 1. Add profiling_enabled column to users table if missing
        print("Checking for profiling_enabled column in users table...")
        
        # Check if column exists
        check_col_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='profiling_enabled';
        """)
        
        result = await conn.execute(check_col_query)
        if result.scalar() is None:
            print("Adding profiling_enabled column...")
            await conn.execute(text("ALTER TABLE users ADD COLUMN profiling_enabled BOOLEAN DEFAULT TRUE NOT NULL;"))
            print("Column profiling_enabled added.")
        else:
            print("Column profiling_enabled already exists.")

        # 2. Add metadata_json column to user_profiles table if missing (for dev iterations)
        # This handles cases where table might exist from previous attempts but schema evolved
        print("Checking for metadata_json column in user_profiles table...")
        try:
             # Check if table exists first
            check_table_query = text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name='user_profiles';
            """)
            table_exists = (await conn.execute(check_table_query)).scalar()
            
            if table_exists:
                check_meta_query = text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='user_profiles' AND column_name='metadata_json';
                """)
                result = await conn.execute(check_meta_query)
                if result.scalar() is None:
                    print("Adding metadata_json column...")
                    await conn.execute(text("ALTER TABLE user_profiles ADD COLUMN metadata_json TEXT;"))
                    print("Column metadata_json added.")
        except Exception as e:
            print(f"Error checking/adding metadata_json: {e}")

    # 3. Create missing tables (including user_profiles if it doesn't exist)
    print("Creating missing tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created/verified.")

    print("Migration complete!")

if __name__ == "__main__":
    # Windows-specific event loop policy for asyncpg
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(run_migration())
