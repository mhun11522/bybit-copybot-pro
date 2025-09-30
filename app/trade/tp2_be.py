import asyncio
from decimal import Decimal
from app.bybit.client import BybitClient
from app.core.precision import q_price
from app.telegram import output

CATEGORY = "linear"
OFFSET = Decimal("0.000015")  # 0.0015%

class TP2BreakEvenManager:
    """
    Watch TP2. When TP2 disappears from open orders (implying it's filled),
    push SL to B/E + 0.0015% (BUY) or B/E - 0.0015% (SELL), ACK before notify.
    """
    def __init__(self, trade_id: str, symbol: str, direction: str, avg_entry, channel_name: str):
        self.trade_id = trade_id
        self.symbol = symbol
        self.direction = direction  # "BUY"/"SELL"
        self.avg_entry = Decimal(str(avg_entry))
        self.channel_name = channel_name
        self.bybit = BybitClient()
        self._running = False
        self._done = False

    async def _tp2_open(self) -> bool:
        try:
            orders = await self.bybit.query_open(CATEGORY, self.symbol)
            open_ids = [o.get("orderLinkId","") for o in orders.get("result",{}).get("list",[])]
            return any(x.endswith("-TP2") for x in open_ids if x)
        except Exception:
            return True  # don't trigger prematurely

    async def _be_price(self) -> Decimal:
        if self.direction == "BUY":
            return self.avg_entry * (Decimal("1") + OFFSET)
        else:
            return self.avg_entry * (Decimal("1") - OFFSET)

    async def run(self):
        self._running = True
        while self._running and not self._done:
            try:
                still_open = await self._tp2_open()
                if not still_open:
                    # TP2 considered filled -> set SL to B/E +/- offset
                    be_raw = await self._be_price()
                    be_q = await q_price(CATEGORY, self.symbol, be_raw)
                    # Amend trading stop (ACK-gated)
                    await self.bybit.set_trading_stop(CATEGORY, self.symbol, be_q, sl_order_type="Market", sl_trigger_by="MarkPrice")
                    await output.send_message(
                        f"🧷 TP2 hit → SL moved to B/E±0.0015% @ {be_q} for {self.symbol} • Source: {self.channel_name}"
                    )
                    self._done = True
                    break
            except Exception:
                pass
            await asyncio.sleep(2)
        self._running = False

    def stop(self):
        self._running = False