#!/usr/bin/env python3
"""Check database structure and missing orders."""

import sqlite3
import json
from datetime import datetime

def check_database():
    """Check database structure and data."""
    try:
        conn = sqlite3.connect('trades.sqlite')
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print("Tables:", tables)
        
        # Check trades table schema
        cursor.execute("PRAGMA table_info(trades)")
        trades_schema = cursor.fetchall()
        print("\nTrades schema:")
        for col in trades_schema:
            print(f"  {col[1]} {col[2]} {'NOT NULL' if col[3] else ''} {'DEFAULT ' + str(col[4]) if col[4] else ''}")
        
        # Check if orders table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'")
        orders_exists = cursor.fetchone()
        print(f"\nOrders table exists: {orders_exists is not None}")
        
        # Check trades data
        cursor.execute("SELECT COUNT(*) FROM trades")
        trades_count = cursor.fetchone()[0]
        print(f"\nTrades count: {trades_count}")
        
        # Check recent trades
        cursor.execute("SELECT trade_id, symbol, direction, state, created_at FROM trades ORDER BY created_at DESC LIMIT 5")
        recent_trades = cursor.fetchall()
        print("\nRecent trades:")
        for trade in recent_trades:
            print(f"  {trade}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error checking database: {e}")

if __name__ == "__main__":
    check_database()
