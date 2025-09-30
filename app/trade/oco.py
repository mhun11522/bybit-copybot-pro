import asyncio
from app.bybit.client import BybitClient
from app.telegram import templates, output

CATEGORY = "linear"

class OCOManager:
    def __init__(self, trade_id, symbol, direction, channel_name):
        self.trade_id=trade_id; self.symbol=symbol; self.direction=direction; self.channel_name=channel_name
        self.bybit=BybitClient(); self._running=False

    async def run(self):
        self._running=True
        while self._running:
            try:
                orders = await self.bybit.query_open(CATEGORY, self.symbol)
                open_ids = [o.get("orderLinkId","") for o in orders.get("result",{}).get("list",[]) if o.get("orderLinkId")]
                tp_open = any(x.endswith(("TP1","TP2","TP3","TP4")) for x in open_ids)
                sl_open = any(x.endswith(("SL",)) for x in open_ids)

                if not tp_open and sl_open:
                    await self.bybit.cancel_all(CATEGORY, self.symbol)
                    await output.send_message(templates.tp_hit(self.symbol, "?", "filled", self.channel_name))
                    self._running=False; break

                if tp_open and not sl_open:
                    await self.bybit.cancel_all(CATEGORY, self.symbol)
                    await output.send_message(templates.sl_hit(self.symbol, "triggered", self.channel_name))
                    self._running=False; break
            except Exception:
                pass
            await asyncio.sleep(2)