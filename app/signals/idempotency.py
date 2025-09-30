"""Idempotency and deduplication for signals."""

import hashlib
import sqlite3
import asyncio
from datetime import datetime, timedelta
from app.config.settings import DEDUP_SECONDS, MAX_CONCURRENT_TRADES

DB_PATH = "trades.sqlite"

def _hash_signal(chat_id: int, text: str) -> str:
    """Create hash for signal deduplication."""
    return hashlib.sha256(f"{chat_id}|{text}".encode("utf-8")).hexdigest()

async def is_new_signal(chat_id: int, text: str) -> bool:
    """Check if signal is new and not duplicate."""
    signal_hash = _hash_signal(chat_id, text)
    
    def _sync_db_operation():
        with sqlite3.connect(DB_PATH) as db:
            # Create tables if not exist
            db.execute("""
                CREATE TABLE IF NOT EXISTS signal_seen(
                    chat_id INTEGER,
                    signal_hash TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(chat_id, signal_hash)
                )
            """)
            
            db.execute("""
                CREATE TABLE IF NOT EXISTS active_trades(
                    trade_id TEXT PRIMARY KEY,
                    symbol TEXT,
                    direction TEXT,
                    channel_name TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'ACTIVE'
                )
            """)
            
            db.commit()
            
            # Check if signal already seen within dedup window
            cutoff_time = datetime.now() - timedelta(seconds=DEDUP_SECONDS)
            cur = db.execute("""
                SELECT 1 FROM signal_seen 
                WHERE chat_id = ? AND signal_hash = ? AND timestamp > ?
            """, (chat_id, signal_hash, cutoff_time))
            if cur.fetchone():
                return False
            
            # Check capacity limit
            cur = db.execute("""
                SELECT COUNT(*) FROM active_trades WHERE status = 'ACTIVE'
            """)
            active_count = cur.fetchone()[0]
            if active_count >= MAX_CONCURRENT_TRADES:
                print(f"⛔ Capacity limit reached: {active_count}/{MAX_CONCURRENT_TRADES}")
                return False
            
            # Record signal as seen
            try:
                db.execute("""
                    INSERT INTO signal_seen(chat_id, signal_hash) VALUES(?, ?)
                """, (chat_id, signal_hash))
                db.commit()
                return True
            except sqlite3.IntegrityError:
                # Signal already exists
                return False
    
    # Run sync operation in thread pool
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_db_operation)

async def register_trade(trade_id: str, symbol: str, direction: str, channel_name: str):
    """Register new active trade."""
    def _sync_operation():
        with sqlite3.connect(DB_PATH) as db:
            db.execute("""
                INSERT OR REPLACE INTO active_trades(trade_id, symbol, direction, channel_name)
                VALUES(?, ?, ?, ?)
            """, (trade_id, symbol, direction, channel_name))
            db.commit()
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _sync_operation)

async def close_trade(trade_id: str):
    """Mark trade as closed."""
    def _sync_operation():
        with sqlite3.connect(DB_PATH) as db:
            db.execute("""
                UPDATE active_trades SET status = 'CLOSED' WHERE trade_id = ?
            """, (trade_id,))
            db.commit()
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _sync_operation)

async def get_active_trades() -> int:
    """Get count of active trades."""
    def _sync_operation():
        with sqlite3.connect(DB_PATH) as db:
            cur = db.execute("""
                SELECT COUNT(*) FROM active_trades WHERE status = 'ACTIVE'
            """)
            return cur.fetchone()[0]
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_operation)