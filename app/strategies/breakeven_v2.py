"""Breakeven strategy implementation with exact client requirements."""

from decimal import Decimal
from typing import Dict, Any
from app.bybit.client import BybitClient
from app.core.logging import system_logger
from app.telegram.output import send_message
from app.telegram.swedish_templates_v2 import SwedishTemplatesV2

class BreakevenStrategyV2:
    """Breakeven strategy: Move SL to BE at TP2 (+0.0015%)."""
    
    def __init__(self, trade_id: str, symbol: str, direction: str, channel_name: str):
        self.trade_id = trade_id
        self.symbol = symbol
        self.direction = direction.upper()
        self.channel_name = channel_name
        from app.bybit.client import get_bybit_client
        self.bybit = get_bybit_client()
        self.activated = False
        self.trigger_pct = Decimal("2.3")  # CLIENT SPEC: +2.3% → SL to breakeven + costs
    
    async def check_and_activate(self, current_price: Decimal, avg_entry: Decimal) -> bool:
        """Check if breakeven should be activated and activate it."""
        if self.activated:
            return True
        
        # Calculate current gain percentage
        if self.direction == "BUY":
            gain_pct = (current_price - avg_entry) / avg_entry * 100
        else:  # SELL
            gain_pct = (avg_entry - current_price) / avg_entry * 100
        
        # Check if we've hit TP2 trigger
        if gain_pct >= self.trigger_pct:
            await self._activate_breakeven(current_price, gain_pct)
            return True
        
        return False
    
    async def _activate_breakeven(self, current_price: Decimal, gain_pct: Decimal):
        """Activate breakeven by moving SL to breakeven + costs."""
        try:
            # Calculate breakeven price + small buffer for costs
            if self.direction == "BUY":
                be_price = current_price * Decimal("0.999")  # 0.1% below current
            else:  # SELL
                be_price = current_price * Decimal("1.001")  # 0.1% above current
            
            # Place new SL order at breakeven
            order_body = {
                "category": "linear",
                "symbol": self.symbol,
                "side": "Sell" if self.direction == "BUY" else "Buy",
                "orderType": "Limit",
                "qty": "0",  # Will be filled by position size
                "price": str(be_price),
                "timeInForce": "GTC",
                "reduceOnly": True,
                "positionIdx": 0,
                "orderLinkId": f"be_{self.trade_id}"
            }
            
            result = await self.bybit.place_order(order_body)
            
            if result.get('retCode') == 0:
                self.activated = True
                system_logger.info(f"Breakeven activated for {self.symbol} at +{gain_pct:.2f}%")
                
                # Send notification
                signal_data = {
                    'symbol': self.symbol,
                    'channel_name': self.channel_name,
                    'gain_pct': f"{gain_pct:.2f}"
                }
                message = SwedishTemplatesV2.breakeven_activated(signal_data)
                await send_message(message)
                return True
                
            else:
                system_logger.error(f"Failed to activate breakeven: {result}")
                return False
                
        except Exception as e:
            system_logger.error(f"Breakeven activation error: {e}", exc_info=True)
            return False
