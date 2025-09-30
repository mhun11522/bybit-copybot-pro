import asyncio
from decimal import Decimal
from app.bybit.client import BybitClient
from app.core.precision import q_price, q_qty
from app.telegram import output, templates

CATEGORY="linear"
TRIGGER_PCT=Decimal("0.061")  # +6.1%
TRAIL_DISTANCE=Decimal("0.025")  # 2.5%

class TrailingStopManager:
    def __init__(self, trade_id, symbol, direction, avg_entry, position_size, channel_name):
        self.trade_id=trade_id; self.symbol=symbol; self.direction=direction
        self.avg_entry=Decimal(str(avg_entry)); self.pos_size=Decimal(str(position_size))
        self.channel_name=channel_name; self.bybit=BybitClient(); self._running=False
        self._activated=False
        self._high_watermark = self.avg_entry if direction == "BUY" else self.avg_entry
        self._low_watermark = self.avg_entry if direction == "SELL" else self.avg_entry

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
                    # Update high watermark
                    if mp > self._high_watermark:
                        self._high_watermark = mp
                    
                    gain = (mp - self.avg_entry)/self.avg_entry
                    
                    # Activate trailing at +6.1%
                    if not self._activated and gain >= TRIGGER_PCT:
                        self._activated = True
                        new_sl = await q_price(CATEGORY, self.symbol, self.avg_entry*Decimal("1.00000015"))
                        qty = await q_qty(CATEGORY, self.symbol, self.pos_size)
                        await self.bybit.sl_market_reduceonly_mark(CATEGORY, self.symbol, side_exit, str(qty), str(new_sl), f"{self.trade_id}-SL")
                        await output.send_message(templates.trailing_moved(self.symbol, new_sl, self.channel_name))
                    
                    # Continue trailing with 2.5% distance
                    elif self._activated:
                        target_sl = self._high_watermark * (Decimal("1") - TRAIL_DISTANCE)
                        current_sl = await self._get_current_sl()
                        if current_sl and target_sl > current_sl:
                            new_sl = await q_price(CATEGORY, self.symbol, target_sl)
                            qty = await q_qty(CATEGORY, self.symbol, self.pos_size)
                            await self.bybit.sl_market_reduceonly_mark(CATEGORY, self.symbol, side_exit, str(qty), str(new_sl), f"{self.trade_id}-SL")
                            await output.send_message(templates.trailing_moved(self.symbol, new_sl, self.channel_name))
                
                else:  # SELL
                    # Update low watermark
                    if mp < self._low_watermark:
                        self._low_watermark = mp
                    
                    gain = (self.avg_entry - mp)/self.avg_entry
                    
                    # Activate trailing at +6.1%
                    if not self._activated and gain >= TRIGGER_PCT:
                        self._activated = True
                        new_sl = await q_price(CATEGORY, self.symbol, self.avg_entry*Decimal("0.99999985"))
                        qty = await q_qty(CATEGORY, self.symbol, self.pos_size)
                        await self.bybit.sl_market_reduceonly_mark(CATEGORY, self.symbol, side_exit, str(qty), str(new_sl), f"{self.trade_id}-SL")
                        await output.send_message(templates.trailing_moved(self.symbol, new_sl, self.channel_name))
                    
                    # Continue trailing with 2.5% distance
                    elif self._activated:
                        target_sl = self._low_watermark * (Decimal("1") + TRAIL_DISTANCE)
                        current_sl = await self._get_current_sl()
                        if current_sl and target_sl < current_sl:
                            new_sl = await q_price(CATEGORY, self.symbol, target_sl)
                            qty = await q_qty(CATEGORY, self.symbol, self.pos_size)
                            await self.bybit.sl_market_reduceonly_mark(CATEGORY, self.symbol, side_exit, str(qty), str(new_sl), f"{self.trade_id}-SL")
                            await output.send_message(f"⛳ Trailing moved SL to {new_sl} (2.5% above LWM {self._low_watermark}) • Source: {self.channel_name}")
                            
            except Exception:
                pass
            await asyncio.sleep(3)

    async def _get_current_sl(self):
        """Get current stop loss price from open orders."""
        try:
            orders = await self.bybit.query_open(CATEGORY, self.symbol)
            for order in orders.get("result", {}).get("list", []):
                if order.get("orderLinkId", "").endswith("-SL"):
                    return Decimal(str(order.get("stopLoss", "0")))
        except Exception:
            pass
        return None