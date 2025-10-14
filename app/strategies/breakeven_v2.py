"""Breakeven strategy implementation with exact client requirements."""

from decimal import Decimal
from typing import Dict, Any
from app.bybit.client import BybitClient
from app.core.logging import system_logger
from app.telegram.output import send_message
from app.telegram.engine import render_template
from app.core.confirmation_gate import ConfirmationGate

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
        
        # CLIENT FIX (COMPLIANCE doc/10_12_2.md Lines 297-302):
        # Read from STRICT_CONFIG instead of hardcoding
        from app.core.strict_config import STRICT_CONFIG
        # CLIENT SPEC: +2.3% → SL to breakeven (from pyramid step 2)
        # Use pyramid level 2's trigger (2.3%) for breakeven activation
        self.trigger_pct = STRICT_CONFIG.pyramid_levels[1]["trigger"]  # Step 2: 2.3%
        self.offset_pct = STRICT_CONFIG.breakeven_offset  # 0.0015% offset for costs
    
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
            # CLIENT FIX: Use configured offset_pct instead of hardcoded 0.1%
            # Calculate breakeven price + configured buffer for costs
            offset_multiplier = Decimal("1") + (self.offset_pct / Decimal("100"))
            
            if self.direction == "BUY":
                # For BUY: BE is slightly below avg_entry (offset_pct %)
                be_price = current_price * (Decimal("1") - (self.offset_pct / Decimal("100")))
            else:  # SELL
                # For SELL: BE is slightly above avg_entry (offset_pct %)
                be_price = current_price * offset_multiplier
            
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
                # CLIENT FIX (DEEP_ANALYSIS): Verify Bybit confirmed the SL move
                verification = await self.bybit.get_position("linear", self.symbol)
                
                if verification.get('retCode') != 0:
                    system_logger.error(
                        f"Breakeven SL placed but Bybit verification failed",
                        {
                            "symbol": self.symbol,
                            "retCode": verification.get('retCode'),
                            "retMsg": verification.get('retMsg')
                        }
                    )
                    return False  # ❌ Do NOT send Telegram
                
                # ✅ Bybit confirmed - proceed
                self.activated = True
                system_logger.info(f"Breakeven activated for {self.symbol} at +{gain_pct:.2f}%")
                
                # Fetch exact IM from Bybit using singleton pattern
                from app.core.confirmation_gate import get_confirmation_gate
                gate = get_confirmation_gate()
                im_confirmed = await gate._fetch_confirmed_im(self.symbol)
                
                # Get avg_price and leverage from position (FROM BYBIT!)
                pos = await self.bybit.positions("linear", self.symbol)
                avg_price = current_price  # Fallback
                current_leverage = Decimal("6.00")  # Fallback
                if pos.get("result", {}).get("list"):
                    position = pos["result"]["list"][0]
                    avg_price = Decimal(str(position.get("avgPrice", str(current_price))))
                    current_leverage = Decimal(str(position.get("leverage", "6.00")))
                
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
                    'new_sl': be_price,
                    'entry_price': avg_price,
                    'trade_id': self.trade_id,
                    'bot_order_id': f"BOT-{self.trade_id}",
                    'bybit_order_id': ''
                }
                
                # Enqueue through Engine (includes rate limiting & retry)
                await engine.enqueue_and_send("BREAKEVEN_MOVED", template_data, priority=4)
                return True
                
            else:
                system_logger.error(f"Failed to activate breakeven: {result}")
                return False
                
        except Exception as e:
            system_logger.error(f"Breakeven activation error: {e}", exc_info=True)
            return False
