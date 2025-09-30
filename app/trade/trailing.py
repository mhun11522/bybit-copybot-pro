import asyncio
from decimal import Decimal
from app.bybit.client import BybitClient
from app.core.precision import q_price, q_qty
from app.telegram import output

CATEGORY="linear"
TRIGGER_PCT=Decimal("0.061")  # +6.1%

class TrailingStopManager:
    def __init__(self, trade_id, symbol, direction, avg_entry, position_size, channel_name):
        self.trade_id=trade_id; self.symbol=symbol; self.direction=direction
        self.avg_entry=Decimal(str(avg_entry)); self.pos_size=Decimal(str(position_size))
        self.channel_name=channel_name; self.bybit=BybitClient(); self._running=False

    async def _mark_price(self):
        pos = await self.bybit.positions(CATEGORY, self.symbol)
        try: return Decimal(str(pos["result"]["list"][0]["markPrice"]))
        except Exception: return self.avg_entry

    async def run(self):
        self._running=True
        side_exit = "Sell" if self.direction=="BUY" else "Buy"
        while self._running:
            try:
                mp = await self._mark_price()
                if self.direction=="BUY":
                    gain = (mp - self.avg_entry)/self.avg_entry
                    if gain >= TRIGGER_PCT:
                        new_sl = await q_price(CATEGORY, self.symbol, self.avg_entry*Decimal("1.00000015"))
                        qty = await q_qty(CATEGORY, self.symbol, self.pos_size)
                        await self.bybit.sl_market_reduceonly_mark(CATEGORY, self.symbol, side_exit, str(qty), str(new_sl), f"{self.trade_id}-SL")
                        await output.send_message(f"⛳ Trailing moved SL to ~BE for {self.symbol} • Source: {self.channel_name}")
                        self._running=False; break
                else:
                    gain = (self.avg_entry - mp)/self.avg_entry
                    if gain >= TRIGGER_PCT:
                        new_sl = await q_price(CATEGORY, self.symbol, self.avg_entry*Decimal("0.99999985"))
                        qty = await q_qty(CATEGORY, self.symbol, self.pos_size)
                        await self.bybit.sl_market_reduceonly_mark(CATEGORY, self.symbol, side_exit, str(qty), str(new_sl), f"{self.trade_id}-SL")
                        await output.send_message(f"⛳ Trailing moved SL to ~BE for {self.symbol} • Source: {self.channel_name}")
                        self._running=False; break
            except Exception:
                pass
            await asyncio.sleep(3)