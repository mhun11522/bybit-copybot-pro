import hashlib
import aiosqlite
from app.storage.db import DB_PATH


def sig_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def is_new_signal(channel_id: int, text: str) -> bool:
    h = sig_hash(text)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS signal_seen (
                channel_id INTEGER,
                hash TEXT,
                ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (channel_id, hash)
            )
            """
        )
        try:
            await db.execute("INSERT INTO signal_seen (channel_id, hash) VALUES (?,?)", (channel_id, h))
            await db.commit()
            return True
        except Exception:
            return False

