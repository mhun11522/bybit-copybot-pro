import asyncio
from decimal import Decimal
from app.bybit.client import BybitClient
from app.core.precision import q_price, q_qty
from app.config.settings import CATEGORY, REENTRY_DELAY_SECONDS, HEDGE_MAX_RENTRIES
from app.telegram.output import send_message

class ReEntryManager:
    """
    When SL is hit and the position closes, attempt up to 3 re-entries following the last signal logic.
    """
    def __init__(self, trade_id, symbol, direction, entries, leverage, channel_name):
        self.trade_id=trade_id
        self.symbol=symbol
        self.direction=direction.upper()
        self.entries=[Decimal(str(x)) for x in entries]
        self.leverage=int(leverage)
        self.channel_name=channel_name
        self.bybit=BybitClient()
        self._attempts=0

    async def attempt(self):
        if self._attempts >= HEDGE_MAX_RENTRIES:
            return False
        side = "Buy" if self.direction=="BUY" else "Sell"
        # Use E1 (or market) on re-entry for simplicity
        price = await q_price(CATEGORY, self.symbol, self.entries[0])
        # A small qty based on your IM rule would be ideal
        await self.bybit.place_order({
            "category": CATEGORY, "symbol": self.symbol,
            "side": side, "orderType":"Market", "qty": "1",
            "reduceOnly": False, "positionIdx": 0, "orderLinkId": f"{self.trade_id}-RE-{self._attempts+1}"
        })
        self._attempts += 1
        await send_message(f"🔁 Re-entry {self._attempts} attempted for {self.symbol} • Source: {self.channel_name}")
        return True

    async def run(self):
        # Wait, then attempt re-entries up to 3 times
        for _ in range(HEDGE_MAX_RENTRIES):
            await asyncio.sleep(REENTRY_DELAY_SECONDS)
            ok = await self.attempt()
            if not ok:
                break
