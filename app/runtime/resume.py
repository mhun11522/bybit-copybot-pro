import asyncio, sqlite3
from decimal import Decimal
from app.strategies.trailing_v2 import TrailingStopStrategyV2
from app.strategies.hedge_v2 import HedgeStrategyV2
from app.strategies.breakeven_v2 import BreakevenStrategyV2
from app.storage.db import DB_PATH

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
            # Create tasks with proper cleanup tracking
            trail_task = asyncio.create_task(trail.run())
            hedge_task = asyncio.create_task(hedge.run())
            tp2_task = asyncio.create_task(tp2.run())
            
            # Store tasks for cleanup
            if not hasattr(resume_open_trades, '_active_tasks'):
                resume_open_trades._active_tasks = set()
            
            resume_open_trades._active_tasks.update([trail_task, hedge_task, tp2_task])
            
            # Add done callbacks to remove completed tasks
            for task in [trail_task, hedge_task, tp2_task]:
                task.add_done_callback(lambda t: resume_open_trades._active_tasks.discard(t))
    except Exception as e:
        system_logger.error(f"Error resuming trade strategies: {e}", exc_info=True)

async def cleanup_resume_tasks():
    """Clean up all active resume tasks"""
    if hasattr(resume_open_trades, '_active_tasks'):
        active_tasks = resume_open_trades._active_tasks.copy()
        if active_tasks:
            system_logger.info(f"Cancelling {len(active_tasks)} active resume tasks")
            for task in active_tasks:
                if not task.done():
                    task.cancel()
            # Wait for tasks to complete
            await asyncio.gather(*active_tasks, return_exceptions=True)
            resume_open_trades._active_tasks.clear()