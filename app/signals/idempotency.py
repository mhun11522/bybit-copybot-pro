"""Idempotency and deduplication for signals."""

import hashlib
import aiosqlite
from datetime import datetime, timedelta
from app.config.settings import DEDUP_SECONDS, MAX_CONCURRENT_TRADES

DB_PATH = "trades.sqlite"

def _hash_signal(chat_id: int, text: str) -> str:
    """Create hash for signal deduplication."""
    return hashlib.sha256(f"{chat_id}|{text}".encode("utf-8")).hexdigest()

async def is_new_signal(chat_id: int, text: str) -> bool:
    """Check if signal is new and not duplicate."""
    signal_hash = _hash_signal(chat_id, text)
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Create tables if not exist
        await db.execute("""
            CREATE TABLE IF NOT EXISTS signal_seen(
                chat_id INTEGER,
                signal_hash TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(chat_id, signal_hash)
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS active_trades(
                trade_id TEXT PRIMARY KEY,
                symbol TEXT,
                direction TEXT,
                channel_name TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'ACTIVE'
            )
        """)
        
        await db.commit()
        
        # Check if signal already seen within dedup window
        cutoff_time = datetime.now() - timedelta(seconds=DEDUP_SECONDS)
        async with db.execute("""
            SELECT 1 FROM signal_seen 
            WHERE chat_id = ? AND signal_hash = ? AND timestamp > ?
        """, (chat_id, signal_hash, cutoff_time)) as cur:
            if await cur.fetchone():
                return False
        
        # Check capacity limit
        async with db.execute("""
            SELECT COUNT(*) FROM active_trades WHERE status = 'ACTIVE'
        """) as cur:
            active_count = (await cur.fetchone())[0]
            if active_count >= MAX_CONCURRENT_TRADES:
                print(f"⛔ Capacity limit reached: {active_count}/{MAX_CONCURRENT_TRADES}")
                return False
        
        # Record signal as seen
        try:
            await db.execute("""
                INSERT INTO signal_seen(chat_id, signal_hash) VALUES(?, ?)
            """, (chat_id, signal_hash))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            # Signal already exists
            return False

async def register_trade(trade_id: str, symbol: str, direction: str, channel_name: str):
    """Register new active trade."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO active_trades(trade_id, symbol, direction, channel_name)
            VALUES(?, ?, ?, ?)
        """, (trade_id, symbol, direction, channel_name))
        await db.commit()

async def close_trade(trade_id: str):
    """Mark trade as closed."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE active_trades SET status = 'CLOSED' WHERE trade_id = ?
        """, (trade_id,))
        await db.commit()

async def get_active_trades() -> int:
    """Get count of active trades."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT COUNT(*) FROM active_trades WHERE status = 'ACTIVE'
        """) as cur:
            return (await cur.fetchone())[0]