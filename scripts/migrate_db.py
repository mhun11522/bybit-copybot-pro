#!/usr/bin/env python3
"""Database migration runner for the trading bot."""

import sqlite3
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

DB_PATH = "trades.sqlite"

def run_migration(migration_file):
    """Run a single migration file."""
    print(f"🔄 Running migration: {migration_file}")
    
    with open(migration_file, 'r') as f:
        sql = f.read()
    
    with sqlite3.connect(DB_PATH) as db:
        db.executescript(sql)
        db.commit()
    
    print(f"✅ Migration completed: {migration_file}")

def main():
    """Run all pending migrations."""
    print("🚀 Starting database migration...")
    
    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"📝 Creating new database: {DB_PATH}")
        with sqlite3.connect(DB_PATH) as db:
            db.execute("SELECT 1")  # Create the file
    
    # Run migrations
    migrations_dir = Path(__file__).parent.parent / "migrations"
    
    if migrations_dir.exists():
        migration_files = sorted(migrations_dir.glob("*.sql"))
        
        for migration_file in migration_files:
            try:
                run_migration(migration_file)
            except Exception as e:
                print(f"❌ Migration failed: {migration_file}")
                print(f"Error: {e}")
                sys.exit(1)
    else:
        print("⚠️ No migrations directory found")
    
    print("🎉 All migrations completed successfully!")

if __name__ == "__main__":
    main()