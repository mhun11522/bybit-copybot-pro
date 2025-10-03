"""Hedge strategy implementation with exact client requirements."""

from decimal import Decimal
from typing import Dict, Any
from app.bybit.client import BybitClient
from app.core.logging import system_logger
from app.telegram.output import send_message
from app.telegram.swedish_templates_v2 import SwedishTemplatesV2

class HedgeStrategyV2:
    """Hedge strategy: Opens reverse position at -2% adverse move."""
    
    def __init__(self, trade_id: str, symbol: str, direction: str, channel_name: str):
        self.trade_id = trade_id
        self.symbol = symbol
        self.direction = direction.upper()
        self.channel_name = channel_name
        self.bybit = BybitClient()
        self.activated = False
        self.trigger_pct = Decimal("2.0")  # -2% trigger
        self.hedge_size: Optional[Decimal] = None
    
    async def check_and_activate(self, current_price: Decimal, original_entry: Decimal) -> bool:
        """Check if hedge should be activated."""
        if self.activated:
            return True
        
        # Calculate current loss percentage
        if self.direction == "BUY":
            loss_pct = (original_entry - current_price) / original_entry * 100
        else:  # SELL
            loss_pct = (current_price - original_entry) / original_entry * 100
        
        # Check if we've hit -2% trigger
        if loss_pct >= self.trigger_pct:
            await self._activate_hedge(current_price, loss_pct)
            return True
        
        return False
    
    async def _activate_hedge(self, current_price: Decimal, loss_pct: Decimal):
        """Activate hedge by opening reverse position."""
        try:
            # Get current position size
            pos = await self.bybit.positions("linear", self.symbol)
            if not pos.get("result", {}).get("list"):
                system_logger.error(f"No position found for {self.symbol}")
                return
            
            position = pos["result"]["list"][0]
            current_size = Decimal(str(position.get("size", "0")))
            
            if current_size <= 0:
                system_logger.error(f"Invalid position size: {current_size}")
                return
            
            # Calculate hedge size (100% of current position)
            self.hedge_size = current_size
            
            # Determine hedge direction (opposite of current position)
            hedge_direction = "Sell" if self.direction == "BUY" else "Buy"
            
            # Place hedge order
            order_body = {
                "category": "linear",
                "symbol": self.symbol,
                "side": hedge_direction,
                "orderType": "Market",
                "qty": str(self.hedge_size),
                "timeInForce": "IOC",
                "reduceOnly": False,
                "positionIdx": 0,
                "orderLinkId": f"hedge_{self.trade_id}"
            }
            
            result = await self.bybit.place_order(order_body)
            
            if result.get('retCode') == 0:
                self.activated = True
                system_logger.info(f"Hedge activated for {self.symbol} at -{loss_pct:.2f}%")
                
                # Send notification
                signal_data = {
                    'symbol': self.symbol,
                    'channel_name': self.channel_name,
                    'loss_pct': f"{loss_pct:.2f}"
                }
                message = SwedishTemplatesV2.hedge_activated(signal_data)
                await send_message(message)
                
            else:
                system_logger.error(f"Failed to activate hedge: {result}")
                
        except Exception as e:
            system_logger.error(f"Hedge activation error: {e}", exc_info=True)
    
    async def close_hedge(self):
        """Close the hedge position."""
        try:
            if not self.hedge_size:
                return
            
            # Get current position
            pos = await self.bybit.positions("linear", self.symbol)
            if not pos.get("result", {}).get("list"):
                return
            
            position = pos["result"]["list"][0]
            current_size = Decimal(str(position.get("size", "0")))
            
            # Determine close direction
            close_direction = "Sell" if self.direction == "BUY" else "Buy"
            
            # Close hedge position
            order_body = {
                "category": "linear",
                "symbol": self.symbol,
                "side": close_direction,
                "orderType": "Market",
                "qty": str(self.hedge_size),
                "timeInForce": "IOC",
                "reduceOnly": True,
                "positionIdx": 0,
                "orderLinkId": f"close_hedge_{self.trade_id}"
            }
            
            result = await self.bybit.place_order(order_body)
            
            if result.get('retCode') == 0:
                system_logger.info(f"Hedge closed for {self.symbol}")
                self.hedge_size = None
            else:
                system_logger.error(f"Failed to close hedge: {result}")
                
        except Exception as e:
            system_logger.error(f"Hedge close error: {e}", exc_info=True)
