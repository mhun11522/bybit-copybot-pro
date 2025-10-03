import asyncio
from decimal import Decimal
from app.bybit.client import BybitClient
from app.core.precision import q_price, q_qty
from app.trade.metrics import pnl_pct
from app.config.settings import CATEGORY, TRAIL_TRIGGER_PCT, TRAIL_DISTANCE_PCT, TRAIL_POLL_SECONDS
from app.telegram.output import send_message

class TrailingStopManager:
    def __init__(self, trade_id, symbol, direction, original_entry, avg_entry, position_size, channel_name):
        self.trade_id=trade_id
        self.symbol=symbol
        self.direction=direction.upper()  # BUY/SELL
        self.original_entry=Decimal(str(original_entry))  # CRITICAL: Use original entry for gain calculation
        self.avg_entry=Decimal(str(avg_entry))  # Current average entry
        self.pos_size=Decimal(str(position_size))
        self.channel_name=channel_name
        self.bybit=BybitClient()
        self._armed=False
        self._hwm=None
        self._lwm=None
        self._running=False
        self._tps_cancelled=False  # Track if TPs below 6.1% have been cancelled

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

    async def _cancel_tps_below_6_1_percent(self):
        """Cancel all TPs below 6.1% when trailing stop activates."""
        try:
            # Get all open orders
            orders = await self.bybit.get_open_orders(CATEGORY, self.symbol)
            if orders.get('retCode') == 0:
                for order in orders.get('result', {}).get('list', []):
                    order_type = order.get('orderType', '')
                    if order_type == 'Limit' and not order.get('reduceOnly', False):
                        # This is a TP order (not SL)
                        order_id = order.get('orderId', '')
                        if order_id:
                            await self.bybit.cancel_order(CATEGORY, self.symbol, order_id)
                            await send_message(f"🔄 Trailing activated: Cancelled TP below 6.1% for {self.symbol} • Source: {self.channel_name}")
        except Exception as e:
            print(f"Error cancelling TPs: {e}")

    async def run(self):
        self._running=True
        dist = Decimal("0.025")  # 2.5% behind price as per client spec
        trigger = Decimal("6.1")  # 6.1% trigger as per client spec
        while self._running:
            try:
                mark = await self._mark()
                # CRITICAL: Use original entry for gain calculation, not average entry
                gain = pnl_pct(self.direction, self.original_entry, mark)
                
                if not self._armed and gain >= trigger:
                    self._armed=True
                    # Cancel all TPs below 6.1% when trailing starts
                    if not self._tps_cancelled:
                        await self._cancel_tps_below_6_1_percent()
                        self._tps_cancelled=True
                    
                    # Set initial trailing SL at 2.5% behind current price
                    if self.direction == "BUY":
                        initial_sl = mark * (Decimal("1") - dist)
                    else:
                        initial_sl = mark * (Decimal("1") + dist)
                    await self._move_sl(initial_sl)
                    await send_message(f"🔄 TRAILING STOP AKTIVERAD: {self.symbol} at +{gain:.1f}% • Source: {self.channel_name}")

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
