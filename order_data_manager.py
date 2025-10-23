#!/usr/bin/env python3
"""
Order Data Persistence System
Fixes the journal reconciliation issues and adds proper order tracking.
"""

import asyncio
import sqlite3
import json
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional
from pathlib import Path

class OrderDataManager:
    """Manages order data persistence and journal reconciliation."""
    
    def __init__(self, db_path: str = "trades.sqlite"):
        self.db_path = db_path
        self.journal_path = Path("logs/journal.jsonl")
        
    async def initialize_database(self):
        """Initialize database with proper schema."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create orders table with comprehensive schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
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
                    commission REAL DEFAULT 0,
                    commission_asset TEXT DEFAULT 'USDT',
                    FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
                )
            """)
            
            # Create fills table for order execution details
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fills (
                    fill_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    trade_id TEXT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    qty REAL NOT NULL,
                    price REAL NOT NULL,
                    commission REAL DEFAULT 0,
                    commission_asset TEXT DEFAULT 'USDT',
                    fill_time TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (order_id) REFERENCES orders(order_id),
                    FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
                )
            """)
            
            # Create order_states table for state transitions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS order_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data TEXT,  -- JSON data for additional context
                    FOREIGN KEY (order_id) REFERENCES orders(order_id)
                )
            """)
            
            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_trade_id ON orders(trade_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fills_order_id ON fills(order_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fills_trade_id ON fills(trade_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_states_order_id ON order_states(order_id)")
            
            conn.commit()
            conn.close()
            
            print("Database initialized with comprehensive order schema")
            
        except Exception as e:
            print(f"Error initializing database: {e}")
            raise
    
    async def save_order(self, order_data: Dict[str, Any]) -> bool:
        """Save order data to database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Insert order
            cursor.execute("""
                INSERT OR REPLACE INTO orders (
                    order_id, trade_id, symbol, side, order_type, order_link_id,
                    price, qty, status, time_in_force, reduce_only, post_only,
                    trigger_price, trigger_by, close_on_trigger, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_data.get("orderId"),
                order_data.get("trade_id"),
                order_data.get("symbol"),
                order_data.get("side"),
                order_data.get("orderType", "Limit"),
                order_data.get("orderLinkId"),
                order_data.get("price"),
                order_data.get("qty"),
                order_data.get("orderStatus", "New"),
                order_data.get("timeInForce", "GTC"),
                order_data.get("reduceOnly", False),
                order_data.get("postOnly", False),
                order_data.get("triggerPrice"),
                order_data.get("triggerBy"),
                order_data.get("closeOnTrigger", False),
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            
            # Record state transition
            cursor.execute("""
                INSERT INTO order_states (order_id, state, data)
                VALUES (?, ?, ?)
            """, (
                order_data.get("orderId"),
                order_data.get("orderStatus", "New"),
                json.dumps(order_data)
            ))
            
            conn.commit()
            conn.close()
            
            print(f"Order saved: {order_data.get('orderId')} - {order_data.get('symbol')}")
            return True
            
        except Exception as e:
            print(f"Error saving order: {e}")
            return False
    
    async def update_order_status(self, order_id: str, status: str, additional_data: Dict[str, Any] = None):
        """Update order status and record state transition."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Update order status
            cursor.execute("""
                UPDATE orders 
                SET status = ?, updated_at = ?, filled_qty = ?, avg_price = ?
                WHERE order_id = ?
            """, (
                status,
                datetime.now().isoformat(),
                additional_data.get("cumExecQty", 0) if additional_data else 0,
                additional_data.get("avgPrice", 0) if additional_data else 0,
                order_id
            ))
            
            # Record state transition
            cursor.execute("""
                INSERT INTO order_states (order_id, state, data)
                VALUES (?, ?, ?)
            """, (
                order_id,
                status,
                json.dumps(additional_data or {})
            ))
            
            conn.commit()
            conn.close()
            
            print(f"Order status updated: {order_id} -> {status}")
            
        except Exception as e:
            print(f"Error updating order status: {e}")
    
    async def save_fill(self, fill_data: Dict[str, Any]) -> bool:
        """Save order fill data."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO fills (
                    fill_id, order_id, trade_id, symbol, side, qty, price,
                    commission, commission_asset, fill_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fill_data.get("execId"),
                fill_data.get("orderId"),
                fill_data.get("trade_id"),
                fill_data.get("symbol"),
                fill_data.get("side"),
                fill_data.get("execQty"),
                fill_data.get("execPrice"),
                fill_data.get("execFee", 0),
                fill_data.get("feeTokenId", "USDT"),
                fill_data.get("execTime", datetime.now().isoformat())
            ))
            
            conn.commit()
            conn.close()
            
            print(f"Fill saved: {fill_data.get('execId')} - {fill_data.get('symbol')}")
            return True
            
        except Exception as e:
            print(f"Error saving fill: {e}")
            return False
    
    async def reconcile_with_bybit(self, bybit_orders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Reconcile local orders with Bybit orders."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get all local orders
            cursor.execute("SELECT order_id, symbol, side, status FROM orders")
            local_orders = {row[0]: row for row in cursor.fetchall()}
            
            # Get Bybit order IDs
            bybit_order_ids = {order.get("orderId") for order in bybit_orders}
            
            # Find missing orders (in Bybit but not in local DB)
            missing_orders = []
            for order in bybit_orders:
                order_id = order.get("orderId")
                if order_id not in local_orders:
                    missing_orders.append(order)
            
            # Find orphaned orders (in local DB but not in Bybit)
            orphaned_orders = []
            for order_id, order_data in local_orders.items():
                if order_id not in bybit_order_ids:
                    orphaned_orders.append(order_data)
            
            # Insert missing orders
            for order in missing_orders:
                await self.save_order(order)
            
            conn.close()
            
            reconciliation_result = {
                "status": "clean" if not missing_orders and not orphaned_orders else "has_issues",
                "missing": missing_orders,
                "orphans": orphaned_orders,
                "total_bybit_orders": len(bybit_orders),
                "total_local_orders": len(local_orders)
            }
            
            print(f"Reconciliation complete: {len(missing_orders)} missing, {len(orphaned_orders)} orphaned")
            return reconciliation_result
            
        except Exception as e:
            print(f"Error during reconciliation: {e}")
            return {"status": "error", "error": str(e)}
    
    async def get_order_history(self, trade_id: str = None, symbol: str = None) -> List[Dict[str, Any]]:
        """Get order history with optional filters."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = "SELECT * FROM orders WHERE 1=1"
            params = []
            
            if trade_id:
                query += " AND trade_id = ?"
                params.append(trade_id)
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            query += " ORDER BY created_at DESC"
            
            cursor.execute(query, params)
            columns = [description[0] for description in cursor.description]
            orders = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            conn.close()
            return orders
            
        except Exception as e:
            print(f"Error getting order history: {e}")
            return []
    
    async def get_trade_summary(self, trade_id: str) -> Dict[str, Any]:
        """Get comprehensive trade summary including all orders and fills."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get trade info
            cursor.execute("SELECT * FROM trades WHERE trade_id = ?", (trade_id,))
            trade_row = cursor.fetchone()
            if not trade_row:
                return {}
            
            trade_columns = [description[0] for description in cursor.description]
            trade_data = dict(zip(trade_columns, trade_row))
            
            # Get all orders for this trade
            cursor.execute("SELECT * FROM orders WHERE trade_id = ? ORDER BY created_at", (trade_id,))
            order_columns = [description[0] for description in cursor.description]
            orders = [dict(zip(order_columns, row)) for row in cursor.fetchall()]
            
            # Get all fills for this trade
            cursor.execute("SELECT * FROM fills WHERE trade_id = ? ORDER BY fill_time", (trade_id,))
            fill_columns = [description[0] for description in cursor.description]
            fills = [dict(zip(fill_columns, row)) for row in cursor.fetchall()]
            
            conn.close()
            
            return {
                "trade": trade_data,
                "orders": orders,
                "fills": fills,
                "order_count": len(orders),
                "fill_count": len(fills)
            }
            
        except Exception as e:
            print(f"Error getting trade summary: {e}")
            return {}

async def main():
    """Test the order data manager."""
    manager = OrderDataManager()
    
    # Initialize database
    await manager.initialize_database()
    
    # Test order saving
    test_order = {
        "orderId": "test_order_123",
        "trade_id": "test_trade_456",
        "symbol": "BTCUSDT",
        "side": "Buy",
        "orderType": "Limit",
        "orderLinkId": "test_link_789",
        "price": 50000.0,
        "qty": 0.001,
        "orderStatus": "New",
        "timeInForce": "GTC",
        "reduceOnly": False,
        "postOnly": True
    }
    
    await manager.save_order(test_order)
    
    # Test status update
    await manager.update_order_status("test_order_123", "Filled", {
        "cumExecQty": 0.001,
        "avgPrice": 50000.0
    })
    
    # Test fill saving
    test_fill = {
        "execId": "fill_123",
        "orderId": "test_order_123",
        "trade_id": "test_trade_456",
        "symbol": "BTCUSDT",
        "side": "Buy",
        "execQty": 0.001,
        "execPrice": 50000.0,
        "execFee": 0.05,
        "feeTokenId": "USDT",
        "execTime": datetime.now().isoformat()
    }
    
    await manager.save_fill(test_fill)
    
    # Get order history
    orders = await manager.get_order_history(trade_id="test_trade_456")
    print(f"Found {len(orders)} orders for test trade")
    
    print("Order data manager test completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
