import aiosqlite, time, math
from app.config.settings import DEDUP_SECONDS, DUP_TOLERANCE_PCT, BLOCK_SAME_DIR_SECONDS

DB_PATH = "trades.sqlite"

async def _ensure_tables():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS signal_guard(
            chat_id INTEGER,
            symbol  TEXT,
            direction TEXT,
            entry1  REAL,
            entry2  REAL,
            ts      INTEGER,
            PRIMARY KEY(chat_id, symbol, direction, ts)
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS symbol_dir_block(
            symbol  TEXT,
            direction TEXT,
            until_ts INTEGER,
            PRIMARY KEY(symbol, direction)
        )""")
        await db.commit()

def _within_tolerance(a: float, b: float, pct: float) -> bool:
    if a == 0 or b == 0: return False
    diff = abs(a - b) / ((a + b) / 2.0) * 100.0
    return diff <= pct

async def block_same_symbol_dir(symbol: str, direction: str):
    await _ensure_tables()
    until_ts = int(time.time()) + BLOCK_SAME_DIR_SECONDS
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""INSERT OR REPLACE INTO symbol_dir_block(symbol,direction,until_ts)
                            VALUES(?,?,?)""", (symbol.upper(), direction.upper(), until_ts))
        await db.commit()

async def is_symbol_dir_blocked(symbol: str, direction: str) -> bool:
    await _ensure_tables()
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""SELECT until_ts FROM symbol_dir_block
                                 WHERE symbol=? AND direction=?""",
                              (symbol.upper(), direction.upper())) as cur:
            row = await cur.fetchone()
            return bool(row and row[0] > now)

async def is_new_signal(chat_id: int, symbol: str, direction: str, entries: list[str]) -> bool:
    """
    Dedup within 3h window with ±5% tolerance on entries.
    Additionally, block same symbol+direction within the same window.
    """
    await _ensure_tables()
    now = int(time.time())
    e1 = float(entries[0]) if entries else math.nan
    e2 = float(entries[1]) if len(entries) > 1 else e1

    # Symbol/dir block?
    if await is_symbol_dir_blocked(symbol, direction):
        return False

    floor_ts = now - DEDUP_SECONDS
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""SELECT entry1, entry2, ts FROM signal_guard
                                 WHERE chat_id=? AND symbol=? AND direction=? AND ts>=?""",
                              (int(chat_id), symbol.upper(), direction.upper(), floor_ts)) as cur:
            async for r1, r2, ts in cur:
                if _within_tolerance(e1, float(r1), DUP_TOLERANCE_PCT) and _within_tolerance(e2, float(r2), DUP_TOLERANCE_PCT):
                    return False
        # new → insert row
        await db.execute("""INSERT OR REPLACE INTO signal_guard(chat_id,symbol,direction,entry1,entry2,ts)
                            VALUES(?,?,?,?,?,?)""",
                         (int(chat_id), symbol.upper(), direction.upper(), e1, e2, now))
        await db.commit()
    # Also start a symbol/dir block for the same window
    await block_same_symbol_dir(symbol, direction)
    return True
