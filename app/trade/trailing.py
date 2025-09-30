"""Trailing Stop Manager with +6.1% trigger and 2.5% band."""

import asyncio
from decimal import Decimal
from app.bybit.client import BybitClient
from app.core.precision import q_price, q_qty
from app.telegram.output import send_message
from app.config.settings import CATEGORY

class TrailingStopManager:
    """Manages trailing stops with +6.1% trigger and 2.5% band."""
    
    def __init__(self, trade_id, symbol, direction, avg_entry, position_size, channel_name):
        self.trade_id = trade_id
        self.symbol = symbol
        self.direction = direction
        self.avg_entry = Decimal(str(avg_entry))
        self.position_size = Decimal(str(position_size))
        self.channel_name = channel_name
        self.bybit = BybitClient()
        self._running = False
        self.trailing_active = False
        self.highest_price = self.avg_entry

    async def run(self):
        """Run trailing stop monitoring."""
        self._running = True
        print(f"🔄 Trailing Stop Manager started for {self.symbol}")
        
        while self._running:
            try:
                # Get current mark price
                mark_price = await self._get_mark_price()
                if not mark_price:
                    await asyncio.sleep(3)
                    continue
                
                # Check if we should activate trailing
                if not self.trailing_active:
                    gain_pct = self._calculate_gain(mark_price)
                    if gain_pct >= Decimal("0.061"):  # +6.1%
                        self.trailing_active = True
                        await self._activate_trailing(mark_price)
                
                # Update trailing stop if active
                if self.trailing_active:
                    await self._update_trailing_stop(mark_price)
                    
            except Exception as e:
                print(f"❌ Trailing stop error for {self.symbol}: {e}")
            
            await asyncio.sleep(3)

    async def _get_mark_price(self):
        """Get current mark price."""
        try:
            positions = await self.bybit.positions(CATEGORY, self.symbol)
            if positions.get("result", {}).get("list"):
                return Decimal(str(positions["result"]["list"][0].get("markPrice", "0")))
        except Exception:
            pass
        return None

    def _calculate_gain(self, current_price):
        """Calculate gain percentage."""
        if self.direction == "BUY":
            return (current_price - self.avg_entry) / self.avg_entry
        else:
            return (self.avg_entry - current_price) / self.avg_entry

    async def _activate_trailing(self, current_price):
        """Activate trailing stop at +6.1%."""
        try:
            # Calculate initial trailing SL (2.5% band from current price)
            if self.direction == "BUY":
                trailing_sl = current_price * Decimal("0.975")  # 2.5% below current
            else:
                trailing_sl = current_price * Decimal("1.025")  # 2.5% above current
            
            # Quantize and place trailing SL
            sl_q = await q_price(CATEGORY, self.symbol, trailing_sl)
            size_q = await q_qty(CATEGORY, self.symbol, self.position_size)
            
            # Cancel existing SL and place trailing SL
            await self.bybit.cancel_all(CATEGORY, self.symbol)
            
            exit_side = "Sell" if self.direction == "BUY" else "Buy"
            await self.bybit.sl_market_reduceonly_mark(
                CATEGORY, self.symbol, exit_side, str(size_q), str(sl_q),
                f"{self.trade_id}-SL-TRAIL"
            )
            
            self.highest_price = current_price
            
            await send_message(
                f"⛳ Trailing stop activated at +6.1% for {self.symbol} (SL: {sl_q}) • Source: {self.channel_name}"
            )
            
        except Exception as e:
            print(f"❌ Failed to activate trailing stop for {self.symbol}: {e}")

    async def _update_trailing_stop(self, current_price):
        """Update trailing stop with 2.5% band."""
        try:
            # Update highest price for long positions
            if self.direction == "BUY" and current_price > self.highest_price:
                self.highest_price = current_price
                
                # Calculate new trailing SL (2.5% below highest)
                new_sl = self.highest_price * Decimal("0.975")
                sl_q = await q_price(CATEGORY, self.symbol, new_sl)
                size_q = await q_qty(CATEGORY, self.symbol, self.position_size)
                
                # Update SL
                await self.bybit.cancel_all(CATEGORY, self.symbol)
                
                exit_side = "Sell" if self.direction == "BUY" else "Buy"
                await self.bybit.sl_market_reduceonly_mark(
                    CATEGORY, self.symbol, exit_side, str(size_q), str(sl_q),
                    f"{self.trade_id}-SL-TRAIL"
                )
                
                print(f"⛳ Trailing stop updated for {self.symbol}: {sl_q}")
            
            # Update lowest price for short positions
            elif self.direction == "SELL" and current_price < self.highest_price:
                self.highest_price = current_price
                
                # Calculate new trailing SL (2.5% above lowest)
                new_sl = self.highest_price * Decimal("1.025")
                sl_q = await q_price(CATEGORY, self.symbol, new_sl)
                size_q = await q_qty(CATEGORY, self.symbol, self.position_size)
                
                # Update SL
                await self.bybit.cancel_all(CATEGORY, self.symbol)
                
                exit_side = "Sell" if self.direction == "BUY" else "Buy"
                await self.bybit.sl_market_reduceonly_mark(
                    CATEGORY, self.symbol, exit_side, str(size_q), str(sl_q),
                    f"{self.trade_id}-SL-TRAIL"
                )
                
                print(f"⛳ Trailing stop updated for {self.symbol}: {sl_q}")
                
        except Exception as e:
            print(f"❌ Failed to update trailing stop for {self.symbol}: {e}")