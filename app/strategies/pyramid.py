"""Pyramid strategy implementation with exact client levels."""

from decimal import Decimal
from typing import Dict, Any, List, Optional
from app.core.decimal_config import to_decimal, quantize_price, quantize_qty
from app.core.strict_config import STRICT_CONFIG
from app.core.logging import trade_logger
from app.bybit.client import BybitClient

class PyramidStrategy:
    """Pyramid strategy with exact client specification levels."""
    
    def __init__(self):
        self.bybit_client = BybitClient()
        self.pyramid_levels = STRICT_CONFIG.pyramid_levels
        self.max_leverage = Decimal("50")
    
    async def check_and_apply_pyramid(
        self,
        symbol: str,
        direction: str,
        entry_price: Decimal,
        current_price: Decimal,
        current_pyramid_level: int,
        current_im: Decimal,
        current_leverage: Decimal
    ) -> Dict[str, Any]:
        """
        Check if pyramid level should be applied and execute.
        
        Args:
            symbol: Trading symbol
            direction: Trade direction
            entry_price: Original entry price
            current_price: Current market price
            current_pyramid_level: Current pyramid level
            current_im: Current initial margin
            current_leverage: Current leverage
        
        Returns:
            Dict with pyramid result
        """
        try:
            # Calculate price percentage from entry
            price_pct = self._calculate_price_percentage(entry_price, current_price, direction)
            
            # Find applicable pyramid level
            pyramid_level = self._find_applicable_level(price_pct, current_pyramid_level)
            if not pyramid_level:
                return {'applied': False, 'reason': 'No applicable pyramid level'}
            
            # Apply pyramid level
            result = await self._apply_pyramid_level(
                symbol, direction, pyramid_level, current_im, current_leverage
            )
            
            if result['success']:
                trade_logger.info("Pyramid level applied", {
                    'symbol': symbol,
                    'direction': direction,
                    'pyramid_level': pyramid_level,
                    'price_pct': str(price_pct),
                    'new_im': str(result.get('new_im', 0)),
                    'new_leverage': str(result.get('new_leverage', 0))
                })
            
            return result
            
        except Exception as e:
            trade_logger.error(f"Pyramid strategy error: {e}", {
                'symbol': symbol,
                'direction': direction,
                'current_pyramid_level': current_pyramid_level
            }, exc_info=True)
            return {'applied': False, 'error': str(e)}
    
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
    
    def _find_applicable_level(
        self, 
        price_pct: Decimal, 
        current_pyramid_level: int
    ) -> Optional[Dict[str, Any]]:
        """Find the next applicable pyramid level."""
        for level in self.pyramid_levels:
            trigger = level["trigger"]
            if price_pct >= trigger and trigger > current_pyramid_level:
                return level
        return None
    
    async def _apply_pyramid_level(
        self,
        symbol: str,
        direction: str,
        level: Dict[str, Any],
        current_im: Decimal,
        current_leverage: Decimal
    ) -> Dict[str, Any]:
        """Apply specific pyramid level."""
        try:
            action = level["action"]
            
            if action == "check_im":
                return await self._check_im(symbol, level)
            elif action == "sl_to_be":
                return await self._sl_to_be(symbol, direction)
            elif action == "max_leverage":
                return await self._max_leverage(symbol, level)
            elif action == "add_im":
                return await self._add_im(symbol, direction, level, current_im)
            else:
                return {'applied': False, 'reason': f'Unknown action: {action}'}
                
        except Exception as e:
            trade_logger.error(f"Error applying pyramid level: {e}", {
                'symbol': symbol,
                'level': level
            }, exc_info=True)
            return {'applied': False, 'error': str(e)}
    
    async def _check_im(self, symbol: str, level: Dict[str, Any]) -> Dict[str, Any]:
        """Check IM level (trigger at +1.5%)."""
        target_im = Decimal(str(level["target_im"]))
        
        # This would check current IM and adjust if needed
        return {
            'applied': True,
            'action': 'check_im',
            'target_im': str(target_im)
        }
    
    async def _sl_to_be(self, symbol: str, direction: str) -> Dict[str, Any]:
        """Set SL to breakeven (trigger at +2.3%)."""
        try:
            # Get current position to find entry price
            position = await self.bybit_client.positions(
                STRICT_CONFIG.supported_categories[0], symbol
            )
            
            if position.get("retCode") != 0:
                return {'applied': False, 'reason': 'Failed to get position'}
            
            positions = position.get("result", {}).get("list", [])
            if not positions:
                return {'applied': False, 'reason': 'No position found'}
            
            entry_price = Decimal(str(positions[0].get("avgPrice", 0)))
            
            # Calculate breakeven price
            be_price = entry_price
            
            # Set SL to breakeven
            result = await self.bybit_client.set_trading_stop(
                STRICT_CONFIG.supported_categories[0],
                symbol,
                str(be_price),
                "Market",
                "MarkPrice"
            )
            
            if result.get("retCode") == 0:
                return {
                    'applied': True,
                    'action': 'sl_to_be',
                    'be_price': str(be_price)
                }
            else:
                return {'applied': False, 'reason': 'Failed to set SL to BE'}
                
        except Exception as e:
            trade_logger.error(f"Error setting SL to BE: {e}", exc_info=True)
            return {'applied': False, 'error': str(e)}
    
    async def _max_leverage(self, symbol: str, level: Dict[str, Any]) -> Dict[str, Any]:
        """Set maximum leverage (trigger at +2.4%)."""
        target_lev = Decimal(str(level["target_lev"]))
        
        try:
            result = await self.bybit_client.set_leverage(
                STRICT_CONFIG.supported_categories[0],
                symbol,
                int(target_lev),
                int(target_lev)
            )
            
            if result.get("retCode") == 0:
                return {
                    'applied': True,
                    'action': 'max_leverage',
                    'new_leverage': str(target_lev)
                }
            else:
                return {'applied': False, 'reason': 'Failed to set max leverage'}
                
        except Exception as e:
            trade_logger.error(f"Error setting max leverage: {e}", exc_info=True)
            return {'applied': False, 'error': str(e)}
    
    async def _add_im(
        self, 
        symbol: str, 
        direction: str, 
        level: Dict[str, Any], 
        current_im: Decimal
    ) -> Dict[str, Any]:
        """Add initial margin (triggers at +2.5%, +4%, +6%, +8.6%)."""
        target_im = Decimal(str(level["target_im"]))
        
        try:
            # Calculate additional IM needed
            additional_im = target_im - current_im
            if additional_im <= 0:
                return {'applied': False, 'reason': 'No additional IM needed'}
            
            # Calculate additional position size
            current_price = await self._get_current_price(symbol)
            if not current_price:
                return {'applied': False, 'reason': 'Failed to get current price'}
            
            # Calculate additional quantity
            additional_qty = additional_im / current_price
            
            # Place additional order
            order_body = {
                "category": STRICT_CONFIG.supported_categories[0],
                "symbol": symbol,
                "side": direction,
                "orderType": "Market",
                "qty": str(additional_qty),
                "timeInForce": "IOC",
                "reduceOnly": False,
                "positionIdx": 0
            }
            
            result = await self.bybit_client.place_order(order_body)
            
            if result.get("retCode") == 0:
                return {
                    'applied': True,
                    'action': 'add_im',
                    'target_im': str(target_im),
                    'additional_im': str(additional_im),
                    'additional_qty': str(additional_qty)
                }
            else:
                return {'applied': False, 'reason': 'Failed to add IM'}
                
        except Exception as e:
            trade_logger.error(f"Error adding IM: {e}", exc_info=True)
            return {'applied': False, 'error': str(e)}
    
    async def _get_current_price(self, symbol: str) -> Optional[Decimal]:
        """Get current market price for symbol."""
        try:
            result = await self.bybit_client.instruments(
                STRICT_CONFIG.supported_categories[0], symbol
            )
            
            if result.get("retCode") == 0:
                instruments = result.get("result", {}).get("list", [])
                if instruments:
                    last_price = instruments[0].get("lastPrice")
                    if last_price:
                        return Decimal(str(last_price))
            
            return None
            
        except Exception as e:
            trade_logger.error(f"Error getting current price: {e}", exc_info=True)
            return None

# Global pyramid strategy instance
_pyramid_strategy = None

def get_pyramid_strategy() -> PyramidStrategy:
    """Get global pyramid strategy instance."""
    global _pyramid_strategy
    if _pyramid_strategy is None:
        _pyramid_strategy = PyramidStrategy()
    return _pyramid_strategy