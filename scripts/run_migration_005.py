"""Run migration 005: Add report columns."""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.storage.db import aiosqlite, DB_PATH

async def run_migration():
    """Run migration 005."""
    print("Running migration 005: Add report columns...")
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Read migration SQL
        with open('migrations/005_add_report_columns.sql', 'r') as f:
            migration_sql = f.read()
        
        # Split by semicolons and execute each statement
        statements = [s.strip() for s in migration_sql.split(';') if s.strip()]
        
        for i, statement in enumerate(statements, 1):
            try:
                print(f"  Executing statement {i}/{len(statements)}...")
                await db.execute(statement)
            except Exception as e:
                # Ignore "duplicate column" errors (migration already applied)
                if "duplicate column" in str(e).lower():
                    print(f"  ⚠️  Column already exists, skipping...")
                else:
                    print(f"  ❌ Error: {e}")
                    raise
        
        await db.commit()
        print("✅ Migration 005 completed successfully!")
        
        # Verify columns were added
        cursor = await db.execute("PRAGMA table_info(trades)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        print("\n📊 Current trades table schema:")
        for col_name in column_names:
            print(f"  - {col_name}")
        
        # Check for required columns
        required_cols = ['pyramid_level', 'hedge_count', 'reentry_count', 'error_type', 'pnl_pct', 'status']
        missing_cols = [col for col in required_cols if col not in column_names]
        
        if missing_cols:
            print(f"\n⚠️  WARNING: Missing columns: {missing_cols}")
        else:
            print("\n✅ All required columns present!")

if __name__ == "__main__":
    asyncio.run(run_migration())

