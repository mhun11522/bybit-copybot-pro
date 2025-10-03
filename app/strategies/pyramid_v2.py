"""Pyramid strategy implementation with exact client requirements."""

from decimal import Decimal
from typing import Dict, Any
from app.bybit.client import BybitClient
from app.core.logging import system_logger
from app.telegram.output import send_message
from app.telegram.swedish_templates_v2 import SwedishTemplatesV2

class PyramidStrategyV2:
    """Pyramid strategy with exact client requirements."""
    
    def __init__(self, trade_id: str, symbol: str, direction: str, original_entry: Decimal, channel_name: str):
        self.trade_id = trade_id
        self.symbol = symbol
        self.direction = direction.upper()
        self.original_entry = original_entry
        self.channel_name = channel_name
        self.bybit = BybitClient()
        self.levels = {
            Decimal("1.5"): {"im": Decimal("20"), "leverage": Decimal("10")},  # +1.5%: IM 20 USDT
            Decimal("2.3"): {"im": Decimal("20"), "leverage": Decimal("10")},  # +2.3%: SL to BE
            Decimal("2.4"): {"im": Decimal("20"), "leverage": Decimal("50")},  # +2.4%: Max leverage
            Decimal("2.5"): {"im": Decimal("40"), "leverage": Decimal("50")},  # +2.5%: IM 40 USDT
            Decimal("4.0"): {"im": Decimal("60"), "leverage": Decimal("50")},  # +4.0%: IM 60 USDT
            Decimal("6.0"): {"im": Decimal("80"), "leverage": Decimal("50")},  # +6.0%: IM 80 USDT
            Decimal("8.6"): {"im": Decimal("100"), "leverage": Decimal("50")}, # +8.6%: IM 100 USDT
        }
        self.activated_levels = set()
        self.max_adds = 7
    
    async def check_and_activate(self, current_price: Decimal) -> bool:
        """Check if pyramid levels should be activated."""
        # Calculate gain from original entry
        if self.direction == "BUY":
            gain_pct = (current_price - self.original_entry) / self.original_entry * 100
        else:  # SELL
            gain_pct = (self.original_entry - current_price) / self.original_entry * 100
        
        # Check each level
        for level_pct, config in self.levels.items():
            if gain_pct >= level_pct and level_pct not in self.activated_levels:
                await self._activate_level(level_pct, config, gain_pct)
                self.activated_levels.add(level_pct)
                return True
        
        return False
    
    async def _activate_level(self, level_pct: Decimal, config: Dict[str, Decimal], gain_pct: Decimal):
        """Activate a pyramid level."""
        try:
            level_num = len(self.activated_levels) + 1
            
            # Special handling for +2.3% (move SL to breakeven)
            if level_pct == Decimal("2.3"):
                await self._move_sl_to_breakeven()
            
            # Update leverage if needed
            if config["leverage"] > Decimal("10"):
                await self._update_leverage(config["leverage"])
            
            # Update position size if needed
            if config["im"] > Decimal("20"):
                await self._update_position_size(config["im"])
            
            system_logger.info(f"Pyramid level {level_num} activated for {self.symbol} at +{gain_pct:.2f}%")
            
            # Send notification
            signal_data = {
                'symbol': self.symbol,
                'channel_name': self.channel_name,
                'level': level_num,
                'gain_pct': f"{gain_pct:.2f}",
                'new_im': str(config["im"]),
                'new_leverage': f"x{config['leverage']}"
            }
            message = SwedishTemplatesV2.pyramid_activated(signal_data)
            await send_message(message)
            
        except Exception as e:
            system_logger.error(f"Pyramid level activation error: {e}", exc_info=True)
    
    async def _move_sl_to_breakeven(self):
        """Move SL to breakeven + costs."""
        try:
            # Get current position
            pos = await self.bybit.positions("linear", self.symbol)
            if pos.get("result", {}).get("list"):
                position = pos["result"]["list"][0]
                avg_price = Decimal(str(position.get("avgPrice", "0")))
                
                # Calculate breakeven + small buffer
                if self.direction == "BUY":
                    be_price = avg_price * Decimal("0.999")  # 0.1% below entry
                else:  # SELL
                    be_price = avg_price * Decimal("1.001")  # 0.1% above entry
                
                # Place new SL order
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
                    system_logger.info(f"SL moved to breakeven for {self.symbol}")
                else:
                    system_logger.error(f"Failed to move SL to breakeven: {result}")
                    
        except Exception as e:
            system_logger.error(f"Breakeven SL move error: {e}", exc_info=True)
    
    async def _update_leverage(self, new_leverage: Decimal):
        """Update leverage to maximum."""
        try:
            result = await self.bybit.set_leverage(
                category="linear",
                symbol=self.symbol,
                buy_leverage=str(new_leverage),
                sell_leverage=str(new_leverage)
            )
            
            if result.get('retCode') == 0:
                system_logger.info(f"Leverage updated to {new_leverage}x for {self.symbol}")
            else:
                system_logger.error(f"Failed to update leverage: {result}")
                
        except Exception as e:
            system_logger.error(f"Leverage update error: {e}", exc_info=True)
    
    async def _update_position_size(self, new_im: Decimal):
        """Update position size to new IM target."""
        try:
            # Get current position
            pos = await self.bybit.positions("linear", self.symbol)
            if pos.get("result", {}).get("list"):
                position = pos["result"]["list"][0]
                current_size = Decimal(str(position.get("size", "0")))
                avg_price = Decimal(str(position.get("avgPrice", "0")))
                leverage = Decimal(str(position.get("leverage", "1")))
                
                # Calculate new position size based on new IM
                new_size = (new_im * leverage) / avg_price
                size_difference = new_size - current_size
                
                if size_difference > 0:
                    # Add to position
                    order_body = {
                        "category": "linear",
                        "symbol": self.symbol,
                        "side": self.direction,
                        "orderType": "Market",
                        "qty": str(size_difference),
                        "timeInForce": "IOC",
                        "reduceOnly": False,
                        "positionIdx": 0,
                        "orderLinkId": f"pyramid_{self.trade_id}_{len(self.activated_levels)}"
                    }
                    
                    result = await self.bybit.place_order(order_body)
                    if result.get('retCode') == 0:
                        system_logger.info(f"Position size increased by {size_difference} for {self.symbol}")
                    else:
                        system_logger.error(f"Failed to increase position size: {result}")
                        
        except Exception as e:
            system_logger.error(f"Position size update error: {e}", exc_info=True)
