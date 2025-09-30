"""Hedge and Re-entry Manager with -2% trigger and up to 3 re-entries."""

import asyncio
from decimal import Decimal
from app.bybit.client import BybitClient
from app.core.precision import q_price, q_qty, ensure_min_notional
from app.telegram.output import send_message
from app.config.settings import CATEGORY

class HedgeReentryManager:
    """Manages hedging and re-entries with -2% trigger."""
    
    def __init__(self, trade_id, symbol, direction, avg_entry, position_size, leverage, channel_name):
        self.trade_id = trade_id
        self.symbol = symbol
        self.direction = direction
        self.avg_entry = Decimal(str(avg_entry))
        self.position_size = Decimal(str(position_size))
        self.leverage = leverage
        self.channel_name = channel_name
        self.bybit = BybitClient()
        self._running = False
        self.reentry_count = 0
        self.max_reentries = 3

    async def run(self):
        """Run hedge and re-entry monitoring."""
        self._running = True
        print(f"🔄 Hedge/Re-entry Manager started for {self.symbol}")
        
        while self._running and self.reentry_count < self.max_reentries:
            try:
                # Get current mark price
                mark_price = await self._get_mark_price()
                if not mark_price:
                    await asyncio.sleep(3)
                    continue
                
                # Check if we should hedge (-2% adverse move)
                drawdown = self._calculate_drawdown(mark_price)
                if drawdown >= Decimal("0.02"):  # -2%
                    await self._execute_hedge(mark_price)
                    self.reentry_count += 1
                    
            except Exception as e:
                print(f"❌ Hedge/Re-entry error for {self.symbol}: {e}")
            
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

    def _calculate_drawdown(self, current_price):
        """Calculate drawdown percentage."""
        if self.direction == "BUY":
            return (self.avg_entry - current_price) / self.avg_entry
        else:
            return (current_price - self.avg_entry) / self.avg_entry

    async def _execute_hedge(self, current_price):
        """Execute hedge flip at -2% drawdown."""
        try:
            # Calculate hedge size (100% of original position)
            hedge_size = self.position_size
            
            # Determine hedge direction (opposite of original)
            hedge_direction = "SELL" if self.direction == "BUY" else "BUY"
            hedge_side = "Sell" if hedge_direction == "BUY" else "Buy"
            enter_side = "Buy" if hedge_direction == "BUY" else "Sell"
            
            # Quantize hedge size
            hedge_size_q = await q_qty(CATEGORY, self.symbol, hedge_size)
            hedge_size_q = await ensure_min_notional(CATEGORY, self.symbol, current_price, hedge_size_q)
            
            # Place hedge entry order
            price_q = await q_price(CATEGORY, self.symbol, current_price)
            await self.bybit.entry_limit_postonly(
                CATEGORY, self.symbol, enter_side, str(hedge_size_q), str(price_q),
                f"{self.trade_id}-HEDGE-{self.reentry_count + 1}"
            )
            
            # Place hedge SL (at original entry price)
            sl_q = await q_price(CATEGORY, self.symbol, self.avg_entry)
            await self.bybit.sl_market_reduceonly_mark(
                CATEGORY, self.symbol, hedge_side, str(hedge_size_q), str(sl_q),
                f"{self.trade_id}-HEDGE-SL-{self.reentry_count + 1}"
            )
            
            # Update position tracking
            self.direction = hedge_direction
            self.avg_entry = current_price
            self.position_size = hedge_size_q
            
            await send_message(
                f"♻️ Hedge flip #{self.reentry_count + 1} executed for {self.symbol} "
                f"({self.direction} @ {price_q}) • Source: {self.channel_name}"
            )
            
        except Exception as e:
            print(f"❌ Failed to execute hedge for {self.symbol}: {e}")

    async def stop(self):
        """Stop the hedge manager."""
        self._running = False