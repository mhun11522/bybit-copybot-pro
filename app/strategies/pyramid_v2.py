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
        # Pyramid levels calculated from ORIGINAL ENTRY as per CLIENT SPECIFICATION
        # CRITICAL: All percentages calculated from ORIGINAL ENTRY, not current price
        # DO NOT MODIFY THESE VALUES WITHOUT CLIENT APPROVAL
        self.levels = {
            Decimal("1.5"): {"action": "im_total", "target_im": Decimal("20")},   # Step 1: +1.5% → IM total 20 USDT
            Decimal("2.3"): {"action": "sl_breakeven"},                           # Step 2: +2.3% → SL to breakeven
            Decimal("2.4"): {"action": "set_full_leverage"},                      # Step 3: +2.4% → Full leverage (ETH=50x cap, others=instrument max)
            Decimal("2.5"): {"action": "im_total", "target_im": Decimal("40")},   # Step 4: +2.5% → IM total 40 USDT
            Decimal("4.0"): {"action": "im_total", "target_im": Decimal("60")},   # Step 5: +4.0% → IM total 60 USDT
            Decimal("6.0"): {"action": "im_total", "target_im": Decimal("80")},   # Step 6: +6.0% → IM total 80 USDT
            Decimal("8.1"): {"action": "im_total", "target_im": Decimal("100")},  # Step 7: +8.1% → IM total 100 USDT (FIXED from 8.6%)
        }
        self.activated_levels = set()
        self.max_adds = 7
    
    async def check_and_activate(self, current_price: Decimal) -> bool:
        """Check if pyramid levels should be activated."""
        # Calculate gain from original entry
        if self.direction == "LONG":
            gain_pct = (current_price - self.original_entry) / self.original_entry * 100
        else:  # SHORT
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
            
            success = False
            
            if action == "im_total":
                # Steps 1, 4, 5, 6, 7: IM increased to target total
                target_im = config.get("target_im", Decimal("20"))
                success = await self._update_position_size_to_total_im(target_im)
                
            elif action == "sl_breakeven":
                # Step 2: +2.3%: SL is moved to breakeven + costs
                success = await self._move_sl_to_breakeven()
                
            elif action == "set_full_leverage":
                # Step 3: +2.4%: Set full leverage (ETH=50x cap, others=instrument max)
                success = await self._set_full_leverage()
                
            elif action == "add_im":
                # Legacy action name - treat as im_total
                target_im = config.get("target_im", Decimal("20"))
                success = await self._update_position_size_to_total_im(target_im)
            
            if success:
                system_logger.info(f"Pyramid level {level_num} activated for {self.symbol} at +{gain_pct:.2f}% - Action: {action}")
                
                # Send notification only if Bybit operation succeeded
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
            else:
                system_logger.error(f"Pyramid action {action} failed for {self.symbol}; not sending activation message")
            
        except Exception as e:
            system_logger.error(f"Pyramid level activation error: {e}", exc_info=True)
    
    async def _check_im_20_if_tp_hit(self) -> bool:
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
                    return True
                else:
                    return True  # IM already at target or no position
            return False
        except Exception as e:
            system_logger.error(f"IM check error: {e}", exc_info=True)
            return False

    async def _move_sl_to_breakeven(self) -> bool:
        """Move SL to breakeven + costs."""
        try:
            # Get current position
            pos = await self.bybit.positions("linear", self.symbol)
            if pos.get("result", {}).get("list"):
                position = pos["result"]["list"][0]
                avg_price = Decimal(str(position.get("avgPrice", "0")))
                
                # Calculate breakeven + small buffer
                if self.direction == "LONG":
                    be_price = avg_price * Decimal("0.999")  # 0.1% below entry
                else:  # SELL
                    be_price = avg_price * Decimal("1.001")  # 0.1% above entry
                
                # Place new SL order
                order_body = {
                    "category": "linear",
                    "symbol": self.symbol,
                    "side": "Sell" if self.direction == "LONG" else "Buy",
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
    
    async def _set_full_leverage(self) -> bool:
        """
        Step 3: Set full leverage (CLIENT SPEC).
        
        RULES:
        - ETH: Set to 50x (capped by instrument max if lower)
        - Other symbols: Set to instrument max
        """
        try:
            from app.core.leverage_policy import LeveragePolicy
            
            # Get instrument max leverage
            instrument_max = await LeveragePolicy.get_instrument_max_leverage(self.symbol)
            
            # Determine target leverage
            if "ETH" in self.symbol.upper():
                # ETH: min(50, instrument_max)
                target_leverage = min(Decimal("50"), instrument_max)
                system_logger.info(f"ETH pyramid step 3: setting leverage to {target_leverage}x (cap=50x, instrument_max={instrument_max}x)")
            else:
                # Other symbols: use instrument max
                target_leverage = instrument_max
                system_logger.info(f"Pyramid step 3: setting leverage to instrument max {target_leverage}x for {self.symbol}")
            
            # Set leverage via Bybit API
            result = await self.bybit.set_leverage(
                category="linear",
                symbol=self.symbol,
                buy_leverage=str(target_leverage),
                sell_leverage=str(target_leverage)
            )
            
            # Check for success (retCode 0 or 110043 "leverage not modified")
            if result.get('retCode') in [0, 110043]:
                system_logger.info(f"Full leverage set to {target_leverage}x for {self.symbol}")
                return True
            else:
                system_logger.error(f"Failed to set full leverage: {result}")
                return False
                
        except Exception as e:
            system_logger.error(f"Set full leverage error: {e}", exc_info=True)
            return False
    
    async def _update_leverage(self, new_leverage: Decimal) -> bool:
        """
        Update leverage (legacy method, kept for compatibility).
        Use _set_full_leverage() for Step 3 instead.
        """
        try:
            result = await self.bybit.set_leverage(
                category="linear",
                symbol=self.symbol,
                buy_leverage=str(new_leverage),
                sell_leverage=str(new_leverage)
            )
            
            if result.get('retCode') in [0, 110043]:  # 0=success, 110043=no change needed
                system_logger.info(f"Leverage updated to {new_leverage}x for {self.symbol}")
                return True
            else:
                system_logger.error(f"Failed to update leverage: {result}")
                return False
        except Exception as e:
            system_logger.error(f"Leverage update error: {e}", exc_info=True)
            return False
    
    async def _update_position_size_to_total_im(self, target_im_total: Decimal) -> bool:
        """
        Update position size to reach target TOTAL IM (CLIENT SPEC).
        
        IMPORTANT: target_im_total is the TOTAL IM desired, not the amount to add.
        Calculate how much to add by: (target_total - current_im)
        
        Args:
            target_im_total: Target total IM in USDT (e.g., 20, 40, 60, 80, 100)
        
        Returns:
            True if successful or no action needed, False on error
        """
        try:
            # Get current position
            pos = await self.bybit.positions("linear", self.symbol)
            if pos.get("result", {}).get("list"):
                position = pos["result"]["list"][0]
                current_size = Decimal(str(position.get("size", "0")))
                current_im = Decimal(str(position.get("positionIM", "0")))  # Current IM
                avg_price = Decimal(str(position.get("avgPrice", "0")))
                leverage = Decimal(str(position.get("leverage", "1")))
                
                # Calculate IM to add
                im_to_add = target_im_total - current_im
                
                if im_to_add <= 0:
                    system_logger.info(f"IM already at or above target ({current_im} >= {target_im_total}), no action needed")
                    return True  # Already at target
                
                # Calculate additional size needed
                # Formula: additional_qty = (im_to_add * leverage) / price
                additional_size = (im_to_add * leverage) / avg_price
                
                system_logger.info(f"Adding {im_to_add} USDT IM to {self.symbol} (current: {current_im}, target: {target_im_total})")
                
                # Add to position
                bybit_side = "Buy" if self.direction == "LONG" else "Sell"
                
                order_body = {
                    "category": "linear",
                    "symbol": self.symbol,
                    "side": bybit_side,
                    "orderType": "Market",
                    "qty": str(additional_size),
                    "timeInForce": "IOC",
                    "reduceOnly": False,
                    "positionIdx": 0,
                    "orderLinkId": f"pyramid_im_{self.trade_id}_{len(self.activated_levels)}"
                }
                
                result = await self.bybit.place_order(order_body)
                if result.get('retCode') == 0:
                    system_logger.info(f"Position IM increased to {target_im_total} USDT for {self.symbol} (+{additional_size} contracts)")
                    return True
                else:
                    system_logger.error(f"Failed to increase position IM: {result}")
                    return False
            return False
        except Exception as e:
            system_logger.error(f"Update position size to total IM error: {e}", exc_info=True)
            return False
    
    async def _update_position_size(self, new_im: Decimal) -> bool:
        """
        Update position size to new IM target (legacy method).
        Use _update_position_size_to_total_im() for new code.
        """
        return await self._update_position_size_to_total_im(new_im)
    
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
                    # Convert direction to Bybit format for adding margin
                    # For LONG positions: adding margin requires Buy orders
                    # For SHORT positions: adding margin requires Sell orders
                    bybit_side = "Buy" if self.direction == "LONG" else "Sell"
                    
                    # Add to position
                    order_body = {
                        "category": "linear",
                        "symbol": self.symbol,
                        "side": bybit_side,  # Correct side for adding margin
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
