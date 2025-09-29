import asyncio
from app.storage import db


def test_db_flow():
	async def demo():
		await db.init_db()
		await db.save_trade("TRD-1", "BTCUSDT", "BUY", 20000.0, 0.001, "ENTRIES_PLACED")
		async with db.aiosqlite.connect(db.DB_PATH) as conn:
			async with conn.execute("SELECT * FROM trades") as cur:
				rows = await cur.fetchall()
				print(rows)
				assert len(rows) > 0
	asyncio.run(demo())