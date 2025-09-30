from __future__ import annotations
import asyncio
from decimal import Decimal
from app.bybit_client import BybitClient
from app.telegram.output import send_message
from app.telegram import templates
from app.core.precision import q_price
from app import settings


class TrailingStopManager:
    def __init__(self, bybit_client: BybitClient, trade_id: str, symbol: str, direction: str, 
                 sl_price, activation_pct: Decimal = None, distance_pct: Decimal = None):
        self.bybit = bybit_client
        self.trade_id = trade_id
        self.symbol = symbol
        self.direction = direction  # "BUY" or "SELL"
        self.initial_sl = Decimal(str(sl_price)) if sl_price is not None else None
        self.activation_pct = activation_pct or settings.TRAILING_ACTIVATION_PCT  # +6.1%
        self.distance_pct = distance_pct or settings.TRAILING_DISTANCE_PCT  # 2.5%
        self.active = False
        self.last_sl = self.initial_sl
        self.highest_price = None
        self.tps_cancelled = False

    async def monitor(self, entry_price: Decimal, qty: str):
        """Monitor for trailing stop opportunities."""
        side = "Sell" if self.direction == "BUY" else "Buy"
        print(f"📈 Starting trailing stop manager for {self.symbol}...")

        entry_d = Decimal(str(entry_price))
        self.highest_price = entry_d

        for _ in range(100):  # ~8 minutes depending on sleep
            try:
                ticker = await asyncio.to_thread(self.bybit.get_ticker, self.symbol) or {}
                last_price_str = ((ticker.get("result", {}).get("list") or [{}])[0].get("lastPrice"))
                if not last_price_str:
                    await asyncio.sleep(5)
                    continue
                last = Decimal(str(last_price_str))

                # Update highest price for trailing
                if self.direction == "BUY":
                    if self.highest_price is None or last > self.highest_price:
                        self.highest_price = last
                else:
                    if self.highest_price is None or last < self.highest_price:
                        self.highest_price = last

                # Calculate gain percentage relative to entry
                if self.direction == "BUY":
                    change = (last - entry_d) / entry_d
                else:
                    change = (entry_d - last) / entry_d

                # Check if trailing should be activated (+6.1%)
                if change >= self.activation_pct and not self.active:
                    await self._activate_trailing(last, side, qty)
                    self.active = True

                # If trailing is active, update SL based on highest price
                if self.active:
                    await self._update_trailing_sl(last, side, qty)

                await asyncio.sleep(5)
            except Exception as e:
                print("Trailing stop error:", e)
                await asyncio.sleep(5)

    async def _activate_trailing(self, current_price: Decimal, side: str, qty: str):
        """Activate trailing stop and cancel TPs."""
        print(f"🔄 Activating trailing stop for {self.symbol} at {current_price}")
        
        # Cancel all TP orders when trailing activates
        if not self.tps_cancelled:
            try:
                await asyncio.to_thread(self.bybit.cancel_all, self.symbol)
                self.tps_cancelled = True
                print(f"✅ Cancelled all orders for {self.symbol}")
            except Exception as e:
                print(f"Error cancelling orders: {e}")

        # Send activation message
        try:
            await send_message(templates.trailing_activated(
                self.symbol,
                self.direction,
                f"TRD-{self.symbol}",
                self.activation_pct,
                self.distance_pct,
                current_price
            ))
        except Exception as e:
            print(f"Trailing activation message error: {e}")

    async def _update_trailing_sl(self, current_price: Decimal, side: str, qty: str):
        """Update trailing stop loss based on highest price."""
        if self.highest_price is None:
            return

        # Calculate new SL based on distance behind highest price
        if self.direction == "BUY":
            new_sl_raw = self.highest_price * (Decimal("1") - self.distance_pct)
        else:
            new_sl_raw = self.highest_price * (Decimal("1") + self.distance_pct)

        new_sl = await q_price(self.symbol, new_sl_raw)

        # Only move SL in favorable direction
        should_move = False
        if self.direction == "BUY":
            if self.last_sl is None or new_sl > self.last_sl:
                should_move = True
        else:
            if self.last_sl is None or new_sl < self.last_sl:
                should_move = True

        if should_move:
            try:
                print(f"🔄 Moving trailing SL to {new_sl} (highest: {self.highest_price})")
                await asyncio.to_thread(
                    self.bybit.create_sl_order,
                    symbol=self.symbol,
                    side=side,
                    qty=qty,
                    trigger_price=str(new_sl),
                    trade_id=f"{self.trade_id}-TRL",
                )
                self.last_sl = new_sl
            except Exception as e:
                print(f"Trailing SL update error: {e}")


# Legacy function for backward compatibility
async def trailing_moved(symbol: str, price: str) -> str:
    """Legacy trailing moved message."""
    return f"""🔄 TRAILING STOP FLYTTAD
📊 Symbol: {symbol}
📍 Pris: {price}

🔄 TRAILING STOP MOVED
📊 Symbol: {symbol}
�� Price: {price}""" 