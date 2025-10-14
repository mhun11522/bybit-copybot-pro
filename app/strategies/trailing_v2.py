"""Trailing stop strategy implementation with exact client requirements."""

from decimal import Decimal
from typing import Dict, Any, Optional
from app.bybit.client import BybitClient
from app.core.logging import system_logger
from app.telegram.output import send_message
from app.telegram.engine import render_template
from app.core.confirmation_gate import ConfirmationGate

class TrailingStopStrategyV2:
    """Trailing stop strategy: Activates at +6.1%, SL 2.5% behind highest/lowest price."""
    
    def __init__(self, trade_id: str, symbol: str, direction: str, channel_name: str):
        self.trade_id = trade_id
        self.symbol = symbol
        self.direction = direction.upper()
        self.channel_name = channel_name
        from app.bybit.client import get_bybit_client
        self.bybit = get_bybit_client()
        self.armed = False
        
        # CLIENT FIX (COMPLIANCE doc/10_12_2.md Lines 303-308):
        # Read from STRICT_CONFIG instead of hardcoding
        from app.core.strict_config import STRICT_CONFIG
        self.trigger_pct = STRICT_CONFIG.trailing_trigger  # 6.1% trigger (CLIENT SPEC)
        self.trail_distance = STRICT_CONFIG.trailing_distance  # 2.5% behind price (CLIENT SPEC)
        
        self.highest_price: Optional[Decimal] = None
        self.lowest_price: Optional[Decimal] = None
        self.current_sl: Optional[Decimal] = None
        self.tps_cancelled = False
    
    async def check_and_update(self, current_price: Decimal, original_entry: Decimal) -> bool:
        """Check if trailing should be activated and update SL."""
        # Calculate gain from original entry
        if self.direction == "BUY":
            gain_pct = (current_price - original_entry) / original_entry * 100
        else:  # SELL
            gain_pct = (original_entry - current_price) / original_entry * 100
        
        # Check if we should arm trailing
        if not self.armed and gain_pct >= self.trigger_pct:
            await self._arm_trailing(current_price, gain_pct)
            self.armed = True
        
        # Update trailing if armed
        if self.armed:
            await self._update_trailing(current_price)
            return True
        
        return False
    
    async def _arm_trailing(self, current_price: Decimal, gain_pct: Decimal):
        """Arm the trailing stop."""
        try:
            # Cancel all TPs below 6.1% when trailing starts
            if not self.tps_cancelled:
                await self._cancel_tps_below_6_1_percent()
                self.tps_cancelled = True
            
            # Set initial trailing SL at 2.5% behind current price
            if self.direction == "BUY":
                initial_sl = current_price * (Decimal("1") - self.trail_distance / 100)
                self.highest_price = current_price
            else:  # SELL
                initial_sl = current_price * (Decimal("1") + self.trail_distance / 100)
                self.lowest_price = current_price
            
            await self._place_trailing_sl(initial_sl)
            
            # CLIENT FIX (DEEP_ANALYSIS): Verify Bybit confirmed the trailing SL
            verification = await self.bybit.get_position("linear", self.symbol)
            
            if verification.get('retCode') != 0:
                system_logger.error(
                    f"Trailing SL placed but Bybit verification failed",
                    {
                        "symbol": self.symbol,
                        "retCode": verification.get('retCode'),
                        "retMsg": verification.get('retMsg')
                    }
                )
                return  # ❌ Do NOT send Telegram
            
            # ✅ Bybit confirmed - proceed
            system_logger.info(f"Trailing stop armed for {self.symbol} at +{gain_pct:.2f}%")
            
            # Fetch exact IM from Bybit using singleton pattern
            from app.core.confirmation_gate import get_confirmation_gate
            gate = get_confirmation_gate()
            im_confirmed = await gate._fetch_confirmed_im(self.symbol)
            
            # Get current leverage for profit calculation
            pos = await self.bybit.positions("linear", self.symbol)
            current_leverage = Decimal("1")
            if pos.get("result", {}).get("list"):
                current_leverage = Decimal(str(pos["result"]["list"][0].get("leverage", "1")))
            
            # CLIENT FIX: Calculate PnL WITH LEVERAGE
            # gain_pct is trade % (price movement)
            # Client requirement: Must multiply by leverage
            pnl_pct_leveraged = gain_pct * current_leverage  # WITH LEVERAGE!
            pnl_usdt = im_confirmed * (pnl_pct_leveraged / Decimal("100"))  # Estimated
            
            # Calculate new SL based on trail distance
            if self.direction == "BUY":
                new_sl = current_price * (Decimal("1") - (self.trail_distance / Decimal("100")))
            else:
                new_sl = current_price * (Decimal("1") + (self.trail_distance / Decimal("100")))
            
            # PRIORITY 2: Use Engine queue instead of direct send_message
            from app.telegram.engine import get_template_engine
            engine = get_template_engine()
            
            # Prepare data for template
            template_data = {
                'symbol': self.symbol,
                'source_name': self.channel_name,
                'side': self.direction,
                'leverage': current_leverage,  # FROM BYBIT!
                'sl': getattr(self, 'sl', None),  # For type detection
                'trigger_pct': float(gain_pct),
                'trail_dist_pct': float(self.trail_distance),
                'new_extreme': current_price,
                'new_sl': new_sl,
                'pnl_pct': float(pnl_pct_leveraged),  # WITH LEVERAGE!
                'pnl_usdt': pnl_usdt,
                'trade_id': self.trade_id,
                'bot_order_id': f"BOT-{self.trade_id}",
                'bybit_order_id': ''
            }
            
            # Enqueue through Engine (includes rate limiting & retry)
            await engine.enqueue_and_send("TRAILING_ACTIVATED", template_data, priority=3)
            
        except Exception as e:
            system_logger.error(f"Trailing stop arming error: {e}", exc_info=True)
    
    async def _update_trailing(self, current_price: Decimal):
        """Update trailing stop based on current price."""
        try:
            new_sl = None
            
            if self.direction == "BUY":
                # Update highest price
                if self.highest_price is None or current_price > self.highest_price:
                    self.highest_price = current_price
                    new_sl = current_price * (Decimal("1") - self.trail_distance / 100)
            else:  # SELL
                # Update lowest price
                if self.lowest_price is None or current_price < self.lowest_price:
                    self.lowest_price = current_price
                    new_sl = current_price * (Decimal("1") + self.trail_distance / 100)
            
            # Update SL if we have a better price
            if new_sl and (self.current_sl is None or self._is_better_sl(new_sl)):
                await self._place_trailing_sl(new_sl)
                self.current_sl = new_sl
                
        except Exception as e:
            system_logger.error(f"Trailing stop update error: {e}", exc_info=True)
    
    def _is_better_sl(self, new_sl: Decimal) -> bool:
        """Check if new SL is better than current SL."""
        if self.current_sl is None:
            return True
        
        if self.direction == "BUY":
            return new_sl > self.current_sl  # Higher SL is better for BUY
        else:  # SELL
            return new_sl < self.current_sl  # Lower SL is better for SELL
    
    async def _place_trailing_sl(self, sl_price: Decimal):
        """Place trailing stop loss order."""
        try:
            order_body = {
                "category": "linear",
                "symbol": self.symbol,
                "side": "Sell" if self.direction == "BUY" else "Buy",
                "orderType": "Limit",
                "qty": "0",  # Will be filled by position size
                "price": str(sl_price),
                "timeInForce": "GTC",
                "reduceOnly": True,
                "positionIdx": 0,
                "orderLinkId": f"trail_{self.trade_id}"
            }
            
            result = await self.bybit.place_order(order_body)
            
            if result.get('retCode') == 0:
                system_logger.info(f"Trailing SL updated to {sl_price} for {self.symbol}")
            else:
                system_logger.error(f"Failed to update trailing SL: {result}")
                
        except Exception as e:
            system_logger.error(f"Trailing SL placement error: {e}", exc_info=True)
    
    async def _cancel_tps_below_6_1_percent(self):
        """Cancel all TP orders below 6.1% profit."""
        try:
            # Get open orders
            orders = await self.bybit.get_open_orders("linear", self.symbol)
            
            if orders.get("result", {}).get("list"):
                for order in orders["result"]["list"]:
                    order_type = order.get("orderType", "")
                    reduce_only = order.get("reduceOnly", False)
                    
                    # Cancel TP orders (reduce-only orders that are not SL)
                    if reduce_only and order_type == "Limit":
                        order_id = order.get("orderId", "")
                        if order_id:
                            cancel_result = await self.bybit.cancel_order("linear", self.symbol, order_id)
                            if cancel_result.get('retCode') == 0:
                                system_logger.info(f"Cancelled TP order {order_id} for {self.symbol}")
                            else:
                                system_logger.error(f"Failed to cancel TP order: {cancel_result}")
                                
        except Exception as e:
            system_logger.error(f"TP cancellation error: {e}", exc_info=True)
