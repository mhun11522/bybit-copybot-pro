"""Enhanced trade execution system for Bybit copybot."""

import asyncio
from decimal import Decimal, ROUND_DOWN
from typing import Dict, Any, Optional, List
from datetime import datetime
from app.bybit.client import BybitClient
from app.core.logging import trade_logger, bybit_logger
from app.config.settings import (
    RISK_PER_TRADE, MAX_CONCURRENT_TRADES, LEV_MIN, LEV_MAX,
    IM_PER_ENTRY_USDT, CATEGORY
)
from app.config.trading_config import (
    is_trading_enabled, is_live_trading, is_dry_run,
    get_channel_risk_multiplier, is_symbol_blacklisted,
    is_trading_hours, MAX_POSITION_SIZE_USDT, MAX_LEVERAGE
)
from app.trade.planner import plan_dual_entries
from app.storage.db import get_db_connection


class TradeExecutor:
    """Handles actual trade execution based on processed signals."""
    
    def __init__(self, bybit_client: BybitClient):
        self.bybit = bybit_client
        self.active_trades = {}  # symbol -> trade_info
        self.max_concurrent = MAX_CONCURRENT_TRADES
        
    async def execute_signal(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a trade based on processed signal.
        
        Args:
            signal_data: {
                'symbol': str,
                'direction': str,  # 'BUY' or 'SELL'
                'entries': List[str],  # Entry prices
                'channel_name': str,
                'leverage': Optional[int],
                'risk_percent': Optional[float]
            }
        
        Returns:
            Dict with execution results
        """
        try:
            symbol = signal_data['symbol']
            direction = signal_data['direction']
            entries = signal_data['entries']
            channel_name = signal_data['channel_name']
            
            # Check trading configuration
            if not is_trading_enabled():
                return {
                    'success': False,
                    'reason': 'Trading disabled (MONITOR mode)',
                    'symbol': symbol
                }
            
            # Check trading hours
            if not is_trading_hours():
                return {
                    'success': False,
                    'reason': 'Outside trading hours',
                    'symbol': symbol
                }
            
            # Check if symbol is blacklisted
            if is_symbol_blacklisted(symbol):
                return {
                    'success': False,
                    'reason': 'Symbol is blacklisted',
                    'symbol': symbol
                }
            
            # Check if we can trade this symbol
            if not await self._can_trade_symbol(symbol, direction):
                return {
                    'success': False,
                    'reason': 'Symbol blocked or max concurrent trades reached',
                    'symbol': symbol
                }
            
            # Validate symbol exists on Bybit
            if not await self.bybit.symbol_exists(CATEGORY, symbol):
                trade_logger.warning(f"Symbol {symbol} not available on Bybit", {
                    'symbol': symbol,
                    'channel': channel_name
                })
                return {
                    'success': False,
                    'reason': 'Symbol not available on Bybit',
                    'symbol': symbol
                }
            
            # Get account balance
            balance = await self._get_account_balance()
            if balance <= 0:
                return {
                    'success': False,
                    'reason': 'Insufficient balance',
                    'balance': balance
                }
            
            # Calculate position size
            position_size = await self._calculate_position_size(
                signal_data, balance
            )
            
            if position_size <= 0:
                return {
                    'success': False,
                    'reason': 'Position size too small',
                    'position_size': position_size
                }
            
            # Execute the trade (or simulate in dry run mode)
            if is_dry_run():
                trade_result = await self._simulate_trade(
                    symbol, direction, entries, position_size, channel_name
                )
            else:
                trade_result = await self._place_trade(
                    symbol, direction, entries, position_size, channel_name
                )
            
            if trade_result['success']:
                # Record trade in database
                await self._record_trade(signal_data, trade_result)
                
                # Add to active trades
                self.active_trades[symbol] = {
                    'direction': direction,
                    'size': position_size,
                    'channel': channel_name,
                    'timestamp': datetime.now(),
                    'order_ids': trade_result.get('order_ids', [])
                }
                
                trade_logger.trade_event('trade_executed', symbol, {
                    'direction': direction,
                    'size': position_size,
                    'channel': channel_name,
                    'order_ids': trade_result.get('order_ids', [])
                })
            
            return trade_result
            
        except Exception as e:
            trade_logger.error(f"Trade execution failed for {symbol}", {
                'symbol': symbol,
                'error': str(e),
                'channel': channel_name
            }, exc_info=True)
            return {
                'success': False,
                'reason': f'Execution error: {str(e)}',
                'symbol': symbol
            }
    
    async def _can_trade_symbol(self, symbol: str, direction: str) -> bool:
        """Check if we can trade this symbol."""
        # Check max concurrent trades
        if len(self.active_trades) >= self.max_concurrent:
            return False
        
        # Check if symbol is already being traded
        if symbol in self.active_trades:
            return False
        
        # Check symbol blocking in database
        async with get_db_connection() as db:
            cursor = await db.execute("""
                SELECT until_ts FROM symbol_dir_block 
                WHERE symbol = ? AND direction = ? AND until_ts > ?
            """, (symbol, direction, int(datetime.now().timestamp())))
            
            if await cursor.fetchone():
                return False
        
        return True
    
    async def _get_account_balance(self) -> float:
        """Get USDT balance from account."""
        try:
            result = await self.bybit.wallet_balance("USDT")
            if result.get("retCode") == 0:
                accounts = result.get("result", {}).get("list", [])
                if accounts:
                    return float(accounts[0].get("totalEquity", 0))
        except Exception as e:
            bybit_logger.error(f"Failed to get account balance: {e}")
        return 0.0
    
    async def _calculate_position_size(
        self, 
        signal_data: Dict[str, Any], 
        balance: float
    ) -> float:
        """Calculate position size based on risk management."""
        try:
            # Get risk percentage from signal or use default
            risk_percent = signal_data.get('risk_percent', RISK_PER_TRADE)
            
            # Apply channel risk multiplier
            channel_name = signal_data.get('channel_name', 'DEFAULT')
            risk_multiplier = get_channel_risk_multiplier(channel_name)
            adjusted_risk = risk_percent * risk_multiplier
            
            # Calculate position value
            position_value = balance * adjusted_risk
            
            # Apply maximum position size limit
            position_value = min(position_value, MAX_POSITION_SIZE_USDT)
            
            # Get entry price (use first entry)
            entry_price = float(signal_data['entries'][0])
            
            # Calculate position size in contracts
            position_size = position_value / entry_price
            
            # Apply minimum size check
            min_size = 0.001  # Minimum position size
            if position_size < min_size:
                return 0.0
            
            # Round down to avoid over-leveraging
            return float(Decimal(str(position_size)).quantize(
                Decimal('0.001'), rounding=ROUND_DOWN
            ))
            
        except Exception as e:
            trade_logger.error(f"Position size calculation failed: {e}")
            return 0.0
    
    async def _simulate_trade(
        self, 
        symbol: str, 
        direction: str, 
        entries: List[str], 
        position_size: float,
        channel_name: str
    ) -> Dict[str, Any]:
        """Simulate trade execution for dry run mode."""
        try:
            # Get leverage
            leverage = await self._get_leverage(symbol)
            
            # Plan dual entries
            planned_prices, splits = plan_dual_entries(direction, entries)
            
            # Simulate order IDs
            order_ids = [f"SIM_{symbol}_{int(datetime.now().timestamp())}_{i}" for i in range(len(planned_prices))]
            
            trade_logger.info(f"DRY RUN: Simulated trade for {symbol}", {
                'symbol': symbol,
                'direction': direction,
                'entries': planned_prices,
                'position_size': position_size,
                'leverage': leverage,
                'order_ids': order_ids
            })
            
            return {
                'success': True,
                'order_ids': order_ids,
                'leverage': leverage,
                'position_size': position_size,
                'simulated': True
            }
            
        except Exception as e:
            trade_logger.error(f"Trade simulation failed: {e}", {
                'symbol': symbol,
                'direction': direction
            }, exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    async def _place_trade(
        self, 
        symbol: str, 
        direction: str, 
        entries: List[str], 
        position_size: float,
        channel_name: str
    ) -> Dict[str, Any]:
        """Place the actual trade on Bybit."""
        try:
            # Get leverage
            leverage = await self._get_leverage(symbol)
            
            # Set leverage
            await self.bybit.set_leverage(
                CATEGORY, symbol, leverage, leverage
            )
            
            # Plan dual entries
            planned_prices, splits = plan_dual_entries(direction, entries)
            
            order_ids = []
            
            # Place dual entry orders
            for i, (price, split) in enumerate(zip(planned_prices, splits)):
                qty = str(position_size * float(split))
                link_id = f"{symbol}_{direction}_{int(datetime.now().timestamp())}_{i}"
                
                order_body = {
                    "category": CATEGORY,
                    "symbol": symbol,
                    "side": direction,
                    "orderType": "Limit",
                    "qty": qty,
                    "price": price,
                    "timeInForce": "PostOnly",
                    "reduceOnly": False,
                    "positionIdx": 0,
                    "orderLinkId": link_id
                }
                
                result = await self.bybit.place_order(order_body)
                
                if result.get("retCode") == 0:
                    order_id = result.get("result", {}).get("orderId")
                    if order_id:
                        order_ids.append(order_id)
                        trade_logger.order_placed(
                            symbol, "Limit", direction, qty, price, order_id
                        )
                else:
                    bybit_logger.bybit_error(
                        result.get("retCode", -1),
                        f"place_order_{i}",
                        {"symbol": symbol, "side": direction}
                    )
            
            return {
                'success': len(order_ids) > 0,
                'order_ids': order_ids,
                'leverage': leverage,
                'position_size': position_size
            }
            
        except Exception as e:
            bybit_logger.error(f"Trade placement failed: {e}", {
                'symbol': symbol,
                'direction': direction
            }, exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _get_leverage(self, symbol: str) -> int:
        """Get appropriate leverage for symbol."""
        try:
            max_leverage = await self.bybit.get_max_leverage(CATEGORY, symbol)
            # Use minimum of configured max, trading config max, and Bybit's max
            leverage = min(LEV_MAX, MAX_LEVERAGE, max_leverage)
            # Ensure it's at least the minimum
            return max(int(leverage), LEV_MIN)
        except Exception:
            return LEV_MIN
    
    async def _record_trade(
        self, 
        signal_data: Dict[str, Any], 
        trade_result: Dict[str, Any]
    ):
        """Record trade in database."""
        try:
            trade_id = f"{signal_data['symbol']}_{int(datetime.now().timestamp())}"
            
            async with get_db_connection() as db:
                await db.execute("""
                    INSERT INTO trades_new (
                        trade_id, symbol, direction, entry_price, size,
                        avg_entry, position_size, leverage, channel_name,
                        state, realized_pnl, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_id,
                    signal_data['symbol'],
                    signal_data['direction'],
                    signal_data['entries'][0],
                    trade_result.get('position_size', 0),
                    signal_data['entries'][0],  # avg_entry same as entry for now
                    trade_result.get('position_size', 0),
                    trade_result.get('leverage', 1),
                    signal_data['channel_name'],
                    'ACTIVE',
                    0.0,
                    datetime.now().isoformat()
                ))
                
                # Also add to active_trades table
                await db.execute("""
                    INSERT INTO active_trades (
                        trade_id, symbol, direction, channel_name, created_at, status
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    trade_id,
                    signal_data['symbol'],
                    signal_data['direction'],
                    signal_data['channel_name'],
                    datetime.now().isoformat(),
                    'ACTIVE'
                ))
                
                await db.commit()
                
        except Exception as e:
            trade_logger.error(f"Failed to record trade: {e}", exc_info=True)
    
    async def close_position(self, symbol: str, reason: str = "manual") -> bool:
        """Close an active position."""
        try:
            if symbol not in self.active_trades:
                return False
            
            # Cancel all open orders for this symbol
            await self.bybit.cancel_all(CATEGORY, symbol)
            
            # Get current position
            positions = await self.bybit.positions(CATEGORY, symbol)
            position_list = positions.get("result", {}).get("list", [])
            
            if not position_list:
                # Remove from active trades
                del self.active_trades[symbol]
                return True
            
            position = position_list[0]
            size = float(position.get("size", 0))
            
            if size > 0:
                # Place market order to close
                side = "Sell" if position.get("side") == "Buy" else "Buy"
                
                order_body = {
                    "category": CATEGORY,
                    "symbol": symbol,
                    "side": side,
                    "orderType": "Market",
                    "qty": str(size),
                    "reduceOnly": True,
                    "positionIdx": 0
                }
                
                result = await self.bybit.place_order(order_body)
                
                if result.get("retCode") == 0:
                    trade_logger.position_closed(
                        symbol, position.get("side", ""), str(size), 
                        position.get("unrealisedPnl", "0"), reason
                    )
                    
                    # Update database
                    await self._update_trade_status(symbol, "CLOSED")
                    
                    # Remove from active trades
                    del self.active_trades[symbol]
                    return True
            
            return False
            
        except Exception as e:
            trade_logger.error(f"Failed to close position {symbol}: {e}", exc_info=True)
            return False
    
    async def _update_trade_status(self, symbol: str, status: str):
        """Update trade status in database."""
        try:
            async with get_db_connection() as db:
                await db.execute("""
                    UPDATE trades_new SET state = ?, closed_at = ?
                    WHERE symbol = ? AND state = 'ACTIVE'
                """, (status, datetime.now().isoformat(), symbol))
                
                await db.execute("""
                    UPDATE active_trades SET status = ?
                    WHERE symbol = ? AND status = 'ACTIVE'
                """, (status, symbol))
                
                await db.commit()
                
        except Exception as e:
            trade_logger.error(f"Failed to update trade status: {e}")
    
    async def get_active_trades(self) -> Dict[str, Any]:
        """Get all active trades."""
        return self.active_trades.copy()
    
    async def cleanup_expired_trades(self):
        """Clean up expired or failed trades."""
        try:
            expired_symbols = []
            for symbol, trade_info in self.active_trades.items():
                # Check if trade is older than 24 hours
                if (datetime.now() - trade_info['timestamp']).total_seconds() > 86400:
                    expired_symbols.append(symbol)
            
            for symbol in expired_symbols:
                await self.close_position(symbol, "expired")
                
        except Exception as e:
            trade_logger.error(f"Cleanup failed: {e}")


# Global executor instance
_executor_instance = None

async def get_trade_executor() -> TradeExecutor:
    """Get or create trade executor instance."""
    global _executor_instance
    if _executor_instance is None:
        bybit_client = BybitClient()
        _executor_instance = TradeExecutor(bybit_client)
    return _executor_instance