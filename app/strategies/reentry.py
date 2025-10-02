"""Re-entry strategy implementation."""

from decimal import Decimal
from typing import Dict, Any, Optional
from app.core.decimal_config import to_decimal, quantize_price, quantize_qty
from app.core.strict_config import STRICT_CONFIG
from app.core.logging import trade_logger
from app.bybit.client import BybitClient

class ReentryStrategy:
    """Re-entry strategy - attempt dual-limit re-entry up to 3 times after SL."""
    
    def __init__(self):
        self.bybit_client = BybitClient()
        self.reentry_count = 0
        self.max_reentries = STRICT_CONFIG.max_reentries
        self.last_sl_price = Decimal("0")
        self.original_entry = Decimal("0")
        self.original_direction = ""
    
    async def check_and_attempt_reentry(
        self,
        symbol: str,
        direction: str,
        original_entry: Decimal,
        sl_price: Decimal,
        position_size: Decimal
    ) -> Dict[str, Any]:
        """
        Check if re-entry should be attempted and execute.
        
        Args:
            symbol: Trading symbol
            direction: Original trade direction
            original_entry: Original entry price
            sl_price: Stop loss price that was hit
            position_size: Original position size
        
        Returns:
            Dict with re-entry result
        """
        try:
            # Check if we can attempt re-entry
            if not self._can_attempt_reentry():
                return {'applied': False, 'reason': 'Max re-entries reached or not applicable'}
            
            # Store re-entry context
            self.last_sl_price = sl_price
            self.original_entry = original_entry
            self.original_direction = direction
            
            # Attempt re-entry
            return await self._attempt_reentry(symbol, direction, position_size)
            
        except Exception as e:
            trade_logger.error(f"Re-entry strategy error: {e}", {
                'symbol': symbol,
                'direction': direction,
                'reentry_count': self.reentry_count
            }, exc_info=True)
            return {'applied': False, 'error': str(e)}
    
    def _can_attempt_reentry(self) -> bool:
        """Check if re-entry can be attempted."""
        return self.reentry_count < self.max_reentries
    
    async def _attempt_reentry(
        self,
        symbol: str,
        direction: str,
        position_size: Decimal
    ) -> Dict[str, Any]:
        """Attempt dual-limit re-entry."""
        try:
            # Calculate re-entry prices
            reentry_prices = self._calculate_reentry_prices()
            
            # Place dual-limit orders
            order_results = []
            for i, price in enumerate(reentry_prices):
                order_body = {
                    "category": STRICT_CONFIG.supported_categories[0],
                    "symbol": symbol,
                    "side": direction,
                    "orderType": "Limit",
                    "qty": str(position_size / 2),  # Split quantity 50/50
                    "price": str(price),
                    "timeInForce": STRICT_CONFIG.entry_time_in_force,
                    "reduceOnly": False,
                    "positionIdx": 0,
                    "orderLinkId": f"reentry_{symbol}_{self.reentry_count}_{i}"
                }
                
                result = await self.bybit_client.place_order(order_body)
                order_results.append(result)
            
            # Check if any orders were placed successfully
            successful_orders = [r for r in order_results if r.get("retCode") == 0]
            
            if successful_orders:
                self.reentry_count += 1
                
                trade_logger.info("Re-entry attempted", {
                    'symbol': symbol,
                    'direction': direction,
                    'reentry_count': self.reentry_count,
                    'reentry_prices': [str(p) for p in reentry_prices],
                    'successful_orders': len(successful_orders)
                })
                
                return {
                    'applied': True,
                    'reentry_count': self.reentry_count,
                    'reentry_prices': [str(p) for p in reentry_prices],
                    'successful_orders': len(successful_orders),
                    'order_results': order_results
                }
            else:
                trade_logger.error("All re-entry orders failed", {
                    'symbol': symbol,
                    'direction': direction,
                    'reentry_count': self.reentry_count,
                    'order_results': order_results
                })
                
                return {
                    'applied': False,
                    'reason': 'All re-entry orders failed',
                    'order_results': order_results
                }
                
        except Exception as e:
            trade_logger.error(f"Error attempting re-entry: {e}", exc_info=True)
            return {'applied': False, 'error': str(e)}
    
    def _calculate_reentry_prices(self) -> list[Decimal]:
        """Calculate dual re-entry prices."""
        # Use original entry price as base
        base_price = self.original_entry
        
        # Calculate price spread (0.1% in trade direction)
        spread = base_price * Decimal("0.001")
        
        if self.original_direction == "LONG":
            # For LONG, use slightly lower prices
            price1 = base_price - spread
            price2 = base_price - (spread * 2)
        else:  # SHORT
            # For SHORT, use slightly higher prices
            price1 = base_price + spread
            price2 = base_price + (spread * 2)
        
        return [price1, price2]
    
    async def monitor_reentry_orders(
        self,
        symbol: str
    ) -> Dict[str, Any]:
        """Monitor re-entry orders for fills."""
        try:
            # Get open orders for this symbol
            result = await self.bybit_client.query_open(
                STRICT_CONFIG.supported_categories[0],
                symbol
            )
            
            if result.get("retCode") != 0:
                return {'status': 'error', 'reason': 'Failed to query orders'}
            
            orders = result.get("result", {}).get("list", [])
            reentry_orders = [
                order for order in orders 
                if order.get("orderLinkId", "").startswith(f"reentry_{symbol}")
            ]
            
            if not reentry_orders:
                # No re-entry orders, check if we should reset
                if self.reentry_count > 0:
                    self.reset()
                    return {'status': 'completed', 'reason': 'No re-entry orders found'}
                else:
                    return {'status': 'no_orders', 'reason': 'No re-entry orders to monitor'}
            
            # Check for filled orders
            filled_orders = [
                order for order in reentry_orders 
                if order.get("orderStatus") == "Filled"
            ]
            
            if filled_orders:
                trade_logger.info("Re-entry order filled", {
                    'symbol': symbol,
                    'filled_orders': len(filled_orders),
                    'reentry_count': self.reentry_count
                })
                
                return {
                    'status': 'filled',
                    'filled_orders': len(filled_orders),
                    'reentry_count': self.reentry_count
                }
            else:
                return {
                    'status': 'pending',
                    'pending_orders': len(reentry_orders),
                    'reentry_count': self.reentry_count
                }
                
        except Exception as e:
            trade_logger.error(f"Error monitoring re-entry orders: {e}", exc_info=True)
            return {'status': 'error', 'error': str(e)}
    
    def get_reentry_stats(self) -> Dict[str, Any]:
        """Get re-entry statistics."""
        return {
            'reentry_count': self.reentry_count,
            'max_reentries': self.max_reentries,
            'can_attempt': self._can_attempt_reentry(),
            'last_sl_price': str(self.last_sl_price),
            'original_entry': str(self.original_entry),
            'original_direction': self.original_direction
        }
    
    def reset(self):
        """Reset re-entry state."""
        self.reentry_count = 0
        self.last_sl_price = Decimal("0")
        self.original_entry = Decimal("0")
        self.original_direction = ""

# Global re-entry strategy instance
_reentry_strategy = None

def get_reentry_strategy() -> ReentryStrategy:
    """Get global re-entry strategy instance."""
    global _reentry_strategy
    if _reentry_strategy is None:
        _reentry_strategy = ReentryStrategy()
    return _reentry_strategy