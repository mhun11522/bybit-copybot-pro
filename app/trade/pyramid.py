from decimal import Decimal, ROUND_UP
import asyncio
from app.telegram.output import send_message
from app.telegram import templates


class PyramidManager:
    def __init__(self, bybit_client, trade_id: str, base_symbol: str, direction: str, leverage: int, step_im: Decimal = Decimal("20")):
        self.bybit = bybit_client
        self.trade_id = trade_id
        self.symbol = base_symbol
        self.direction = direction
        self.leverage = Decimal(str(leverage))
        self.step_im = Decimal(step_im)
        self.count = 0
        self.max_adds = 100

    def add_entry(self, price):
        if self.count >= self.max_adds:
            print("⚠️ Max pyramid adds reached")
            return None

        side = "Buy" if self.direction == "BUY" else "Sell"
        # Pull instrument filters
        info = self.bybit.get_instruments_info(self.symbol) or {}
        details = (info.get("result", {}).get("list") or [{}])[0]
        lot = details.get("lotSizeFilter", {})
        pricef = details.get("priceFilter", {})
        qty_step = Decimal(str(lot.get("qtyStep", "0.001")))
        min_qty = Decimal(str(lot.get("minOrderQty", "0.001")))
        min_notional = Decimal(str(lot.get("minNotionalValue", "5")))
        tick_size = Decimal(str(pricef.get("tickSize", "0.10")))

        # Enforce at least 20 USDT notional per add
        if min_notional < Decimal("20"):
            min_notional = Decimal("20")

        # Helpers
        def round_up_to_step(value: Decimal, step: Decimal) -> Decimal:
            if step == 0:
                return value
            return (value / step).to_integral_value(rounding=ROUND_UP) * step

        price_d = round_up_to_step(Decimal(str(price)), tick_size)

        # Use live last price to satisfy minNotional reliably (Bybit validates against market values)
        live_price = None
        try:
            ticker = self.bybit.get_ticker(self.symbol) or {}
            last_price_str = ((ticker.get("result", {}).get("list") or [{}])[0].get("lastPrice"))
            if last_price_str:
                live_price = Decimal(str(last_price_str))
        except Exception:
            live_price = None

        ref_price = live_price if live_price else price_d

        # Start from fixed IM step sizing: qty = IM * leverage / ref_price
        base_qty = (self.step_im * self.leverage) / ref_price
        qty_d = round_up_to_step(base_qty, qty_step)
        if qty_d < min_qty:
            qty_d = round_up_to_step(min_qty, qty_step)

        # Ensure min notional against reference price
        notional = qty_d * ref_price
        if notional < min_notional:
            required_qty = round_up_to_step(min_notional / ref_price, qty_step)
            if required_qty > qty_d:
                qty_d = required_qty

        attempts = 0
        while True:
            qty_str = str(qty_d)
            resp = self.bybit.create_entry_order(
                symbol=self.symbol,
                side=side,
                qty=qty_str,
                price=str(price_d),
                trade_id=self.trade_id,
                entry_no=self.count + 10,
            )
            print(f"Pyramid attempt {attempts + 1} @ qty={qty_str} price={price_d} resp: {resp}")
            if isinstance(resp, dict) and resp.get("retCode") == 0:
                self.count += 1
                print(f"✅ Pyramid add {self.count} placed at {price_d} qty {qty_str}")
                # Notify (fire-and-forget)
                try:
                    loop = asyncio.get_event_loop()
                    loop.create_task(send_message(templates.pyramid_added(self.symbol, str(price_d), qty_str)))
                except Exception:
                    pass
                return resp
            # Retry: bump qty up (double for faster convergence) if min notional error persists
            if isinstance(resp, dict) and resp.get("retCode") == 110094 and attempts < 4:
                qty_d = round_up_to_step(qty_d * Decimal("2"), qty_step)
                attempts += 1
                continue
            print("❌ Pyramid add failed:", resp)
            return resp

    def _calc_qty(self, price):
        # Compute quantity from IM step and leverage, quantized by instrument step
        from app.core.precision import q_qty
        price_d = Decimal(str(price))
        if price_d == 0:
            return Decimal("0")
        raw = (self.step_im * self.leverage) / price_d
        return q_qty(self.symbol, raw)