import asyncio
from decimal import Decimal
from app.bybit.client import BybitClient
from app.telegram import templates, output

CATEGORY = "linear"

class OCOManager:
    def __init__(self, trade_id, symbol, direction, channel_name):
        self.trade_id=trade_id; self.symbol=symbol; self.direction=direction; self.channel_name=channel_name
        self.bybit=BybitClient(); self._running=False

    async def _check_position_closed(self):
        """Check if position is closed by querying positions."""
        try:
            pos = await self.bybit.positions(CATEGORY, self.symbol)
            if pos.get("result", {}).get("list"):
                size = Decimal(str(pos["result"]["list"][0].get("size", "0")))
                return size <= 0
            return True
        except Exception:
            return False

    async def _check_tp_filled(self):
        """Check if any TP was filled by examining order history."""
        try:
            orders = await self.bybit.query_open(CATEGORY, self.symbol)
            open_ids = [o.get("orderLinkId","") for o in orders.get("result",{}).get("list",[]) if o.get("orderLinkId")]
            tp_open = any(x.endswith(("TP1","TP2","TP3","TP4")) for x in open_ids)
            sl_open = any(x.endswith(("SL",)) for x in open_ids)
            return not tp_open and sl_open, tp_open and not sl_open
        except Exception:
            return False, False

    async def run(self):
        self._running=True
        while self._running:
            try:
                # Check if position is closed first
                if await self._check_position_closed():
                    await self.bybit.cancel_all(CATEGORY, self.symbol)
                    await output.send_message(templates.tp_hit(self.symbol, "?", "position closed", self.channel_name))
                    self._running=False; break

                # Check for TP/SL fills
                tp_filled, sl_filled = await self._check_tp_filled()
                
                if tp_filled:
                    await self.bybit.cancel_all(CATEGORY, self.symbol)
                    await output.send_message(templates.tp_hit(self.symbol, "?", "filled", self.channel_name))
                    self._running=False; break

                if sl_filled:
                    await self.bybit.cancel_all(CATEGORY, self.symbol)
                    await output.send_message(templates.sl_hit(self.symbol, "triggered", self.channel_name))
                    self._running=False; break
                    
            except Exception as e:
                print(f"OCO error: {e}")
            await asyncio.sleep(2)