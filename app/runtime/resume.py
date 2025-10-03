import asyncio, sqlite3
from decimal import Decimal
from app.strategies.trailing_v2 import TrailingStopStrategyV2
from app.strategies.hedge_v2 import HedgeStrategyV2
from app.strategies.breakeven_v2 import BreakevenStrategyV2

DB_PATH="trades.sqlite"

async def resume_open_trades():
    try:
        def _sync_operation():
            with sqlite3.connect(DB_PATH) as db:
                db.execute("""CREATE TABLE IF NOT EXISTS trades(
                    trade_id TEXT PRIMARY KEY, symbol TEXT, direction TEXT,
                    avg_entry REAL, position_size REAL, leverage REAL,
                    channel_name TEXT, realized_pnl REAL DEFAULT 0, state TEXT
                )""")
                cur = db.execute("SELECT trade_id,symbol,direction,avg_entry,position_size,leverage,channel_name FROM trades WHERE state='OPEN'")
                return cur.fetchall()
        
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(None, _sync_operation)
        
        for (tid,sym,dir_,avg,pos,lev,chan) in rows:
            trail = TrailingStopStrategyV2(tid, sym, dir_, Decimal(str(avg)), Decimal(str(pos)), chan)
            hedge = HedgeStrategyV2(tid, sym, dir_, Decimal(str(avg)), Decimal(str(pos)), int(lev), chan)
            tp2   = BreakevenStrategyV2(tid, sym, dir_, Decimal(str(avg)), chan)
            asyncio.create_task(trail.run())
            asyncio.create_task(hedge.run())
            asyncio.create_task(tp2.run())
    except Exception:
        pass