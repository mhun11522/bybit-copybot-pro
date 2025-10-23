#!/usr/bin/env python3
"""Check orders table and missing data."""

import sqlite3
import json
from datetime import datetime

def check_orders():
    """Check orders table structure and data."""
    try:
        conn = sqlite3.connect('trades.sqlite')
        cursor = conn.cursor()
        
        # Check orders table schema
        cursor.execute("PRAGMA table_info(orders)")
        orders_schema = cursor.fetchall()
        print("Orders schema:")
        for col in orders_schema:
            print(f"  {col[1]} {col[2]} {'NOT NULL' if col[3] else ''} {'DEFAULT ' + str(col[4]) if col[4] else ''}")
        
        # Check orders count
        cursor.execute("SELECT COUNT(*) FROM orders")
        orders_count = cursor.fetchone()[0]
        print(f"\nOrders count: {orders_count}")
        
        # Check recent orders
        cursor.execute("SELECT order_id, symbol, side, order_type, status, created_at FROM orders ORDER BY created_at DESC LIMIT 10")
        recent_orders = cursor.fetchall()
        print("\nRecent orders:")
        for order in recent_orders:
            print(f"  {order}")
        
        # Check fills table
        cursor.execute("PRAGMA table_info(fills)")
        fills_schema = cursor.fetchall()
        print("\nFills schema:")
        for col in fills_schema:
            print(f"  {col[1]} {col[2]} {'NOT NULL' if col[3] else ''} {'DEFAULT ' + str(col[4]) if col[4] else ''}")
        
        # Check fills count
        cursor.execute("SELECT COUNT(*) FROM fills")
        fills_count = cursor.fetchone()[0]
        print(f"\nFills count: {fills_count}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error checking orders: {e}")

if __name__ == "__main__":
    check_orders()
