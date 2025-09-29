import asyncio


class OCOManager:
    def __init__(self, bybit_client, signal: dict, trade_id: str):
        self.bybit = bybit_client
        self.signal = signal
        self.trade_id = trade_id

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
                    return "TP_HIT"

                if not tp_active and sl_active:
                    print("✅ SL triggered, canceling all TPs")
                    self.bybit.cancel_all(symbol)
                    return "SL_HIT"

            await asyncio.sleep(3)

        print("⚠️ Timeout — no exit detected")
        return "TIMEOUT"