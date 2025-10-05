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
        from app.bybit.client import get_bybit_client
        self.bybit = get_bybit_client()
        # Pyramid levels calculated from ORIGINAL ENTRY as per client requirements
        self.levels = {
            Decimal("1.5"): {"action": "check_im", "target_im": Decimal("20")},   # +1.5%: Check IM is 20 USDT if any TP hit
            Decimal("2.3"): {"action": "sl_to_be"},                               # +2.3%: SL moved to breakeven + costs
            Decimal("2.4"): {"action": "max_leverage", "target_lev": Decimal("50")}, # +2.4%: Leverage raised to max 50x
            Decimal("2.5"): {"action": "add_im", "target_im": Decimal("40")},     # +2.5%: IM increased to total 40 USDT
            Decimal("4.0"): {"action": "add_im", "target_im": Decimal("60")},     # +4.0%: IM increased to total 60 USDT
            Decimal("6.0"): {"action": "add_im", "target_im": Decimal("80")},     # +6.0%: IM increased to total 80 USDT
            Decimal("8.6"): {"action": "add_im", "target_im": Decimal("100")},    # +8.6%: IM increased to total 100 USDT
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
    
    async def _activate_level(self, level_pct: Decimal, config: Dict[str, Any], gain_pct: Decimal):
        """Activate a pyramid level based on action type."""
        try:
            level_num = len(self.activated_levels) + 1
            action = config.get("action", "")
            
            if action == "check_im":
                # +1.5%: Check that IM is 20 USDT if any TP has been hit
                await self._check_im_20_if_tp_hit()
                
            elif action == "sl_to_be":
                # +2.3%: SL is moved to breakeven + costs
                await self._move_sl_to_breakeven()
                
            elif action == "max_leverage":
                # +2.4%: Leverage is raised to max (up to 50x) and position recalculated
                target_lev = config.get("target_lev", Decimal("50"))
                await self._update_leverage(target_lev)
                
            elif action == "add_im":
                # +2.5%, +4%, +6%, +8.6%: IM increased to target total
                target_im = config.get("target_im", Decimal("20"))
                await self._update_position_size(target_im)
            
            system_logger.info(f"Pyramid level {level_num} activated for {self.symbol} at +{gain_pct:.2f}% - Action: {action}")
            
            # Send notification
            signal_data = {
                'symbol': self.symbol,
                'channel_name': self.channel_name,
                'level': level_num,
                'gain_pct': f"{gain_pct:.2f}",
                'action': action,
                'target_im': str(config.get("target_im", "20")),
                'target_leverage': str(config.get("target_lev", "10"))
            }
            message = SwedishTemplatesV2.pyramid_activated(signal_data)
            await send_message(message)
            
        except Exception as e:
            system_logger.error(f"Pyramid level activation error: {e}", exc_info=True)
    
    async def _check_im_20_if_tp_hit(self):
        """Check that IM is 20 USDT if any TP has been hit."""
        try:
            # Get current position
            pos = await self.bybit.get_position("linear", self.symbol)
            if pos.get("result", {}).get("list"):
                position = pos["result"]["list"][0]
                current_im = Decimal(str(position.get("initialMargin", "0")))
                
                # Check if any TP has been hit by looking at position size vs original
                # If position size is reduced, it means some TPs were hit
                current_size = Decimal(str(position.get("size", "0")))
                
                # If IM is less than 20 USDT and TPs were hit, add to position
                if current_im < Decimal("20") and current_size > 0:
                    # Add to position to bring IM to 20 USDT
                    im_to_add = Decimal("20") - current_im
                    await self._add_im_to_position(im_to_add)
                    
                    system_logger.info(f"Added {im_to_add} USDT IM to bring total to 20 USDT for {self.symbol}")
                    
        except Exception as e:
            system_logger.error(f"IM check error: {e}", exc_info=True)

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
    
    async def _add_im_to_position(self, im_to_add: Decimal):
        """Add specific IM amount to position."""
        try:
            # Get current position
            pos = await self.bybit.get_position("linear", self.symbol)
            if pos.get("result", {}).get("list"):
                position = pos["result"]["list"][0]
                current_size = Decimal(str(position.get("size", "0")))
                avg_price = Decimal(str(position.get("avgPrice", "0")))
                leverage = Decimal(str(position.get("leverage", "1")))
                
                # Calculate additional size needed for the IM
                additional_size = (im_to_add * leverage) / avg_price
                
                if additional_size > 0:
                    # Add to position
                    order_body = {
                        "category": "linear",
                        "symbol": self.symbol,
                        "side": self.direction,
                        "orderType": "Market",
                        "qty": str(additional_size),
                        "timeInForce": "IOC",
                        "reduceOnly": False,
                        "positionIdx": 0,
                        "orderLinkId": f"add_im_{self.trade_id}_{len(self.activated_levels)}"
                    }
                    
                    result = await self.bybit.place_order(order_body)
                    if result.get('retCode') == 0:
                        system_logger.info(f"Added {additional_size} contracts (${im_to_add} IM) to {self.symbol}")
                    else:
                        system_logger.error(f"Failed to add IM: {result}")
                        
        except Exception as e:
            system_logger.error(f"Add IM error: {e}", exc_info=True)
