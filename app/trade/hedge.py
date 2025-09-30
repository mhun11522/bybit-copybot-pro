import asyncio
from decimal import Decimal
from app.bybit.client import BybitClient
from app.core.precision import q_price, q_qty, ensure_min_notional
from app.telegram import output

CATEGORY="linear"
ADVERSE_PCT=Decimal("0.02")
MAX_REENTRIES=3

class HedgeReentryManager:
    def __init__(self, trade_id, symbol, direction, avg_entry, position_size, leverage, channel_name):
        self.trade_id=trade_id; self.symbol=symbol; self.direction=direction
        self.avg_entry=Decimal(str(avg_entry)); self.pos_size=Decimal(str(position_size))
        self.leverage=leverage; self.channel_name=channel_name
        self.bybit=BybitClient(); self._running=False; self._re=0

    async def _mark_price(self):
        pos = await self.bybit.positions(CATEGORY, self.symbol)
        try: return Decimal(str(pos["result"]["list"][0]["markPrice"]))
        except Exception: return self.avg_entry

    async def run(self):
        self._running=True
        while self._running and self._re < MAX_REENTRIES:
            try:
                mp = await self._mark_price()
                draw = (self.avg_entry - mp)/self.avg_entry if self.direction=="BUY" else (mp - self.avg_entry)/self.avg_entry
                if draw >= ADVERSE_PCT:
                    self._re += 1
                    new_dir = "SELL" if self.direction=="BUY" else "BUY"
                    side_exit = "Sell" if self.direction=="BUY" else "Buy"
                    side_enter = "Buy" if new_dir=="BUY" else "Sell"

                    qty = await q_qty(CATEGORY, self.symbol, self.pos_size)
                    sl = await q_price(CATEGORY, self.symbol, mp)
                    await self.bybit.sl_market_reduceonly_mark(CATEGORY, self.symbol, side_exit, str(qty), str(sl), f"{self.trade_id}-HEDGE-SL-{self._re}")

                    enter_price = await q_price(CATEGORY, self.symbol, mp)
                    qty2 = await ensure_min_notional(CATEGORY, self.symbol, enter_price, qty)
                    await self.bybit.entry_limit_postonly(CATEGORY, self.symbol, side_enter, str(qty2), str(enter_price), f"{self.trade_id}-HEDGE-E{self._re}")
                    await output.send_message(f"♻️ Hedge flip {self._re} on {self.symbol} ({self.direction}→{new_dir}) • Source: {self.channel_name}")
                    self.direction = new_dir; self.avg_entry = enter_price
            except Exception:
                pass
            await asyncio.sleep(3)