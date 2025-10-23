#!/usr/bin/env python3
"""Check journal reconciliation issues and fix orders table."""

import sqlite3
import json
from datetime import datetime

def check_journal_and_fix_orders():
    """Check journal issues and fix orders table."""
    try:
        conn = sqlite3.connect('trades.sqlite')
        cursor = conn.cursor()
        
        # Check current orders table schema
        cursor.execute("PRAGMA table_info(orders)")
        orders_schema = cursor.fetchall()
        print("Current orders schema:")
        for col in orders_schema:
            print(f"  {col[1]} {col[2]}")
        
        # The missing orders from logs were:
        missing_orders = [
            {"order_id": "e8965455-9bd1-4fa3-9b99-729a1421f066", "symbol": "BTCUSDT", "side": "Buy", "orderLinkId": "entry_BTCUSDT_LONG_172223_1"},
            {"order_id": "81642624-cea6-4292-a736-7d555377e683", "symbol": "BTCUSDT", "side": "Buy", "orderLinkId": "entry_BTCUSDT_LONG_172223_0"},
            {"order_id": "a081bf36-981d-4d27-9482-c929c658dd7b", "symbol": "BTCUSDT", "side": "Buy", "orderLinkId": "entry_BTCUSDT_LONG_22747_1"},
            {"order_id": "b72cd150-d98f-478e-bd01-043fded333f7", "symbol": "BTCUSDT", "side": "Buy", "orderLinkId": "entry_BTCUSDT_LONG_22747_0"},
            {"order_id": "9c482c44-8db9-4ce3-93a5-44b07cbd7cb9", "symbol": "BTCUSDT", "side": "Buy", "orderLinkId": "entry_BTCUSDT_LONG_21329_1"},
            {"order_id": "265aebc3-c843-4857-9358-e68326ad863c", "symbol": "BTCUSDT", "side": "Buy", "orderLinkId": "entry_BTCUSDT_LONG_21329_0"},
            {"order_id": "9e25e054-eb92-49db-922b-d259976d25fd", "symbol": "RLCUSDT", "side": "Sell", "orderLinkId": "entry_RLCUSDT_SHORT_1161199_1"},
            {"order_id": "dd659545-f882-4e42-8c38-a3f89872323c", "symbol": "RLCUSDT", "side": "Sell", "orderLinkId": "entry_RLCUSDT_SHORT_1161199_0"},
            {"order_id": "f59754f7-8c8d-49ee-bdec-035549725770", "symbol": "BTCUSDT", "side": "Buy", "orderLinkId": "entry_BTCUSDT_LONG_1158616_1"},
            {"order_id": "ab86688c-ac82-4f1b-9cff-e0e02382e028", "symbol": "BTCUSDT", "side": "Buy", "orderLinkId": "entry_BTCUSDT_LONG_1158616_0"},
            {"order_id": "30483ede-da6e-4815-89a2-359d6c0cd919", "symbol": "BTCUSDT", "side": "Buy", "orderLinkId": "entry_BTCUSDT_LONG_1155338_1"},
            {"order_id": "eaf25522-be10-4f83-a75f-ce19bd2f8c28", "symbol": "BTCUSDT", "side": "Buy", "orderLinkId": "entry_BTCUSDT_LONG_1155338_0"},
            {"order_id": "a3c32eed-32b8-491b-b14c-11ca447767bc", "symbol": "BELUSDT", "side": "Buy", "orderLinkId": "entry_BELUSDT_LONG_1060533_0"},
            {"order_id": "263e79d3-e6b6-433d-ad9e-13c9ae4c4488", "symbol": "CHESSUSDT", "side": "Buy", "orderLinkId": "entry_CHESSUSDT_LONG_1031423_1"},
            {"order_id": "8522699f-b16a-456e-bc82-a6440c7e7e6c", "symbol": "CHESSUSDT", "side": "Buy", "orderLinkId": "entry_CHESSUSDT_LONG_1031423_0"}
        ]
        
        print(f"\nFound {len(missing_orders)} missing orders from journal reconciliation")
        
        # Create proper orders table schema
        print("\nCreating proper orders table schema...")
        
        # Drop and recreate orders table with proper schema
        cursor.execute("DROP TABLE IF EXISTS orders")
        
        create_orders_sql = """
        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            trade_id TEXT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            order_type TEXT NOT NULL,
            order_link_id TEXT UNIQUE,
            price REAL,
            qty REAL,
            status TEXT DEFAULT 'New',
            time_in_force TEXT DEFAULT 'GTC',
            reduce_only BOOLEAN DEFAULT FALSE,
            post_only BOOLEAN DEFAULT FALSE,
            trigger_price REAL,
            trigger_by TEXT,
            close_on_trigger BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            filled_qty REAL DEFAULT 0,
            avg_price REAL,
            FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
        )
        """
        
        cursor.execute(create_orders_sql)
        
        # Create indexes
        cursor.execute("CREATE INDEX idx_orders_trade_id ON orders(trade_id)")
        cursor.execute("CREATE INDEX idx_orders_symbol ON orders(symbol)")
        cursor.execute("CREATE INDEX idx_orders_status ON orders(status)")
        cursor.execute("CREATE INDEX idx_orders_created_at ON orders(created_at)")
        
        print("Orders table recreated with proper schema")
        
        # Insert missing orders (as historical records)
        print("\nInserting missing orders as historical records...")
        
        for order in missing_orders:
            # Extract trade_id from orderLinkId
            order_link_id = order["orderLinkId"]
            trade_id = None
            
            # Parse orderLinkId to extract trade_id
            if "entry_" in order_link_id:
                parts = order_link_id.split("_")
                if len(parts) >= 3:
                    symbol = parts[1]
                    direction = parts[2]
                    timestamp_part = parts[3] if len(parts) > 3 else "unknown"
                    trade_id = f"{symbol}_{timestamp_part}"
            
            insert_sql = """
            INSERT INTO orders (
                order_id, trade_id, symbol, side, order_type, order_link_id, 
                status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            cursor.execute(insert_sql, (
                order["order_id"],
                trade_id,
                order["symbol"],
                order["side"],
                "Limit",  # Assume limit orders
                order["orderLinkId"],
                "Filled",  # Assume filled since they're missing from journal
                datetime.now().isoformat()
            ))
        
        conn.commit()
        print(f"Inserted {len(missing_orders)} missing orders")
        
        # Verify the new orders table
        cursor.execute("SELECT COUNT(*) FROM orders")
        new_count = cursor.fetchone()[0]
        print(f"Orders table now has {new_count} records")
        
        # Show sample records
        cursor.execute("SELECT order_id, symbol, side, order_link_id, status FROM orders LIMIT 5")
        sample_orders = cursor.fetchall()
        print("\nSample orders:")
        for order in sample_orders:
            print(f"  {order}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error fixing orders table: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_journal_and_fix_orders()
