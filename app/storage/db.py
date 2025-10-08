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
            self._conn = sqlite3.connect(path, check_same_thread=False)

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
    """Get a database connection."""
    return aiosqlite.connect(DB_PATH)


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Lightweight migrations: ensure missing columns exist
        await _migrate_trades_table(db)
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
            realized_pnl REAL DEFAULT 0,
            closed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
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
    try:
        cols = []
        async with db.execute("PRAGMA table_info(trades)") as cur:
            rows = await cur.fetchall()
            cols = [r[1] for r in rows]  # r[1] is column name
        # Add realized_pnl if missing
        if "realized_pnl" not in cols:
            await db.execute("ALTER TABLE trades ADD COLUMN realized_pnl REAL DEFAULT 0")
        # Add closed_at if missing
        if "closed_at" not in cols:
            await db.execute("ALTER TABLE trades ADD COLUMN closed_at TIMESTAMP")
        # Add created_at if missing
        if "created_at" not in cols:
            await db.execute("ALTER TABLE trades ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
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

