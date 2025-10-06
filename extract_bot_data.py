#!/usr/bin/env python3
"""Extract trade data from bot's internal database and create Excel reports."""

import sqlite3
import pandas as pd
from datetime import datetime, timezone
import pytz
import os

def extract_bot_data():
    """Extract data from bot's SQLite database and create Excel reports."""
    
    db_path = "trades.sqlite"
    if not os.path.exists(db_path):
        print(f"❌ Database file {db_path} not found")
        return False
    
    print(f"🔍 Extracting data from {db_path}")
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        
        # Get all table names
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"📊 Found {len(tables)} tables in database:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Create Excel file with all tables
        output_file = "bot_database_export.xlsx"
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            for table_name in tables:
                table_name = table_name[0]
                print(f"\n📋 Processing table: {table_name}")
                
                try:
                    # Read table data
                    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
                    
                    if len(df) > 0:
                        print(f"  ✅ Found {len(df)} records")
                        
                        # Convert timestamp columns if they exist
                        tz_se = pytz.timezone("Europe/Stockholm")
                        
                        for col in df.columns:
                            if 'time' in col.lower() or 'date' in col.lower():
                                try:
                                    # Try to convert to datetime
                                    df[col] = pd.to_datetime(df[col], errors='coerce')
                                    if df[col].dt.tz is None:
                                        # Assume UTC if no timezone
                                        df[col] = df[col].dt.tz_localize('UTC').dt.tz_convert(tz_se)
                                    else:
                                        df[col] = df[col].dt.tz_convert(tz_se)
                                    # Remove timezone for Excel compatibility
                                    df[col] = df[col].dt.tz_localize(None)
                                except:
                                    pass  # Skip if conversion fails
                        
                        # Write to Excel
                        df.to_excel(writer, sheet_name=table_name, index=False)
                        print(f"  ✅ Exported to sheet: {table_name}")
                    else:
                        print(f"  ⚠️  Table is empty")
                        
                except Exception as e:
                    print(f"  ❌ Error processing table {table_name}: {e}")
        
        conn.close()
        
        print(f"\n🎉 Successfully exported database to {output_file}")
        return True
        
    except Exception as e:
        print(f"❌ Error extracting data: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = extract_bot_data()
    if success:
        print("\n✅ Database extraction completed successfully!")
    else:
        print("\n❌ Database extraction failed")
