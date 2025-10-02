"""Hedge strategy implementation."""

from decimal import Decimal
from typing import Dict, Any, Optional
from app.core.decimal_config import to_decimal, quantize_price, quantize_qty
from app.core.strict_config import STRICT_CONFIG
from app.core.logging import trade_logger
from app.bybit.client import BybitClient

class HedgeStrategy:
    """Hedge strategy - open reverse position at -2% adverse move."""
    
    def __init__(self):
        self.bybit_client = BybitClient()
        self.hedge_active = False
        self.hedge_position_size = Decimal("0")
        self.original_sl = Decimal("0")
        self.original_entry = Decimal("0")
    
    async def check_and_apply_hedge(
        self,
        symbol: str,
        direction: str,
        entry_price: Decimal,
        current_price: Decimal,
        position_size: Decimal,
        original_sl: Decimal
    ) -> Dict[str, Any]:
        """
        Check if hedge should be applied and execute.
        
        Args:
            symbol: Trading symbol
            direction: Original trade direction
            entry_price: Original entry price
            current_price: Current market price
            position_size: Original position size
            original_sl: Original stop loss price
        
        Returns:
            Dict with hedge result
        """
        try:
            # Check if hedge should be triggered
            if not self._should_trigger_hedge(entry_price, current_price, direction):
                return {'applied': False, 'reason': 'Hedge trigger not met'}
            
            # Check if hedge is already active
            if self.hedge_active:
                return {'applied': False, 'reason': 'Hedge already active'}
            
            # Apply hedge
            return await self._apply_hedge(
                symbol, direction, position_size, original_sl, entry_price
            )
            
        except Exception as e:
            trade_logger.error(f"Hedge strategy error: {e}", {
                'symbol': symbol,
                'direction': direction,
                'hedge_active': self.hedge_active
            }, exc_info=True)
            return {'applied': False, 'error': str(e)}
    
    def _should_trigger_hedge(
        self, 
        entry_price: Decimal, 
        current_price: Decimal, 
        direction: str
    ) -> bool:
        """Check if hedge should be triggered at -2% adverse move."""
        price_pct = self._calculate_price_percentage(entry_price, current_price, direction)
        return price_pct <= STRICT_CONFIG.hedge_trigger
    
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
    
    async def _apply_hedge(
        self,
        symbol: str,
        direction: str,
        position_size: Decimal,
        original_sl: Decimal,
        original_entry: Decimal
    ) -> Dict[str, Any]:
        """Apply hedge position."""
        try:
            # Calculate hedge position size (100% of original)
            hedge_size = position_size
            
            # Determine hedge direction (opposite of original)
            hedge_direction = "Sell" if direction == "Buy" else "Buy"
            
            # Calculate hedge TP and SL
            hedge_tp = original_sl  # Hedge TP = original SL
            hedge_sl = original_entry  # Hedge SL = original entry
            
            # Place hedge order
            order_body = {
                "category": STRICT_CONFIG.supported_categories[0],
                "symbol": symbol,
                "side": hedge_direction,
                "orderType": "Market",
                "qty": str(hedge_size),
                "timeInForce": "IOC",
                "reduceOnly": False,
                "positionIdx": 0
            }
            
            result = await self.bybit_client.place_order(order_body)
            
            if result.get("retCode") == 0:
                # Set hedge TP and SL
                await self._set_hedge_tp_sl(symbol, hedge_tp, hedge_sl)
                
                # Update hedge state
                self.hedge_active = True
                self.hedge_position_size = hedge_size
                self.original_sl = original_sl
                self.original_entry = original_entry
                
                trade_logger.info("Hedge applied successfully", {
                    'symbol': symbol,
                    'original_direction': direction,
                    'hedge_direction': hedge_direction,
                    'hedge_size': str(hedge_size),
                    'hedge_tp': str(hedge_tp),
                    'hedge_sl': str(hedge_sl)
                })
                
                return {
                    'applied': True,
                    'hedge_direction': hedge_direction,
                    'hedge_size': str(hedge_size),
                    'hedge_tp': str(hedge_tp),
                    'hedge_sl': str(hedge_sl)
                }
            else:
                trade_logger.error("Failed to place hedge order", {
                    'symbol': symbol,
                    'hedge_direction': hedge_direction,
                    'hedge_size': str(hedge_size),
                    'bybit_result': result
                })
                return {'applied': False, 'reason': 'Failed to place hedge order'}
                
        except Exception as e:
            trade_logger.error(f"Error applying hedge: {e}", exc_info=True)
            return {'applied': False, 'error': str(e)}
    
    async def _set_hedge_tp_sl(self, symbol: str, hedge_tp: Decimal, hedge_sl: Decimal):
        """Set hedge TP and SL orders."""
        try:
            # Set hedge TP
            tp_order_body = {
                "category": STRICT_CONFIG.supported_categories[0],
                "symbol": symbol,
                "side": "Sell" if hedge_tp > hedge_sl else "Buy",  # Determine side based on TP/SL relationship
                "orderType": STRICT_CONFIG.exit_order_type,
                "qty": str(self.hedge_position_size),
                "price": str(hedge_tp),
                "timeInForce": "GTC",
                "reduceOnly": STRICT_CONFIG.exit_reduce_only,
                "positionIdx": 0,
                "triggerBy": STRICT_CONFIG.exit_trigger_by
            }
            
            await self.bybit_client.place_order(tp_order_body)
            
            # Set hedge SL
            sl_order_body = {
                "category": STRICT_CONFIG.supported_categories[0],
                "symbol": symbol,
                "side": "Sell" if hedge_sl > hedge_tp else "Buy",  # Determine side based on SL/TP relationship
                "orderType": STRICT_CONFIG.exit_order_type,
                "qty": str(self.hedge_position_size),
                "price": str(hedge_sl),
                "timeInForce": "GTC",
                "reduceOnly": STRICT_CONFIG.exit_reduce_only,
                "positionIdx": 0,
                "triggerBy": STRICT_CONFIG.exit_trigger_by
            }
            
            await self.bybit_client.place_order(sl_order_body)
            
            trade_logger.info("Hedge TP/SL set", {
                'symbol': symbol,
                'hedge_tp': str(hedge_tp),
                'hedge_sl': str(hedge_sl)
            })
            
        except Exception as e:
            trade_logger.error(f"Error setting hedge TP/SL: {e}", exc_info=True)
    
    async def check_hedge_exit(
        self,
        symbol: str,
        current_price: Decimal
    ) -> Dict[str, Any]:
        """Check if hedge should be exited."""
        try:
            if not self.hedge_active:
                return {'should_exit': False, 'reason': 'No active hedge'}
            
            # Check if hedge TP or SL was hit
            # This would typically be checked through position monitoring
            # For now, return a placeholder
            
            return {'should_exit': False, 'reason': 'Hedge monitoring not implemented'}
            
        except Exception as e:
            trade_logger.error(f"Error checking hedge exit: {e}", exc_info=True)
            return {'should_exit': False, 'error': str(e)}
    
    def is_hedge_active(self) -> bool:
        """Check if hedge is active."""
        return self.hedge_active
    
    def get_hedge_stats(self) -> Dict[str, Any]:
        """Get hedge statistics."""
        return {
            'active': self.hedge_active,
            'position_size': str(self.hedge_position_size),
            'original_sl': str(self.original_sl),
            'original_entry': str(self.original_entry)
        }
    
    def reset(self):
        """Reset hedge state."""
        self.hedge_active = False
        self.hedge_position_size = Decimal("0")
        self.original_sl = Decimal("0")
        self.original_entry = Decimal("0")

# Global hedge strategy instance
_hedge_strategy = None

def get_hedge_strategy() -> HedgeStrategy:
    """Get global hedge strategy instance."""
    global _hedge_strategy
    if _hedge_strategy is None:
        _hedge_strategy = HedgeStrategy()
    return _hedge_strategy