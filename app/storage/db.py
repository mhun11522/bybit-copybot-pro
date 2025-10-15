import asyncio
try:
    import aiosqlite as _aiosqlite  # type: ignore
    aiosqlite = _aiosqlite  # re-export for modules importing from this file
except Exception:  # Fallback shim when aiosqlite isn't installable
    import sqlite3

    class _CursorShim:
        def __init__(self, cur: sqlite3.Cursor):
            self._cur = cur

        async def fetchone(self):
            return await asyncio.to_thread(self._cur.fetchone)

        async def fetchall(self):
            return await asyncio.to_thread(self._cur.fetchall)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            try:
                await asyncio.to_thread(self._cur.close)
            except Exception:
                pass
            return False

    class _ExecuteShim:
        def __init__(self, conn: sqlite3.Connection, sql: str, params: tuple):
            self._conn = conn
            self._sql = sql
            self._params = params
            self._cur: sqlite3.Cursor | None = None

        async def _run(self) -> sqlite3.Cursor:
            return await asyncio.to_thread(self._conn.execute, self._sql, self._params)

        def __await__(self):
            async def _await_impl():
                # Execute statement; return a cursor shim for API parity, though callers usually ignore
                cur = await self._run()
                return _CursorShim(cur)
            return _await_impl().__await__()

        async def __aenter__(self):
            self._cur = await self._run()
            return _CursorShim(self._cur)

        async def __aexit__(self, exc_type, exc, tb):
            try:
                if self._cur is not None:
                    await asyncio.to_thread(self._cur.close)
            except Exception:
                pass
            return False

    class _ConnShim:
        def __init__(self, path: str):
            # CRITICAL FIX: Increase timeout for Windows concurrent access
            self._conn = sqlite3.connect(path, check_same_thread=False, timeout=30.0)
            # Enable WAL mode for better concurrent access
            try:
                self._conn.execute('PRAGMA journal_mode=WAL')
                self._conn.execute('PRAGMA busy_timeout=30000')  # 30 second timeout
                self._conn.execute('PRAGMA synchronous=NORMAL')
                self._conn.execute('PRAGMA foreign_keys=ON')
                self._conn.execute('PRAGMA cache_size=-64000')
                self._conn.commit()
            except Exception:
                pass  # Silently ignore if PRAGMA not supported

        def execute(self, sql: str, params: tuple = ()):  # returns awaitable and async-context-manager
            return _ExecuteShim(self._conn, sql, params)

        async def commit(self):
            await asyncio.to_thread(self._conn.commit)

        async def close(self):
            await asyncio.to_thread(self._conn.close)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            try:
                await self.close()
            except Exception:
                pass
            return False

    class _AioSqliteShim:
        def connect(self, path: str):
            return _ConnShim(path)

    aiosqlite = _AioSqliteShim()

DB_PATH = "trades.sqlite"


async def get_db_connection():
    """
    Get a database connection with optimized settings.
    
    CRITICAL FIX (ERROR #1): Enable WAL mode for concurrent access.
    This prevents "database is locked" errors on Windows.
    """
    conn = await aiosqlite.connect(DB_PATH)
    
    # CRITICAL FIX: Enable Write-Ahead Logging for concurrent access
    # This allows multiple readers and one writer simultaneously
    await conn.execute('PRAGMA journal_mode=WAL')
    
    # Set busy timeout (wait up to 10 seconds for locks instead of failing immediately)
    await conn.execute('PRAGMA busy_timeout=10000')
    
    # Optimize for concurrent reads (NORMAL is faster than FULL, safe with WAL)
    await conn.execute('PRAGMA synchronous=NORMAL')
    
    # Enable foreign keys for data integrity
    await conn.execute('PRAGMA foreign_keys=ON')
    
    # Increase cache size for better performance (default is too small)
    await conn.execute('PRAGMA cache_size=-64000')  # 64MB cache
    
    return conn


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # CRITICAL FIX: Enable WAL mode immediately on initialization
        await db.execute('PRAGMA journal_mode=WAL')
        await db.execute('PRAGMA busy_timeout=10000')
        await db.execute('PRAGMA synchronous=NORMAL')
        await db.execute('PRAGMA foreign_keys=ON')
        
        # Lightweight migrations: ensure missing columns exist
        await _migrate_trades_table(db)
        
        # Create unified trades table with all required columns
        await db.execute(
            """
        CREATE TABLE IF NOT EXISTS trades (
            trade_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry_price REAL NOT NULL,
            size REAL NOT NULL,
            avg_entry REAL,
            position_size REAL,
            leverage REAL,
            channel_name TEXT,
            state TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            realized_pnl REAL DEFAULT 0,
            pnl REAL DEFAULT 0,
            pnl_pct REAL DEFAULT 0,
            pyramid_level INTEGER DEFAULT 0,
            hedge_count INTEGER DEFAULT 0,
            reentry_count INTEGER DEFAULT 0,
            error_type TEXT,
            closed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        )
        
        # Create active_trades view for backward compatibility
        await db.execute(
            """
        CREATE VIEW IF NOT EXISTS active_trades AS
        SELECT trade_id, symbol, direction, state as status, created_at
        FROM trades
        WHERE state NOT IN ('DONE', 'CLOSED', 'CANCELLED')
        """
        )
        
        # Create trades_new view as alias to trades for backward compatibility
        await db.execute(
            """
        CREATE VIEW IF NOT EXISTS trades_new AS
        SELECT * FROM trades
        """
        )
        await db.execute(
            """
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            trade_id TEXT,
            link_id TEXT,
            type TEXT,
            price REAL,
            qty REAL,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        )
        await db.execute(
            """
        CREATE TABLE IF NOT EXISTS fills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id TEXT,
            order_id TEXT,
            link_id TEXT,
            side TEXT,
            price REAL,
            qty REAL,
            fee REAL,
            pnl REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        )
        await db.commit()


async def _migrate_trades_table(db) -> None:
    """Migrate trades table to add missing columns."""
    try:
        cols = []
        async with db.execute("PRAGMA table_info(trades)") as cur:
            rows = await cur.fetchall()
            cols = [r[1] for r in rows]  # r[1] is column name
        
        # Add missing columns for backward compatibility
        migrations = [
            ("realized_pnl", "ALTER TABLE trades ADD COLUMN realized_pnl REAL DEFAULT 0"),
            ("closed_at", "ALTER TABLE trades ADD COLUMN closed_at TIMESTAMP"),
            ("created_at", "ALTER TABLE trades ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("status", "ALTER TABLE trades ADD COLUMN status TEXT DEFAULT 'active'"),
            ("pnl", "ALTER TABLE trades ADD COLUMN pnl REAL DEFAULT 0"),
            ("pnl_pct", "ALTER TABLE trades ADD COLUMN pnl_pct REAL DEFAULT 0"),
            ("pyramid_level", "ALTER TABLE trades ADD COLUMN pyramid_level INTEGER DEFAULT 0"),
            ("hedge_count", "ALTER TABLE trades ADD COLUMN hedge_count INTEGER DEFAULT 0"),
            ("reentry_count", "ALTER TABLE trades ADD COLUMN reentry_count INTEGER DEFAULT 0"),
            ("error_type", "ALTER TABLE trades ADD COLUMN error_type TEXT"),
        ]
        
        for col_name, alter_sql in migrations:
            if col_name not in cols:
                try:
                    await db.execute(alter_sql)
                except Exception as e:
                    # Ignore if column already exists
                    if "duplicate column" not in str(e).lower():
                        pass  # Silently ignore other errors
        
        await db.commit()
    except Exception:
        # Best-effort migration; ignore if PRAGMA or ALTER not supported in env
        pass


async def save_trade(trade_id: str, symbol: str, direction: str, entry_price: float, size: float, state: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO trades (trade_id,symbol,direction,entry_price,size,state) VALUES (?,?,?,?,?,?)",
            (trade_id, symbol, direction, entry_price, size, state),
        )
        await db.commit()


async def save_order(order_id: str, trade_id: str, link_id: str, order_type: str, price: float, qty: float, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO orders (order_id,trade_id,link_id,type,price,qty,status) VALUES (?,?,?,?,?,?,?)",
            (order_id, trade_id, link_id, order_type, price, qty, status),
        )
        await db.commit()


async def get_open_trades():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT trade_id,symbol,direction,entry_price,size,state FROM trades WHERE state IN ('POSITION_CONFIRMED','TPSL_PLACED')") as cur:
            rows = await cur.fetchall()
            return rows


async def save_fill(trade_id: str, order_id: str, link_id: str, side: str, price: float, qty: float, fee: float, pnl: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO fills (trade_id,order_id,link_id,side,price,qty,fee,pnl) VALUES (?,?,?,?,?,?,?,?)",
            (trade_id, order_id, link_id, side, price, qty, fee, pnl),
        )
        await db.commit()


async def get_trade(trade_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT trade_id,symbol,direction,entry_price,size,state,realized_pnl,closed_at FROM trades WHERE trade_id=?", (trade_id,)) as cur:
            return await cur.fetchone()


async def update_trade_close(trade_id: str, realized_pnl: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE trades SET realized_pnl=?, closed_at=CURRENT_TIMESTAMP, state='DONE' WHERE trade_id=?",
            (realized_pnl, trade_id),
        )
        await db.commit()


# Convenience alias matching API suggested in runbook
async def close_trade(trade_id: str, realized_pnl: float):
    await update_trade_close(trade_id, realized_pnl)

