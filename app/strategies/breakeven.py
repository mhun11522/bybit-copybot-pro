"""Breakeven strategy implementation."""

from decimal import Decimal
from typing import Dict, Any
from app.core.decimal_config import to_decimal, quantize_price
from app.core.strict_config import STRICT_CONFIG
from app.core.logging import trade_logger
from app.bybit.client import BybitClient

class BreakevenStrategy:
    """Breakeven strategy - move SL to BE + 0.0015% after TP2."""
    
    def __init__(self):
        self.bybit_client = BybitClient()
    
    async def check_and_apply_breakeven(
        self, 
        symbol: str, 
        direction: str, 
        entry_price: Decimal, 
        current_pnl: Decimal,
        pyramid_level: int
    ) -> bool:
        """
        Check if breakeven should be applied and execute.
        
        Args:
            symbol: Trading symbol
            direction: Trade direction (LONG/SHORT)
            entry_price: Original entry price
            current_pnl: Current unrealized PnL
            pyramid_level: Current pyramid level
        
        Returns:
            True if breakeven was applied, False otherwise
        """
        try:
            # Only apply after TP2 (pyramid level >= 2)
            if pyramid_level < 2:
                return False
            
            # Calculate breakeven price
            be_price = self._calculate_breakeven_price(entry_price, direction)
            
            # Apply breakeven offset
            be_price_with_offset = self._apply_breakeven_offset(be_price, direction)
            
            # Set new stop loss
            success = await self._set_breakeven_sl(symbol, be_price_with_offset)
            
            if success:
                trade_logger.info("Breakeven applied", {
                    'symbol': symbol,
                    'direction': direction,
                    'entry_price': str(entry_price),
                    'be_price': str(be_price),
                    'be_price_with_offset': str(be_price_with_offset),
                    'pyramid_level': pyramid_level
                })
            
            return success
            
        except Exception as e:
            trade_logger.error(f"Breakeven strategy error: {e}", {
                'symbol': symbol,
                'direction': direction
            }, exc_info=True)
            return False
    
    def _calculate_breakeven_price(self, entry_price: Decimal, direction: str) -> Decimal:
        """Calculate breakeven price (entry price)."""
        return entry_price
    
    def _apply_breakeven_offset(self, be_price: Decimal, direction: str) -> Decimal:
        """Apply breakeven offset of 0.0015%."""
        offset = be_price * STRICT_CONFIG.breakeven_offset
        
        if direction == "LONG":
            # For LONG, move SL slightly below BE
            return be_price - offset
        else:  # SHORT
            # For SHORT, move SL slightly above BE
            return be_price + offset
    
    async def _set_breakeven_sl(self, symbol: str, sl_price: Decimal) -> bool:
        """Set breakeven stop loss on Bybit."""
        try:
            # Use trading stop endpoint to update SL
            result = await self.bybit_client.set_trading_stop(
                STRICT_CONFIG.supported_categories[0],
                symbol,
                str(sl_price),
                "Market",  # SL order type
                "MarkPrice"  # Trigger by mark price
            )
            
            if result.get("retCode") == 0:
                trade_logger.info("Breakeven SL set successfully", {
                    'symbol': symbol,
                    'sl_price': str(sl_price)
                })
                return True
            else:
                trade_logger.error("Failed to set breakeven SL", {
                    'symbol': symbol,
                    'sl_price': str(sl_price),
                    'bybit_result': result
                })
                return False
                
        except Exception as e:
            trade_logger.error(f"Error setting breakeven SL: {e}", {
                'symbol': symbol,
                'sl_price': str(sl_price)
            }, exc_info=True)
            return False
    
    async def is_breakeven_applicable(
        self, 
        symbol: str, 
        direction: str, 
        entry_price: Decimal,
        current_price: Decimal,
        pyramid_level: int
    ) -> bool:
        """
        Check if breakeven is applicable.
        
        Args:
            symbol: Trading symbol
            direction: Trade direction
            entry_price: Original entry price
            current_price: Current market price
            pyramid_level: Current pyramid level
        
        Returns:
            True if breakeven should be applied
        """
        # Must be at least TP2 level
        if pyramid_level < 2:
            return False
        
        # Check if price has moved favorably
        if direction == "LONG":
            return current_price > entry_price
        else:  # SHORT
            return current_price < entry_price

# Global breakeven strategy instance
_breakeven_strategy = None

def get_breakeven_strategy() -> BreakevenStrategy:
    """Get global breakeven strategy instance."""
    global _breakeven_strategy
    if _breakeven_strategy is None:
        _breakeven_strategy = BreakevenStrategy()
    return _breakeven_strategy