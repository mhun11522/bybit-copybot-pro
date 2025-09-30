from __future__ import annotations
import asyncio
from datetime import datetime, timedelta
from app.bybit_client import BybitClient
from app.storage.db import aiosqlite, DB_PATH
from app import settings


class OrderCleanupManager:
    def __init__(self, bybit_client: BybitClient):
        self.bybit = bybit_client
        self.cleanup_days = settings.ORDER_CLEANUP_DAYS

    async def start_cleanup_scheduler(self):
        """Start the order cleanup scheduler."""
        print(f"🧹 Starting order cleanup scheduler (cleanup after {self.cleanup_days} days)")
        
        while True:
            try:
                await self.cleanup_old_orders()
                await self.cleanup_stale_signals()
                # Run cleanup every hour
                await asyncio.sleep(3600)
            except Exception as e:
                print(f"Order cleanup error: {e}")
                await asyncio.sleep(3600)

    async def cleanup_old_orders(self):
        """Clean up orders older than ORDER_CLEANUP_DAYS."""
        cutoff_date = datetime.now() - timedelta(days=self.cleanup_days)
        cutoff_timestamp = int(cutoff_date.timestamp())
        
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                # Get old orders
                async with db.execute("""
                    SELECT order_id, symbol, order_link_id 
                    FROM orders 
                    WHERE created_at < ? AND status != 'Filled'
                """, (cutoff_timestamp,)) as cur:
                    old_orders = await cur.fetchall()
                
                if old_orders:
                    print(f"🧹 Found {len(old_orders)} old orders to cleanup")
                    
                    for order_id, symbol, order_link_id in old_orders:
                        try:
                            # Cancel order on Bybit
                            await asyncio.to_thread(
                                self.bybit.cancel_order,
                                symbol=symbol,
                                order_id=order_id
                            )
                            
                            # Mark as deleted in database
                            await db.execute("""
                                UPDATE orders 
                                SET status = 'Deleted', updated_at = ?
                                WHERE order_id = ?
                            """, (int(datetime.now().timestamp()), order_id))
                            
                            print(f"✅ Cleaned up order {order_id} for {symbol}")
                            
                        except Exception as e:
                            print(f"Error cleaning up order {order_id}: {e}")
                    
                    await db.commit()
                    
        except Exception as e:
            print(f"Order cleanup database error: {e}")

    async def cleanup_stale_signals(self):
        """Clean up stale signals older than ORDER_CLEANUP_DAYS."""
        cutoff_date = datetime.now() - timedelta(days=self.cleanup_days)
        cutoff_timestamp = int(cutoff_date.timestamp())
        
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                # Clean up old signal_seen records
                await db.execute("""
                    DELETE FROM signal_seen 
                    WHERE ts < ?
                """, (cutoff_timestamp,))
                
                # Clean up old signal_blocks
                await db.execute("""
                    DELETE FROM signal_blocks 
                    WHERE blocked_at < ?
                """, (cutoff_timestamp,))
                
                await db.commit()
                print(f"✅ Cleaned up stale signals older than {self.cleanup_days} days")
                
        except Exception as e:
            print(f"Signal cleanup database error: {e}")

    async def cleanup_specific_symbol(self, symbol: str):
        """Clean up all orders for a specific symbol."""
        try:
            # Cancel all open orders for symbol
            await asyncio.to_thread(self.bybit.cancel_all, symbol)
            
            # Mark all orders as deleted in database
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    UPDATE orders 
                    SET status = 'Deleted', updated_at = ?
                    WHERE symbol = ? AND status != 'Filled'
                """, (int(datetime.now().timestamp()), symbol))
                await db.commit()
                
            print(f"✅ Cleaned up all orders for {symbol}")
            
        except Exception as e:
            print(f"Error cleaning up {symbol}: {e}")


# Global cleanup manager instance
cleanup_manager = None

async def start_order_cleanup(bybit_client: BybitClient):
    """Start the order cleanup system."""
    global cleanup_manager
    cleanup_manager = OrderCleanupManager(bybit_client)
    asyncio.create_task(cleanup_manager.start_cleanup_scheduler()) 