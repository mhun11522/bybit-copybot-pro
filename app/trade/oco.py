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
                    # Delegate recording and messaging to FSM only to avoid duplication
                    try:
                        if self.fsm:
                            trade_row = await get_trade(self.trade_id)
                            if trade_row:
                                _, _, _, _, size, *_ = trade_row
                                tps = self.signal.get("tps", [])
                                if tps:
                                    tp_price = Decimal(str(tps[0]))
                                    await self.fsm.record_exit({"orderId": "", "orderLinkId": f"{self.trade_id}-TP*", "side": "TP"}, float(tp_price), float(size), "TP")
                    except Exception:
                        pass
                    return "TP_HIT"

                if not tp_active and sl_active:
                    print("✅ SL triggered, canceling all TPs")
                    self.bybit.cancel_all(symbol)
                    try:
                        if self.fsm and self.signal.get("sl") is not None:
                            trade_row = await get_trade(self.trade_id)
                            if trade_row:
                                _, _, _, _, size, *_ = trade_row
                                sl_d = Decimal(str(self.signal.get("sl")))
                                await self.fsm.record_exit({"orderId": "", "orderLinkId": f"{self.trade_id}-SL", "side": "SL"}, float(sl_d), float(size), "SL")
                    except Exception:
                        pass
                    return "SL_HIT"

            await asyncio.sleep(3)

        print("⚠️ Timeout — no exit detected")
        return "TIMEOUT"