import asyncio
from decimal import Decimal
from app.bybit.client import BybitClient
from app.core.precision import q_price, q_qty
from app.trade.metrics import pnl_pct
from app.config.settings import CATEGORY, TRAIL_TRIGGER_PCT, TRAIL_DISTANCE_PCT, TRAIL_POLL_SECONDS
from app.telegram.output import send_message

class TrailingStopManager:
    def __init__(self, trade_id, symbol, direction, avg_entry, position_size, channel_name):
        self.trade_id=trade_id
        self.symbol=symbol
        self.direction=direction.upper()  # BUY/SELL
        self.avg_entry=Decimal(str(avg_entry))
        self.pos_size=Decimal(str(position_size))
        self.channel_name=channel_name
        self.bybit=BybitClient()
        self._armed=False
        self._hwm=None
        self._lwm=None
        self._running=False

    async def _mark(self) -> Decimal:
        pos = await self.bybit.positions(CATEGORY, self.symbol)
        try:
            return Decimal(str(pos["result"]["list"][0]["markPrice"]))
        except Exception:
            return self.avg_entry

    async def _move_sl(self, new_sl: Decimal):
        side_exit = "Sell" if self.direction=="BUY" else "Buy"
        qty = await q_qty(CATEGORY, self.symbol, self.pos_size)
        new_sl_q = await q_price(CATEGORY, self.symbol, new_sl)
        await self.bybit.sl_market_reduceonly_mark(CATEGORY, self.symbol, side_exit, str(qty), str(new_sl_q), f"{self.trade_id}-SL")
        await send_message(f"🔄 Trailing stop moved: {self.symbol} → SL={new_sl_q} • Source: {self.channel_name}")

    async def run(self):
        self._running=True
        dist = Decimal(f"{TRAIL_DISTANCE_PCT}")/Decimal("100")
        trigger = Decimal(f"{TRAIL_TRIGGER_PCT}")
        while self._running:
            try:
                mark = await self._mark()
                gain = pnl_pct(self.direction, self.avg_entry, mark)
                if not self._armed and gain >= trigger:
                    self._armed=True
                    # initial ~B/E
                    await self._move_sl(self.avg_entry)

                if self._armed:
                    if self.direction=="BUY":
                        # ratchet high-watermark
                        if self._hwm is None or mark > self._hwm:
                            self._hwm = mark
                            target = self._hwm * (Decimal("1") - dist)
                            if target > self.avg_entry:
                                await self._move_sl(target)
                    else:
                        if self._lwm is None or mark < self._lwm:
                            self._lwm = mark
                            target = self._lwm * (Decimal("1") + dist)
                            if target < self.avg_entry:
                                await self._move_sl(target)
            except Exception:
                pass
            await asyncio.sleep(TRAIL_POLL_SECONDS)
