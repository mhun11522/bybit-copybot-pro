import asyncio
from decimal import Decimal
from app.bybit.client import BybitClient
from app.core.precision import q_qty
from app.config.settings import CATEGORY, PYR_LEVELS, PYR_CHECK_INTERVAL, PYR_MAX_ADDS
from app.trade.metrics import pnl_pct
from app.telegram.output import send_message

class PyramidManager:
    def __init__(self, trade_id, symbol, direction, avg_entry, position_size, leverage, channel_name):
        self.trade_id=trade_id
        self.symbol=symbol
        self.direction=direction.upper()
        self.avg_entry=Decimal(str(avg_entry))
        self.pos_size=Decimal(str(position_size))
        self.leverage=int(leverage)
        self.channel_name=channel_name
        self.bybit=BybitClient()
        self._executed = set()
        self._adds = 0
        self._running=False

    async def _mark(self) -> Decimal:
        pos = await self.bybit.positions(CATEGORY, self.symbol)
        try: return Decimal(str(pos["result"]["list"][0]["markPrice"]))
        except Exception: return self.avg_entry

    async def _add_im_to(self, target_im: int):
        """
        Add contracts to reach ~target initial margin (USDT).
        IM ≈ (qty * price) / lev  => qty_add = (target_im - current_im)*lev / price
        """
        pos = await self.bybit.positions(CATEGORY, self.symbol)
        try:
            row = pos["result"]["list"][0]
            mark = Decimal(str(row["markPrice"]))
            size = Decimal(str(row["size"]))
        except Exception:
            return

        current_im = (size * mark) / Decimal(str(self.leverage))
        target = Decimal(str(target_im))
        if current_im >= target:
            return
        miss = target - current_im
        qty_add = (miss * Decimal(str(self.leverage))) / mark
        qty_add_q = await q_qty(CATEGORY, self.symbol, qty_add)
        if qty_add_q <= 0:
            return

        side_enter = "Buy" if self.direction=="BUY" else "Sell"
        await self.bybit.place_order({
            "category": CATEGORY, "symbol": self.symbol,
            "side": side_enter, "orderType":"Market", "qty": str(qty_add_q),
            "reduceOnly": False, "positionIdx": 0, "orderLinkId": f"{self.trade_id}-PYR-{self._adds+1}"
        })
        self._adds += 1
        await send_message(f"📈 PYRAMID #{self._adds}: {self.symbol} +{qty_add_q} @ {mark} → IM={int(target)} USDT • Source: {self.channel_name}")

    async def _max_leverage(self, target_lev: int):
        await self.bybit.set_leverage(CATEGORY, self.symbol, target_lev, target_lev)
        self.leverage = target_lev

    async def run(self):
        self._running=True
        while self._running and self._adds < PYR_MAX_ADDS:
            try:
                mark = await self._mark()
                gain = pnl_pct(self.direction, self.avg_entry, mark)

                for lvl in PYR_LEVELS:
                    trig = Decimal(str(lvl["trigger"]))
                    if gain >= trig and (lvl["trigger"] not in self._executed):
                        action = lvl["action"]
                        if action == "check_im":
                            await self._add_im_to(lvl["target_im"])
                        elif action == "sl_to_be":
                            # BE handled by TP2_BE manager
                            pass
                        elif action == "max_leverage":
                            await self._max_leverage(lvl["target_lev"])
                        elif action == "add_im":
                            await self._add_im_to(lvl["target_im"])
                        self._executed.add(lvl["trigger"])
            except Exception:
                pass
            await asyncio.sleep(PYR_CHECK_INTERVAL)
