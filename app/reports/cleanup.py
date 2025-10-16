"""
Order cleanup: Delete orders not opened within 6 days (Requirement #5)
"""

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.config.settings import TIMEZONE
from app.core.strict_config import STRICT_CONFIG
from app.bybit.client import BybitClient
from app.storage.db import aiosqlite, DB_PATH
from app.telegram.output import send_message

TZ = ZoneInfo(TIMEZONE)
MAX_ORDER_AGE_DAYS = 6

async def cleanup_old_orders():
    """
    Find and cancel orders that haven't opened a position within 6 days.
    Requirement #5: "If Order not opened within 6 days, delete the signal"
    """
    cutoff = datetime.now(TZ) - timedelta(days=MAX_ORDER_AGE_DAYS)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    
    from app.bybit.client import get_bybit_client
    bybit = get_bybit_client()
    deleted_count = 0
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Find trades that are still pending (no position opened) after 6 days
        # Only clean up orders that haven't opened positions yet
        async with db.execute("""
            SELECT trade_id, symbol, channel_name, created_at
            FROM trades
            WHERE state IN ('ORDER_PLACED', 'ORDER_PENDING', 'ENTRY_WAITING')
            AND created_at < ?
        """, (cutoff_str,)) as cur:
            old_trades = await cur.fetchall()
        
        for trade_id, symbol, channel_name, created_at in old_trades:
            try:
                # Cancel all orders for this symbol
                await bybit.cancel_all(STRICT_CONFIG.category, symbol)
                
                # Mark as DONE/CANCELLED in database
                await db.execute("""
                    UPDATE trades SET state='DONE', closed_at=CURRENT_TIMESTAMP
                    WHERE trade_id=?
                """, (trade_id,))
                
                deleted_count += 1
                
                # Notify via Telegram
                await send_message(f"""**✔️ ORDER RADERAD ✔️**
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

📍 Info: Order ej öppnad inom 6 dagar (raderad enligt reglerna)

**✔️ ORDER DELETED ✔️**
📢 From channel: {channel_name}
📊 Symbol: {symbol}

📍 Info: Order not opened within 6 days (deleted per rules)""")
                
            except Exception as e:
                system_logger.warning(f"Failed to cleanup order {trade_id}: {e}", {
                    "trade_id": trade_id,
                    "error": str(e)
                })
        
        await db.commit()
    
    if deleted_count > 0:
        system_logger.info(f"Cleaned up {deleted_count} old orders (>6 days)", {
            "deleted_count": deleted_count,
            "age_days": 6
        })
    
    return deleted_count

async def cleanup_scheduler():
    """Run cleanup check every 6 hours"""
    while True:
        try:
            await cleanup_old_orders()
        except Exception as e:
            system_logger.error(f"Cleanup scheduler error: {e}", exc_info=True)
        
        # Check every 6 hours
        await asyncio.sleep(6 * 3600)
