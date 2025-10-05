"""Re-entry strategy implementation with exact client requirements."""

from decimal import Decimal
from typing import Dict, Any
from app.bybit.client import BybitClient
from app.core.logging import system_logger
from app.telegram.output import send_message
from app.telegram.swedish_templates_v2 import SwedishTemplatesV2

class ReentryStrategyV2:
    """Re-entry strategy: Attempts re-entries after SL hit (up to 3 attempts)."""
    
    def __init__(self, trade_id: str, symbol: str, direction: str, channel_name: str):
        self.trade_id = trade_id
        self.symbol = symbol
        self.direction = direction.upper()
        self.channel_name = channel_name
        from app.bybit.client import get_bybit_client
        self.bybit = get_bybit_client()
        self.attempts = 0
        self.max_attempts = 3
        self.last_entry_price = Decimal("0")
        self.entry_offset = Decimal("0.001")  # 0.1% offset for re-entries
    
    async def attempt_reentry(self, current_price: Decimal) -> bool:
        """Attempt a re-entry if conditions are met."""
        if self.attempts >= self.max_attempts:
            system_logger.info(f"Max re-entry attempts reached for {self.symbol}")
            return False
        
        # Check if price has moved favorably for re-entry
        if self._should_reenter(current_price):
            success = await self._place_reentry_order(current_price)
            if success:
                self.attempts += 1
                self.last_entry_price = current_price
                return True
        
        return False
    
    def _should_reenter(self, current_price: Decimal) -> bool:
        """Check if conditions are favorable for re-entry."""
        # Simple logic: re-enter if price has moved 0.5% from last entry
        price_change = abs(current_price - self.last_entry_price) / self.last_entry_price
        
        return price_change >= Decimal("0.005")  # 0.5% minimum movement
    
    async def _place_reentry_order(self, current_price: Decimal) -> bool:
        """Place re-entry order."""
        try:
            # Calculate re-entry price with small offset
            if self.direction == "BUY":
                entry_price = current_price * (Decimal("1") - self.entry_offset)
            else:  # SELL
                entry_price = current_price * (Decimal("1") + self.entry_offset)
            
            # Get position size (use original size)
            pos = await self.bybit.positions("linear", self.symbol)
            if not pos.get("result", {}).get("list"):
                system_logger.error(f"No position found for {self.symbol}")
                return False
            
            position = pos["result"]["list"][0]
            original_size = Decimal(str(position.get("size", "0")))
            
            if original_size <= 0:
                system_logger.error(f"Invalid position size: {original_size}")
                return False
            
            # Place re-entry order
            order_body = {
                "category": "linear",
                "symbol": self.symbol,
                "side": self.direction,
                "orderType": "Limit",
                "qty": str(original_size),
                "price": str(entry_price),
                "timeInForce": "PostOnly",
                "reduceOnly": False,
                "positionIdx": 0,
                "orderLinkId": f"reentry_{self.trade_id}_{self.attempts + 1}"
            }
            
            result = await self.bybit.place_order(order_body)
            
            if result.get('retCode') == 0:
                system_logger.info(f"Re-entry order placed for {self.symbol} (attempt {self.attempts + 1})")
                
                # Send notification
                signal_data = {
                    'symbol': self.symbol,
                    'channel_name': self.channel_name,
                    'attempt': self.attempts + 1
                }
                message = SwedishTemplatesV2.reentry_attempted(signal_data)
                await send_message(message)
                
                return True
            else:
                system_logger.error(f"Failed to place re-entry order: {result}")
                return False
                
        except Exception as e:
            system_logger.error(f"Re-entry order placement error: {e}", exc_info=True)
            return False
    
    def can_attempt_more(self) -> bool:
        """Check if more re-entry attempts are allowed."""
        return self.attempts < self.max_attempts
    
    def get_attempts_remaining(self) -> int:
        """Get number of re-entry attempts remaining."""
        return max(0, self.max_attempts - self.attempts)
