"""Trailing stop strategy implementation."""

from decimal import Decimal
from typing import Dict, Any, Optional
from app.core.decimal_config import to_decimal, quantize_price
from app.core.strict_config import STRICT_CONFIG
from app.core.logging import trade_logger
from app.bybit.client import BybitClient

class TrailingStopStrategy:
    """Trailing stop strategy - activate at +6.1%, maintain 2.5% behind high/low."""
    
    def __init__(self):
        self.bybit_client = BybitClient()
        self.trailing_active = False
        self.highest_price = Decimal("0")
        self.lowest_price = Decimal("0")
        self.current_sl = Decimal("0")
    
    async def check_and_update_trailing(
        self,
        symbol: str,
        direction: str,
        entry_price: Decimal,
        current_price: Decimal,
        current_pnl: Decimal
    ) -> Dict[str, Any]:
        """
        Check if trailing stop should be activated or updated.
        
        Args:
            symbol: Trading symbol
            direction: Trade direction
            entry_price: Original entry price
            current_price: Current market price
            current_pnl: Current unrealized PnL
        
        Returns:
            Dict with trailing stop result
        """
        try:
            # Check if trailing should be activated
            if not self.trailing_active:
                should_activate = self._should_activate_trailing(
                    entry_price, current_price, direction
                )
                
                if should_activate:
                    return await self._activate_trailing(symbol, direction, current_price)
                else:
                    return {'applied': False, 'reason': 'Trailing not yet triggered'}
            
            # Update trailing stop if already active
            return await self._update_trailing(symbol, direction, current_price)
            
        except Exception as e:
            trade_logger.error(f"Trailing stop strategy error: {e}", {
                'symbol': symbol,
                'direction': direction,
                'trailing_active': self.trailing_active
            }, exc_info=True)
            return {'applied': False, 'error': str(e)}
    
    def _should_activate_trailing(
        self, 
        entry_price: Decimal, 
        current_price: Decimal, 
        direction: str
    ) -> bool:
        """Check if trailing stop should be activated at +6.1%."""
        price_pct = self._calculate_price_percentage(entry_price, current_price, direction)
        return price_pct >= STRICT_CONFIG.trailing_trigger
    
    def _calculate_price_percentage(
        self, 
        entry_price: Decimal, 
        current_price: Decimal, 
        direction: str
    ) -> Decimal:
        """Calculate price percentage from entry."""
        if direction == "LONG":
            return ((current_price - entry_price) / entry_price) * Decimal("100")
        else:  # SHORT
            return ((entry_price - current_price) / entry_price) * Decimal("100")
    
    async def _activate_trailing(
        self, 
        symbol: str, 
        direction: str, 
        current_price: Decimal
    ) -> Dict[str, Any]:
        """Activate trailing stop."""
        try:
            self.trailing_active = True
            self.highest_price = current_price
            self.lowest_price = current_price
            
            # Calculate initial trailing SL
            trailing_sl = self._calculate_trailing_sl(current_price, direction)
            
            # Set initial trailing SL
            success = await self._set_trailing_sl(symbol, trailing_sl)
            
            if success:
                self.current_sl = trailing_sl
                trade_logger.info("Trailing stop activated", {
                    'symbol': symbol,
                    'direction': direction,
                    'trigger_price': str(current_price),
                    'initial_sl': str(trailing_sl)
                })
                
                return {
                    'applied': True,
                    'action': 'activated',
                    'trigger_price': str(current_price),
                    'initial_sl': str(trailing_sl)
                }
            else:
                self.trailing_active = False
                return {'applied': False, 'reason': 'Failed to set initial trailing SL'}
                
        except Exception as e:
            trade_logger.error(f"Error activating trailing stop: {e}", exc_info=True)
            self.trailing_active = False
            return {'applied': False, 'error': str(e)}
    
    async def _update_trailing(
        self, 
        symbol: str, 
        direction: str, 
        current_price: Decimal
    ) -> Dict[str, Any]:
        """Update trailing stop based on price movement."""
        try:
            # Update highest/lowest prices
            if direction == "LONG":
                if current_price > self.highest_price:
                    self.highest_price = current_price
                    # Calculate new trailing SL
                    new_sl = self._calculate_trailing_sl(current_price, direction)
                    
                    # Only update if new SL is better (higher for LONG)
                    if new_sl > self.current_sl:
                        success = await self._set_trailing_sl(symbol, new_sl)
                        if success:
                            self.current_sl = new_sl
                            return {
                                'applied': True,
                                'action': 'updated',
                                'new_sl': str(new_sl),
                                'high_price': str(self.highest_price)
                            }
            else:  # SHORT
                if current_price < self.lowest_price:
                    self.lowest_price = current_price
                    # Calculate new trailing SL
                    new_sl = self._calculate_trailing_sl(current_price, direction)
                    
                    # Only update if new SL is better (lower for SHORT)
                    if new_sl < self.current_sl:
                        success = await self._set_trailing_sl(symbol, new_sl)
                        if success:
                            self.current_sl = new_sl
                            return {
                                'applied': True,
                                'action': 'updated',
                                'new_sl': str(new_sl),
                                'low_price': str(self.lowest_price)
                            }
            
            return {'applied': False, 'reason': 'No trailing update needed'}
            
        except Exception as e:
            trade_logger.error(f"Error updating trailing stop: {e}", exc_info=True)
            return {'applied': False, 'error': str(e)}
    
    def _calculate_trailing_sl(self, price: Decimal, direction: str) -> Decimal:
        """Calculate trailing stop loss price."""
        trailing_distance = price * (STRICT_CONFIG.trailing_distance / Decimal("100"))
        
        if direction == "LONG":
            # For LONG, SL is below current price
            return price - trailing_distance
        else:  # SHORT
            # For SHORT, SL is above current price
            return price + trailing_distance
    
    async def _set_trailing_sl(self, symbol: str, sl_price: Decimal) -> bool:
        """Set trailing stop loss on Bybit."""
        try:
            result = await self.bybit_client.set_trading_stop(
                STRICT_CONFIG.supported_categories[0],
                symbol,
                str(sl_price),
                "Market",
                "MarkPrice"
            )
            
            if result.get("retCode") == 0:
                return True
            else:
                trade_logger.error("Failed to set trailing SL", {
                    'symbol': symbol,
                    'sl_price': str(sl_price),
                    'bybit_result': result
                })
                return False
                
        except Exception as e:
            trade_logger.error(f"Error setting trailing SL: {e}", {
                'symbol': symbol,
                'sl_price': str(sl_price)
            }, exc_info=True)
            return False
    
    def is_trailing_active(self) -> bool:
        """Check if trailing stop is active."""
        return self.trailing_active
    
    def get_trailing_stats(self) -> Dict[str, Any]:
        """Get trailing stop statistics."""
        return {
            'active': self.trailing_active,
            'highest_price': str(self.highest_price),
            'lowest_price': str(self.lowest_price),
            'current_sl': str(self.current_sl),
            'trailing_distance': str(STRICT_CONFIG.trailing_distance)
        }
    
    def reset(self):
        """Reset trailing stop state."""
        self.trailing_active = False
        self.highest_price = Decimal("0")
        self.lowest_price = Decimal("0")
        self.current_sl = Decimal("0")

# Global trailing stop strategy instance
_trailing_strategy = None

def get_trailing_strategy() -> TrailingStopStrategy:
    """Get global trailing stop strategy instance."""
    global _trailing_strategy
    if _trailing_strategy is None:
        _trailing_strategy = TrailingStopStrategy()
    return _trailing_strategy