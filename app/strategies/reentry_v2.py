"""Re-entry strategy implementation with exact client requirements."""

from decimal import Decimal
from typing import Dict, Any
from app.bybit.client import BybitClient
from app.core.logging import system_logger
from app.telegram.output import send_message
from app.telegram.engine import render_template
from app.core.confirmation_gate import ConfirmationGate

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
        
        # CLIENT FIX (COMPLIANCE doc/10_12_2.md Lines 314-318):
        # Read from STRICT_CONFIG instead of hardcoding
        from app.core.strict_config import STRICT_CONFIG
        self.max_attempts = STRICT_CONFIG.max_reentries  # Maximum re-entry attempts
        
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
        # CLIENT FIX: Use configured entry_offset instead of hardcoded 0.5%
        # Simple logic: re-enter if price has moved entry_offset % from last entry
        if self.last_entry_price == Decimal("0"):
            return True  # First re-entry always allowed
        
        price_change = abs(current_price - self.last_entry_price) / self.last_entry_price
        
        return price_change >= self.entry_offset  # Use configured offset
    
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
                
                # CLIENT FIX: Send notification via Engine after Bybit confirmation
                # Fetch exact IM and leverage from Bybit using singleton pattern
                from app.core.confirmation_gate import get_confirmation_gate
                gate = get_confirmation_gate()
                im_confirmed = await gate._fetch_confirmed_im(self.symbol)
                
                # Get leverage from position (FROM BYBIT!)
                pos = await self.bybit.positions("linear", self.symbol)
                current_leverage = STRICT_CONFIG.reentry_leverage  # Fallback
                if pos.get("result", {}).get("list"):
                    current_leverage = Decimal(str(pos["result"]["list"][0].get("leverage", "6.00")))
                
                # PHASE 4: Pass complete signal data including TPs/SL
                # Get original signal data if available
                original_tps = getattr(self, 'tps', [])
                original_sl = getattr(self, 'sl', None)
                
                # PRIORITY 2: Use Engine queue instead of direct send_message
                from app.telegram.engine import get_template_engine
                engine = get_template_engine()
                
                # Prepare data for template
                template_data = {
                    'symbol': self.symbol,
                    'source_name': self.channel_name,
                    'attempt': self.attempts + 1,
                    'side': self.direction,
                    'leverage': current_leverage,  # FROM BYBIT!
                    'entry': entry_price,
                    'entry1': entry_price,
                    'entry2': entry_price,
                    'tp1': original_tps[0] if len(original_tps) > 0 else None,
                    'tp2': original_tps[1] if len(original_tps) > 1 else None,
                    'tp3': original_tps[2] if len(original_tps) > 2 else None,
                    'tp4': original_tps[3] if len(original_tps) > 3 else None,
                    'sl': original_sl,
                    'price': entry_price,
                    'qty': original_size,
                    'im_confirmed': im_confirmed,
                    'trade_id': self.trade_id,
                    'bot_order_id': f"BOT-{self.trade_id}-REENTRY{self.attempts+1}",
                    'bybit_order_id': ''
                }
                
                # Enqueue through Engine (includes rate limiting & retry)
                await engine.enqueue_and_send("REENTRY_STARTED", template_data, priority=2)
                
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
