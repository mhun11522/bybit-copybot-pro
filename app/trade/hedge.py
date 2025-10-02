import asyncio
from decimal import Decimal
from app.bybit.client import BybitClient
from app.core.precision import q_qty
from app.trade.metrics import pnl_pct
from app.config.settings import CATEGORY, HEDGE_TRIGGER_PCT, HEDGE_MAX_RENTRIES, REENTRY_DELAY_SECONDS
from app.telegram.output import send_message

class HedgeReentryManager:
    def __init__(self, trade_id, symbol, direction, avg_entry, position_size, leverage, channel_name):
        self.trade_id=trade_id
        self.symbol=symbol
        self.direction=direction.upper()
        self.avg_entry=Decimal(str(avg_entry))
        self.pos_size=Decimal(str(position_size))
        self.leverage=int(leverage)
        self.channel_name=channel_name
        self.bybit=BybitClient()
        self._hedge_count=0
        self._running=False

    async def _mark(self) -> Decimal:
        pos = await self.bybit.positions(CATEGORY, self.symbol)
        try: return Decimal(str(pos["result"]["list"][0]["markPrice"]))
        except Exception: return self.avg_entry

    async def _flip(self, mark: Decimal):
        if self._hedge_count >= HEDGE_MAX_RENTRIES:
            return
        old_dir = self.direction
        new_dir = "SELL" if old_dir=="BUY" else "BUY"
        side_exit = "Sell" if old_dir=="BUY" else "Buy"
        side_enter = "Sell" if new_dir=="SELL" else "Buy"

        qty = await q_qty(CATEGORY, self.symbol, self.pos_size)

        # Close current (market reduce-only)
        await self.bybit.place_order({
            "category": CATEGORY, "symbol": self.symbol,
            "side": side_exit, "orderType":"Market", "qty": str(qty),
            "reduceOnly": True, "positionIdx": 0, "orderLinkId": f"{self.trade_id}-HEDGE-CLOSE-{self._hedge_count+1}"
        })
        # Reverse: open opposite 100% size
        await self.bybit.place_order({
            "category": CATEGORY, "symbol": self.symbol,
            "side": side_enter, "orderType":"Market", "qty": str(qty),
            "reduceOnly": False, "positionIdx": 0, "orderLinkId": f"{self.trade_id}-MKT"
        })

        self.direction = new_dir
        self._hedge_count += 1
        await send_message(f"🛡️ HEDGE #{self._hedge_count}: {self.symbol} {old_dir}→{new_dir} @ {mark} • Source: {self.channel_name}")

    async def run(self):
        self._running=True
        while self._running and self._hedge_count < HEDGE_MAX_RENTRIES:
            try:
                mark = await self._mark()
                gain = pnl_pct(self.direction, self.avg_entry, mark)
                if gain <= Decimal(str(HEDGE_TRIGGER_PCT)):
                    await self._flip(mark)
                    await asyncio.sleep(REENTRY_DELAY_SECONDS)
            except Exception:
                pass
            await asyncio.sleep(1)
