"""Position management system for ongoing trade monitoring and management."""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from app.bybit.client import BybitClient
from app.core.logging import trade_logger, system_logger
from app.core.strict_config import STRICT_CONFIG
from app.storage.db import get_db_connection


class PositionManager:
    """Manages ongoing positions and trade lifecycle."""
    
    def __init__(self, bybit_client: BybitClient):
        self.bybit = bybit_client
        self.monitoring_tasks = {}
        self.cleanup_interval = 300  # 5 minutes
        self._cleanup_running = False
        self._cleanup_task = None
        # PRIORITY 2 FIX: Track task lifecycle for proper cleanup
        self._task_metadata = {}  # {symbol: {"task": task, "created_at": timestamp, "trade_id": trade_id}}
        self._shutdown = False
    
    async def start_monitoring(self, symbol: str, trade_id: str):
        """Start monitoring a position with proper task lifecycle management."""
        try:
            if symbol in self.monitoring_tasks:
                trade_logger.warning(f"Already monitoring {symbol}")
                return
            
            # PRIORITY 2 FIX: Create monitoring task with metadata tracking
            task = asyncio.create_task(self._monitor_position(symbol, trade_id))
            self.monitoring_tasks[symbol] = task
            
            # Track task metadata for proper cleanup
            import time
            self._task_metadata[symbol] = {
                "task": task,
                "created_at": time.time(),
                "trade_id": trade_id
            }
            
            trade_logger.info(f"Started monitoring position {symbol}", {
                'trade_id': trade_id,
                'symbol': symbol,
                'task_count': len(self.monitoring_tasks)
            })
            
        except Exception as e:
            trade_logger.error(f"Failed to start monitoring {symbol}: {e}", exc_info=True)
    
    async def stop_monitoring(self, symbol: str):
        """Stop monitoring a position with proper cleanup."""
        try:
            if symbol in self.monitoring_tasks:
                task = self.monitoring_tasks[symbol]
                
                # PRIORITY 2 FIX: Properly cancel and wait for task completion
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass  # Expected when cancelling
                except Exception as e:
                    trade_logger.warning(f"Task {symbol} completed with error: {e}")
                
                # Clean up task tracking
                del self.monitoring_tasks[symbol]
                self._task_metadata.pop(symbol, None)
                
                trade_logger.info(f"Stopped monitoring position {symbol}", {
                    'remaining_tasks': len(self.monitoring_tasks)
                })
                
        except Exception as e:
            trade_logger.error(f"Failed to stop monitoring {symbol}: {e}")
    
    async def _monitor_position(self, symbol: str, trade_id: str):
        """Monitor a position for changes and manage lifecycle."""
        try:
            while True:
                try:
                    # Check position status
                    position_info = await self._get_position_info(symbol)
                    
                    if not position_info:
                        # Position closed or doesn't exist
                        await self._handle_position_closed(symbol, trade_id)
                        break
                    
                    # Check for stop loss or take profit triggers
                    await self._check_exit_conditions(symbol, trade_id, position_info)
                    
                    # Update position in database
                    await self._update_position_info(symbol, trade_id, position_info)
                    
                    # Wait before next check
                    await asyncio.sleep(30)  # Check every 30 seconds
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    trade_logger.error(f"Error monitoring {symbol}: {e}")
                    await asyncio.sleep(60)  # Wait longer on error
                    
        except Exception as e:
            trade_logger.error(f"Position monitoring failed for {symbol}: {e}", exc_info=True)
        finally:
            # Clean up monitoring task
            if symbol in self.monitoring_tasks:
                del self.monitoring_tasks[symbol]
    
    async def _get_position_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current position information from Bybit."""
        try:
            result = await self.bybit.positions(STRICT_CONFIG.category, symbol)
            
            if result.get("retCode") == 0:
                positions = result.get("result", {}).get("list", [])
                if positions:
                    return positions[0]
            
            return None
            
        except Exception as e:
            trade_logger.error(f"Failed to get position info for {symbol}: {e}")
            return None
    
    async def _check_exit_conditions(self, symbol: str, trade_id: str, position_info: Dict[str, Any]):
        """Check if position should be closed based on exit conditions."""
        try:
            size = float(position_info.get("size", 0))
            if size == 0:
                return  # No position
            
            unrealised_pnl = float(position_info.get("unrealisedPnl", 0))
            mark_price = float(position_info.get("markPrice", 0))
            entry_price = float(position_info.get("avgPrice", 0))
            
            if entry_price == 0:
                return
            
            # Calculate PnL percentage
            pnl_percentage = (unrealised_pnl / (entry_price * size)) * 100
            
            # Check for stop loss (default -5%)
            if pnl_percentage <= -5.0:
                await self._close_position(symbol, trade_id, "stop_loss", pnl_percentage)
                return
            
            # Check for take profit (default +10%)
            if pnl_percentage >= 10.0:
                await self._close_position(symbol, trade_id, "take_profit", pnl_percentage)
                return
            
            # Log position status
            trade_logger.info(f"Position status for {symbol}", {
                'size': size,
                'pnl': unrealised_pnl,
                'pnl_percentage': pnl_percentage,
                'mark_price': mark_price,
                'entry_price': entry_price
            })
            
        except Exception as e:
            trade_logger.error(f"Error checking exit conditions for {symbol}: {e}")
    
    async def _close_position(self, symbol: str, trade_id: str, reason: str, pnl_percentage: float):
        """Close a position."""
        try:
            # Get current position
            position_info = await self._get_position_info(symbol)
            if not position_info:
                return
            
            size = float(position_info.get("size", 0))
            if size == 0:
                return
            
            # Determine close side
            side = position_info.get("side", "")
            close_side = "Sell" if side == "Buy" else "Buy"
            
            # Place market order to close
            order_body = {
                "category": STRICT_CONFIG.category,
                "symbol": symbol,
                "side": close_side,
                "orderType": "Market",
                "qty": str(size),
                "reduceOnly": True,
                "positionIdx": 0
            }
            
            result = await self.bybit.place_order(order_body)
            
            if result.get("retCode") == 0:
                trade_logger.position_closed(
                    symbol, side, str(size), 
                    str(position_info.get("unrealisedPnl", 0)), reason
                )
                
                # Update database
                await self._update_trade_status(trade_id, "CLOSED", pnl_percentage)
                
                # Stop monitoring
                await self.stop_monitoring(symbol)
                
            else:
                trade_logger.error(f"Failed to close position {symbol}: {result}")
                
        except Exception as e:
            trade_logger.error(f"Error closing position {symbol}: {e}", exc_info=True)
    
    async def _handle_position_closed(self, symbol: str, trade_id: str):
        """Handle when position is closed externally."""
        try:
            trade_logger.info(f"Position {symbol} was closed externally")
            
            # Update database
            await self._update_trade_status(trade_id, "CLOSED", 0.0)
            
            # Stop monitoring
            await self.stop_monitoring(symbol)
            
        except Exception as e:
            trade_logger.error(f"Error handling position close for {symbol}: {e}")
    
    async def _update_position_info(self, symbol: str, trade_id: str, position_info: Dict[str, Any]):
        """Update position information in database."""
        try:
            size = float(position_info.get("size", 0))
            unrealised_pnl = float(position_info.get("unrealisedPnl", 0))
            mark_price = float(position_info.get("markPrice", 0))
            
            async with get_db_connection() as db:
                await db.execute("""
                    UPDATE trades_new SET 
                        position_size = ?, 
                        realized_pnl = ?,
                        state = ?
                    WHERE trade_id = ?
                """, (size, unrealised_pnl, "ACTIVE", trade_id))
                
                await db.commit()
                
        except Exception as e:
            trade_logger.error(f"Failed to update position info for {symbol}: {e}")
    
    async def _update_trade_status(self, trade_id: str, status: str, pnl_percentage: float):
        """Update trade status in database."""
        try:
            async with get_db_connection() as db:
                await db.execute("""
                    UPDATE trades_new SET 
                        state = ?, 
                        closed_at = ?,
                        realized_pnl = ?
                    WHERE trade_id = ?
                """, (status, datetime.now().isoformat(), pnl_percentage, trade_id))
                
                await db.execute("""
                    UPDATE active_trades SET status = ?
                    WHERE trade_id = ?
                """, (status, trade_id))
                
                await db.commit()
                
        except Exception as e:
            trade_logger.error(f"Failed to update trade status: {e}")
    
    async def get_all_positions(self) -> List[Dict[str, Any]]:
        """Get all active positions."""
        try:
            result = await self.bybit.positions(STRICT_CONFIG.category, "")
            
            if result.get("retCode") == 0:
                return result.get("result", {}).get("list", [])
            
            return []
            
        except Exception as e:
            trade_logger.error(f"Failed to get all positions: {e}")
            return []
    
    async def cleanup_expired_positions(self):
        """Clean up expired or stale positions."""
        try:
            # Get all active trades from database
            db = await get_db_connection()
            async with db:
                cursor = await db.execute("""
                    SELECT trade_id, symbol, created_at 
                    FROM active_trades 
                    WHERE status = 'ACTIVE'
                """)
                
                active_trades = await cursor.fetchall()
                
                for trade in active_trades:
                    trade_id, symbol, created_at = trade
                    
                    # Check if trade is older than 24 hours
                    created_time = datetime.fromisoformat(created_at)
                    if datetime.now() - created_time > timedelta(hours=24):
                        trade_logger.info(f"Cleaning up expired trade: {symbol}")
                        await self._close_position(symbol, trade_id, "expired", 0.0)
                
        except Exception as e:
            trade_logger.error(f"Cleanup failed: {e}")
    
    async def start_cleanup_scheduler(self):
        """Start periodic cleanup of expired positions."""
        # Prevent multiple instances
        if self._cleanup_running or self._cleanup_task is not None:
            trade_logger.info("Cleanup scheduler already running, skipping start")
            return
            
        self._cleanup_running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        trade_logger.info("Starting cleanup scheduler")
    
    async def _cleanup_loop(self):
        """Internal cleanup loop."""
        try:
            while self._cleanup_running:
                try:
                    await self.cleanup_expired_positions()
                    await asyncio.sleep(self.cleanup_interval)
                except Exception as e:
                    trade_logger.error(f"Cleanup scheduler error: {e}")
                    await asyncio.sleep(60)
        finally:
            self._cleanup_running = False
            self._cleanup_task = None
            trade_logger.info("Cleanup scheduler stopped")
    
    async def stop_cleanup_scheduler(self):
        """Stop the cleanup scheduler."""
        if self._cleanup_task is not None:
            self._cleanup_running = False
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
    
    async def shutdown(self):
        """Shutdown position manager and clean up all tasks."""
        system_logger.info("Shutting down position manager...")
        self._shutdown = True
        
        # Stop cleanup scheduler
        await self.stop_cleanup_scheduler()
        
        # PRIORITY 2 FIX: Cancel all monitoring tasks
        tasks_to_cancel = []
        for symbol, task in self.monitoring_tasks.items():
            tasks_to_cancel.append((symbol, task))
        
        # Cancel all tasks
        for symbol, task in tasks_to_cancel:
            task.cancel()
        
        # Wait for all tasks to complete
        if tasks_to_cancel:
            try:
                await asyncio.wait([task for _, task in tasks_to_cancel], timeout=5.0)
            except asyncio.TimeoutError:
                system_logger.warning("Some monitoring tasks did not complete within timeout")
        
        # Clear all tracking data
        self.monitoring_tasks.clear()
        self._task_metadata.clear()
        
        system_logger.info("Position manager shutdown complete", {
            'cancelled_tasks': len(tasks_to_cancel)
        })


# Global manager instance
_manager_instance = None

async def get_position_manager() -> PositionManager:
    """Get or create position manager instance."""
    global _manager_instance
    if _manager_instance is None:
        from app.bybit.client import get_bybit_client
        bybit_client = get_bybit_client()
        _manager_instance = PositionManager(bybit_client)
    return _manager_instance