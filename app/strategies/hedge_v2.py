"""Hedge strategy implementation with exact client requirements."""

from decimal import Decimal
from typing import Dict, Any, Optional
from app.bybit.client import BybitClient
from app.core.logging import system_logger
from app.telegram.output import send_message
from app.telegram.engine import render_template
from app.core.confirmation_gate import ConfirmationGate

class HedgeStrategyV2:
    """Hedge strategy: Opens reverse position at -2% adverse move."""
    
    def __init__(self, trade_id: str, symbol: str, direction: str, original_entry: Decimal, channel_name: str):
        self.trade_id = trade_id
        self.symbol = symbol
        self.direction = direction.upper()
        self.original_entry = original_entry
        self.channel_name = channel_name
        from app.bybit.client import get_bybit_client
        self.bybit = get_bybit_client()
        self.activated = False
        
        # CLIENT FIX (COMPLIANCE doc/10_12_2.md Lines 309-313):
        # Read from STRICT_CONFIG instead of hardcoding
        from app.core.strict_config import STRICT_CONFIG
        self.trigger_pct = abs(STRICT_CONFIG.hedge_trigger)  # -2% trigger (stored as -2.0, use abs)
        
        self.hedge_size: Optional[Decimal] = None
        self.retry_count = 0
        self.max_retries = 3  # Maximum retry attempts for hedge activation
    
    async def check_and_activate(self, current_price: Decimal, original_entry: Decimal) -> bool:
        """Check if hedge should be activated."""
        if self.activated:
            return True
        
        # First check if position still exists
        try:
            pos = await self.bybit.positions("linear", self.symbol)
            if not pos.get("result", {}).get("list"):
                system_logger.warning(f"No position found for {self.symbol} - hedge check skipped")
                return False
            
            position = pos["result"]["list"][0]
            current_size = Decimal(str(position.get("size", "0")))
            
            if current_size <= 0:
                system_logger.warning(f"Position size is 0 for {self.symbol} - hedge check skipped")
                return False
                
        except Exception as e:
            system_logger.error(f"Failed to check position for hedge: {e}")
            return False
        
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
            # Check if already activated to prevent infinite loops
            if self.activated:
                system_logger.info(f"Hedge already activated for {self.symbol} - skipping")
                return False
            
            # Check retry limit
            if self.retry_count >= self.max_retries:
                system_logger.warning(f"Maximum retry attempts ({self.max_retries}) reached for hedge {self.symbol} - marking as activated")
                self.activated = True
                return False
            
            # Increment retry counter
            self.retry_count += 1
            system_logger.info(f"Hedge activation attempt {self.retry_count}/{self.max_retries} for {self.symbol}")
            
            # Get current position size
            pos = await self.bybit.positions("linear", self.symbol)
            if not pos.get("result", {}).get("list"):
                system_logger.error(f"No position found for {self.symbol}")
                self.activated = True  # Mark as activated to prevent retries
                return False
            
            position = pos["result"]["list"][0]
            current_size = Decimal(str(position.get("size", "0")))
            
            if current_size <= 0:
                system_logger.error(f"Invalid position size: {current_size}")
                self.activated = True  # Mark as activated to prevent retries
                return False
            
            # Check account balance before placing order
            try:
                balance = await self.bybit.get_wallet_balance("UNIFIED")
                if balance and balance.get('retCode') == 0:
                    total_balance = Decimal(str(balance.get('result', {}).get('totalWalletBalance', '0')))
                    if total_balance < Decimal("10"):  # Minimum 10 USDT required
                        system_logger.warning(f"Insufficient balance for hedge: {total_balance} USDT")
                        self.activated = True  # Mark as activated to prevent retries
                        return False
                else:
                    system_logger.warning(f"Could not check balance, proceeding with hedge attempt")
            except Exception as e:
                system_logger.warning(f"Balance check failed: {e}, proceeding with hedge attempt")
            
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
                
                # CLIENT FIX: Send notification via Engine after Bybit confirmation
                # Fetch exact IM from Bybit using singleton pattern
                from app.core.confirmation_gate import get_confirmation_gate
                gate = get_confirmation_gate()
                im_confirmed = await gate._fetch_confirmed_im(self.symbol)
                
                # Get leverage from position (FROM BYBIT!)
                pos = await self.bybit.positions("linear", self.symbol)
                current_leverage = Decimal("6.00")  # Fallback
                if pos.get("result", {}).get("list"):
                    current_leverage = Decimal(str(pos["result"]["list"][0].get("leverage", "6.00")))
                
                # Calculate hedge details
                hedge_side = "SHORT" if self.direction == "BUY" else "LONG"
                
                # PRIORITY 2: Use Engine queue instead of direct send_message
                from app.telegram.engine import get_template_engine
                engine = get_template_engine()
                
                # Prepare data for template
                template_data = {
                    'symbol': self.symbol,
                    'source_name': self.channel_name,
                    'side': self.direction,  # Original side
                    'leverage': current_leverage,  # FROM BYBIT!
                    'sl': getattr(self, 'sl', None),  # For type detection
                    'price': current_price,
                    'qty': self.hedge_size,
                    'im': im_confirmed,  # Hedge IM
                    'trade_id': self.trade_id,
                    'bot_order_id': f"BOT-{self.trade_id}-HEDGE",
                    'bybit_order_id': ''
                }
                
                # Enqueue through Engine (includes rate limiting & retry)
                await engine.enqueue_and_send("HEDGE_STARTED", template_data, priority=2)
            else:
                # Handle specific error codes
                error_code = result.get('retCode')
                error_msg = result.get('retMsg', '')
                
                if error_code == 110007:  # "ab not enough for new order"
                    system_logger.warning(f"Insufficient balance for hedge order: {error_msg}")
                    self.activated = True  # Mark as activated to prevent infinite retries
                elif error_code == 10001:  # Parameter error
                    system_logger.error(f"Hedge order parameter error: {error_msg}")
                    self.activated = True  # Mark as activated to prevent retries
                else:
                    system_logger.error(f"Failed to activate hedge (attempt {self.retry_count}/{self.max_retries}): {result}")
                    # Don't mark as activated for other errors, allow retry up to max_retries
                
        except Exception as e:
            system_logger.error(f"Hedge activation error (attempt {self.retry_count}/{self.max_retries}): {e}", exc_info=True)
            # Mark as activated to prevent infinite retries on exceptions
            self.activated = True
    
    async def close_hedge(self):
        """Close the hedge position."""
        try:
            if not self.hedge_size:
                return False
            
            # Get current position
            pos = await self.bybit.positions("linear", self.symbol)
            if not pos.get("result", {}).get("list"):
                return False
            
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
