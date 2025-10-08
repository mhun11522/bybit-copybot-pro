#!/usr/bin/env python3
"""
Simulated TP/SL Manager

Implements custom TP/SL logic when Bybit's native set_trading_stop API
is not available (e.g., in Demo/Futurus environment).
"""

import asyncio
from decimal import Decimal
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from app.core.logging import system_logger
from app.bybit.client import get_bybit_client
from app.core.environment_detector import get_environment_detector

@dataclass
class TPLevel:
    """Take Profit level definition."""
    percentage: Decimal
    quantity_pct: Decimal  # What percentage of position to close
    triggered: bool = False
    executed: bool = False

@dataclass
class SLLevel:
    """Stop Loss level definition."""
    percentage: Decimal
    triggered: bool = False
    executed: bool = False

@dataclass
class SimulatedTPSLOrder:
    """Simulated TP/SL order."""
    symbol: str
    side: str  # 'Buy' or 'Sell'
    position_size: Decimal
    entry_price: Decimal
    tp_levels: List[TPLevel]
    sl_level: Optional[SLLevel]
    created_at: datetime
    trade_id: str
    callback: Optional[Callable] = None

class SimulatedTPSLManager:
    """Manages simulated TP/SL orders when native API is unavailable."""
    
    def __init__(self):
        self.active_orders: Dict[str, SimulatedTPSLOrder] = {}
        self.price_monitor_task: Optional[asyncio.Task] = None
        self._client = None
        self._running = False
        self._monitor_interval = 2.0  # Check prices every 2 seconds
    
    async def start(self):
        """Start the simulated TP/SL monitoring."""
        if self._running:
            return
        
        self._client = get_bybit_client()
        self._running = True
        
        # Start price monitoring task
        self.price_monitor_task = asyncio.create_task(self._monitor_prices())
        
        system_logger.info("Simulated TP/SL manager started", {
            'monitor_interval': self._monitor_interval
        })
    
    async def stop(self):
        """Stop the simulated TP/SL monitoring."""
        self._running = False
        
        if self.price_monitor_task:
            self.price_monitor_task.cancel()
            try:
                await self.price_monitor_task
            except asyncio.CancelledError:
                pass
        
        system_logger.info("Simulated TP/SL manager stopped")
    
    async def add_tpsl_order(
        self,
        symbol: str,
        side: str,
        position_size: Decimal,
        entry_price: Decimal,
        tp_levels: List[Decimal],
        sl_percentage: Decimal,
        trade_id: str,
        callback: Optional[Callable] = None
    ) -> bool:
        """Add a simulated TP/SL order."""
        try:
            # Convert TP percentages to TPLevel objects
            tp_objects = []
            for i, tp_pct in enumerate(tp_levels):
                # Default to closing 50% of position per TP level
                quantity_pct = Decimal("0.5") if len(tp_levels) > 1 else Decimal("1.0")
                tp_objects.append(TPLevel(
                    percentage=tp_pct,
                    quantity_pct=quantity_pct
                ))
            
            # Create SL level
            sl_level = SLLevel(percentage=sl_percentage)
            
            order = SimulatedTPSLOrder(
                symbol=symbol,
                side=side,
                position_size=position_size,
                entry_price=entry_price,
                tp_levels=tp_objects,
                sl_level=sl_level,
                created_at=datetime.now(),
                trade_id=trade_id,
                callback=callback
            )
            
            self.active_orders[trade_id] = order
            
            system_logger.info(f"Added simulated TP/SL order: {trade_id}", {
                'symbol': symbol,
                'side': side,
                'position_size': str(position_size),
                'entry_price': str(entry_price),
                'tp_levels': [str(tp.percentage) for tp in tp_objects],
                'sl_percentage': str(sl_percentage)
            })
            
            return True
            
        except Exception as e:
            system_logger.error(f"Failed to add simulated TP/SL order: {e}", exc_info=True)
            return False
    
    async def remove_tpsl_order(self, trade_id: str) -> bool:
        """Remove a simulated TP/SL order."""
        if trade_id in self.active_orders:
            del self.active_orders[trade_id]
            system_logger.info(f"Removed simulated TP/SL order: {trade_id}")
            return True
        return False
    
    async def _monitor_prices(self):
        """Monitor prices for all active TP/SL orders."""
        while self._running:
            try:
                if not self.active_orders:
                    await asyncio.sleep(self._monitor_interval)
                    continue
                
                # Get current prices for all active symbols
                symbols = list(set(order.symbol for order in self.active_orders.values()))
                
                for symbol in symbols:
                    await self._check_symbol_prices(symbol)
                
                await asyncio.sleep(self._monitor_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                system_logger.error(f"Error in price monitoring: {e}", exc_info=True)
                await asyncio.sleep(self._monitor_interval)
    
    async def _check_symbol_prices(self, symbol: str):
        """Check prices for a specific symbol."""
        try:
            # Get current market price
            ticker_result = await self._client.get_ticker(symbol)
            if not ticker_result or 'result' not in ticker_result:
                return
            
            # Access lastPrice through the list structure
            if 'list' in ticker_result['result'] and ticker_result['result']['list']:
                current_price = Decimal(str(ticker_result['result']['list'][0]['lastPrice']))
            else:
                system_logger.error(f"No list data in ticker result for {symbol}")
                return
            
            # Check all orders for this symbol
            symbol_orders = [order for order in self.active_orders.values() 
                           if order.symbol == symbol]
            
            for order in symbol_orders:
                await self._check_order_triggers(order, current_price)
                
        except Exception as e:
            system_logger.error(f"Failed to check prices for {symbol}: {e}")
    
    async def _check_order_triggers(self, order: SimulatedTPSLOrder, current_price: Decimal):
        """Check if TP/SL levels are triggered for an order."""
        try:
            entry_price = order.entry_price
            side = order.side
            
            # Calculate price changes
            if side == 'Buy':
                # For long positions: profit when price goes up, loss when down
                price_change_pct = ((current_price - entry_price) / entry_price) * 100
            else:
                # For short positions: profit when price goes down, loss when up
                price_change_pct = ((entry_price - current_price) / entry_price) * 100
            
            # Check TP levels
            for tp_level in order.tp_levels:
                if not tp_level.triggered and price_change_pct >= tp_level.percentage:
                    await self._execute_tp_level(order, tp_level, current_price)
            
            # Check SL level
            if (order.sl_level and not order.sl_level.triggered and 
                price_change_pct <= -order.sl_level.percentage):
                await self._execute_sl_level(order, current_price)
                
        except Exception as e:
            system_logger.error(f"Failed to check triggers for {order.trade_id}: {e}")
    
    async def _execute_tp_level(self, order: SimulatedTPSLOrder, tp_level: TPLevel, current_price: Decimal):
        """Execute a take profit level."""
        try:
            tp_level.triggered = True
            
            # Calculate quantity to close
            close_quantity = order.position_size * tp_level.quantity_pct
            
            # Determine close side (opposite of entry)
            close_side = 'Sell' if order.side == 'Buy' else 'Buy'
            
            # Create market close order
            close_result = await self._client.create_order(
                category='linear',
                symbol=order.symbol,
                side=close_side,
                order_type='Market',
                qty=str(close_quantity),
                time_in_force='IOC',
                reduce_only=True,
                position_idx=0,
                order_link_id=f"sim_tp_{order.trade_id}_{tp_level.percentage}"
            )
            
            if close_result and close_result.get('retCode') == 0:
                tp_level.executed = True
                
                system_logger.info(f"Executed simulated TP: {order.trade_id}", {
                    'symbol': order.symbol,
                    'tp_percentage': str(tp_level.percentage),
                    'close_quantity': str(close_quantity),
                    'close_price': str(current_price),
                    'order_id': close_result.get('result', {}).get('orderId')
                })
                
                # Call callback if provided
                if order.callback:
                    try:
                        await order.callback('tp_executed', {
                            'trade_id': order.trade_id,
                            'tp_percentage': tp_level.percentage,
                            'close_price': current_price
                        })
                    except Exception as e:
                        system_logger.error(f"TP callback error: {e}")
                
            else:
                system_logger.error(f"Failed to execute TP order: {close_result}")
                
        except Exception as e:
            system_logger.error(f"Failed to execute TP level: {e}", exc_info=True)
    
    async def _execute_sl_level(self, order: SimulatedTPSLOrder, current_price: Decimal):
        """Execute a stop loss level."""
        try:
            order.sl_level.triggered = True
            
            # Determine close side (opposite of entry)
            close_side = 'Sell' if order.side == 'Buy' else 'Buy'
            
            # Create market close order for entire position
            close_result = await self._client.create_order(
                category='linear',
                symbol=order.symbol,
                side=close_side,
                order_type='Market',
                qty=str(order.position_size),
                time_in_force='IOC',
                reduce_only=True,
                position_idx=0,
                order_link_id=f"sim_sl_{order.trade_id}"
            )
            
            if close_result and close_result.get('retCode') == 0:
                order.sl_level.executed = True
                
                system_logger.info(f"Executed simulated SL: {order.trade_id}", {
                    'symbol': order.symbol,
                    'sl_percentage': str(order.sl_level.percentage),
                    'close_quantity': str(order.position_size),
                    'close_price': str(current_price),
                    'order_id': close_result.get('result', {}).get('orderId')
                })
                
                # Call callback if provided
                if order.callback:
                    try:
                        await order.callback('sl_executed', {
                            'trade_id': order.trade_id,
                            'sl_percentage': order.sl_level.percentage,
                            'close_price': current_price
                        })
                    except Exception as e:
                        system_logger.error(f"SL callback error: {e}")
                
                # Remove order since SL closes entire position
                await self.remove_tpsl_order(order.trade_id)
                
            else:
                system_logger.error(f"Failed to execute SL order: {close_result}")
                
        except Exception as e:
            system_logger.error(f"Failed to execute SL level: {e}", exc_info=True)
    
    def get_active_orders(self) -> Dict[str, SimulatedTPSLOrder]:
        """Get all active simulated TP/SL orders."""
        return self.active_orders.copy()
    
    def get_order_status(self, trade_id: str) -> Optional[Dict]:
        """Get status of a specific order."""
        if trade_id not in self.active_orders:
            return None
        
        order = self.active_orders[trade_id]
        
        tp_status = []
        for tp in order.tp_levels:
            tp_status.append({
                'percentage': str(tp.percentage),
                'quantity_pct': str(tp.quantity_pct),
                'triggered': tp.triggered,
                'executed': tp.executed
            })
        
        sl_status = None
        if order.sl_level:
            sl_status = {
                'percentage': str(order.sl_level.percentage),
                'triggered': order.sl_level.triggered,
                'executed': order.sl_level.executed
            }
        
        return {
            'trade_id': trade_id,
            'symbol': order.symbol,
            'side': order.side,
            'position_size': str(order.position_size),
            'entry_price': str(order.entry_price),
            'tp_levels': tp_status,
            'sl_level': sl_status,
            'created_at': order.created_at.isoformat()
        }

# Global instance
_simulated_tpsl_manager = None

def get_simulated_tpsl_manager() -> SimulatedTPSLManager:
    """Get global simulated TP/SL manager instance."""
    global _simulated_tpsl_manager
    if _simulated_tpsl_manager is None:
        _simulated_tpsl_manager = SimulatedTPSLManager()
    return _simulated_tpsl_manager

async def start_simulated_tpsl():
    """Start the simulated TP/SL manager."""
    manager = get_simulated_tpsl_manager()
    await manager.start()

async def stop_simulated_tpsl():
    """Stop the simulated TP/SL manager."""
    manager = get_simulated_tpsl_manager()
    await manager.stop()
