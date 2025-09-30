"""Pyramid Manager with IM steps and thresholds."""

import asyncio
from decimal import Decimal
from app.bybit.client import BybitClient
from app.core.precision import q_price, q_qty, ensure_min_notional
from app.trade.risk import qty_for_im_step
from app.telegram.output import send_message
from app.config.settings import CATEGORY

class PyramidManager:
    """Manages pyramid adds with IM steps and thresholds."""
    
    def __init__(self, trade_id, symbol, direction, leverage, channel_name, planned_entries=None):
        self.trade_id = trade_id
        self.symbol = symbol
        self.direction = direction
        self.leverage = leverage
        self.channel_name = channel_name
        self.planned_entries = planned_entries or []
        self.bybit = BybitClient()
        self._running = False
        self.add_count = 0
        self.max_adds = 100
        self.im_step = Decimal("20")  # 20 USDT per step

    async def run(self):
        """Run pyramid manager."""
        self._running = True
        print(f"🔄 Pyramid Manager started for {self.symbol}")
        
        # Execute planned entries first
        for entry_price in self.planned_entries:
            if not self._running:
                break
            try:
                await self._add_pyramid(entry_price)
                await asyncio.sleep(0.3)  # Small delay between adds
            except Exception as e:
                print(f"❌ Failed to add pyramid at {entry_price}: {e}")
        
        # Monitor for additional pyramid opportunities
        while self._running and self.add_count < self.max_adds:
            try:
                # Check if we should add more pyramids based on price movement
                # This is a simplified version - in practice, you'd check price thresholds
                await asyncio.sleep(10)  # Check every 10 seconds
            except Exception as e:
                print(f"❌ Pyramid monitoring error for {self.symbol}: {e}")

    async def _add_pyramid(self, entry_price):
        """Add pyramid position at specified price."""
        try:
            if self.add_count >= self.max_adds:
                await send_message(
                    f"⛔ Max pyramid adds reached ({self.max_adds}) for {self.symbol} • Source: {self.channel_name}"
                )
                return False
            
            # Calculate pyramid size based on IM step
            pyramid_size = await qty_for_im_step(CATEGORY, self.symbol, entry_price, self.leverage, self.im_step)
            pyramid_size = await ensure_min_notional(CATEGORY, self.symbol, entry_price, pyramid_size)
            
            # Quantize entry price
            price_q = await q_price(CATEGORY, self.symbol, entry_price)
            
            # Place pyramid entry order
            enter_side = "Buy" if self.direction == "BUY" else "Sell"
            await self.bybit.entry_limit_postonly(
                CATEGORY, self.symbol, enter_side, str(pyramid_size), str(price_q),
                f"{self.trade_id}-PY{self.add_count + 1}"
            )
            
            self.add_count += 1
            
            await send_message(
                f"➕ Pyramid add #{self.add_count} for {self.symbol}: {pyramid_size} @ {price_q} • Source: {self.channel_name}"
            )
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to add pyramid for {self.symbol}: {e}")
            return False

    async def add_at_price(self, price):
        """Add pyramid at current market price."""
        return await self._add_pyramid(price)

    async def stop(self):
        """Stop the pyramid manager."""
        self._running = False