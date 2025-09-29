import asyncio
from decimal import Decimal
from app.storage.db import save_fill, get_trade, update_trade_close


class OCOManager:
    def __init__(self, bybit_client, signal: dict, trade_id: str, fsm=None):
        self.bybit = bybit_client
        self.signal = signal
        self.trade_id = trade_id
        self.fsm = fsm

    async def monitor(self):
        symbol = self.signal["symbol"]
        for _ in range(20):  # ~1 min polling @ 3s
            orders = self.bybit.get_open_orders(symbol)
            print("🔍 Monitoring orders:", orders)

            if isinstance(orders, dict) and orders.get("retCode") == 0:
                order_list = orders.get("result", {}).get("list", [])
                tp_active = [o for o in order_list if "-TP" in (o.get("orderLinkId", "") or "")]
                sl_active = [o for o in order_list if "-SL" in (o.get("orderLinkId", "") or "")]

                if not sl_active and tp_active:
                    print("✅ TP filled, canceling SL + other TPs")
                    self.bybit.cancel_all(symbol)
                    try:
                        # Compute naive realized PnL from entry and the first TP price
                        trade_row = await get_trade(self.trade_id)
                        if trade_row:
                            _, _, direction, entry_price, size, *_ = trade_row
                            # Attempt to read target TP price from signal
                            tp_price = None
                            tps = self.signal.get("tps", [])
                            if tps:
                                tp_price = Decimal(str(tps[0]))
                            if tp_price is not None:
                                entry_d = Decimal(str(entry_price))
                                size_d = Decimal(str(size))
                                if (direction or "").upper() == "BUY":
                                    pnl = (tp_price - entry_d) * size_d
                                else:
                                    pnl = (entry_d - tp_price) * size_d
                                await save_fill(self.trade_id, order_id="", link_id=f"{self.trade_id}-TP*", side="TP", price=float(tp_price), qty=float(size_d), fee=0.0, pnl=float(pnl))
                                await update_trade_close(self.trade_id, float(pnl))
                                # If FSM provided, call its record_exit with richer data
                                if self.fsm:
                                    await self.fsm.record_exit({"orderId": "", "orderLinkId": f"{self.trade_id}-TP*", "side": "TP"}, float(tp_price), float(size_d), "TP")
                    except Exception:
                        pass
                    return "TP_HIT"

                if not tp_active and sl_active:
                    print("✅ SL triggered, canceling all TPs")
                    self.bybit.cancel_all(symbol)
                    try:
                        trade_row = await get_trade(self.trade_id)
                        if trade_row:
                            _, _, direction, entry_price, size, *_ = trade_row
                            sl_price = self.signal.get("sl")
                            if sl_price is not None:
                                sl_d = Decimal(str(sl_price))
                                entry_d = Decimal(str(entry_price))
                                size_d = Decimal(str(size))
                                if (direction or "").upper() == "BUY":
                                    pnl = (sl_d - entry_d) * size_d
                                else:
                                    pnl = (entry_d - sl_d) * size_d
                                await save_fill(self.trade_id, order_id="", link_id=f"{self.trade_id}-SL", side="SL", price=float(sl_d), qty=float(size_d), fee=0.0, pnl=float(pnl))
                                await update_trade_close(self.trade_id, float(pnl))
                                if self.fsm:
                                    await self.fsm.record_exit({"orderId": "", "orderLinkId": f"{self.trade_id}-SL", "side": "SL"}, float(sl_d), float(size_d), "SL")
                    except Exception:
                        pass
                    return "SL_HIT"

            await asyncio.sleep(3)

        print("⚠️ Timeout — no exit detected")
        return "TIMEOUT"