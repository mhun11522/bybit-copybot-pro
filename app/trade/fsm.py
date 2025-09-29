import asyncio
import time
from decimal import Decimal, ROUND_UP
from enum import Enum, auto
from app.bybit_client import BybitClient
from app.trade.oco import OCOManager


class TradeState(Enum):
    RECEIVED = auto()
    LEVERAGE_SET = auto()
    ENTRIES_PLACED = auto()
    POSITION_CONFIRMED = auto()
    TPSL_PLACED = auto()
    DONE = auto()
    ERROR = auto()


class TradeFSM:
    def __init__(self, signal: dict, bybit_client=None, telegram_client=None):
        self.signal = signal
        self.bybit = bybit_client or BybitClient()
        self.tg = telegram_client
        self.state = TradeState.RECEIVED
        self.trade_id = f"TRD-{signal['symbol']}-{signal['direction']}-{int(time.time()*1000)}"

    async def run(self):
        try:
            await self.set_leverage()
            await self.place_entries()
            await self.confirm_position()
            await self.place_tpsl()
            self.state = TradeState.DONE
            print(f"✅ Trade finished: {self.trade_id}")
        except Exception as e:
            self.state = TradeState.ERROR
            print(f"❌ Error in trade {self.trade_id}: {e}")

    async def set_leverage(self):
        print(f"🔧 Setting leverage {self.signal['leverage']}x for {self.signal['symbol']}")
        resp = await asyncio.to_thread(
            self.bybit.set_leverage,
            self.signal["symbol"],
            self.signal["leverage"],
            self.signal["leverage"],
        )
        print("Leverage response:", resp)
        # retCode 0 OK; 110043 means leverage unchanged – acceptable
        if resp.get("retCode") not in (0, 110043):
            raise Exception(f"Leverage failed: {resp}")
        self.state = TradeState.LEVERAGE_SET

    async def place_entries(self):
        side = "Buy" if self.signal["direction"] == "BUY" else "Sell"
        # Inspect instrument filters to compute compliant qty/price
        info = await asyncio.to_thread(self.bybit.get_instruments_info, self.signal["symbol"]) or {}
        details = (info.get("result", {}).get("list") or [{}])[0]
        lot = details.get("lotSizeFilter", {})
        pricef = details.get("priceFilter", {})
        qty_step = Decimal(str(lot.get("qtyStep", "0.001")))
        min_qty = Decimal(str(lot.get("minOrderQty", "0.001")))
        min_notional = Decimal(str(lot.get("minNotionalValue", "5")))
        tick_size = Decimal(str(pricef.get("tickSize", "0.10")))

        def round_up_to_step(value: Decimal, step: Decimal) -> Decimal:
            if step == 0:
                return value
            # Quantize up to the nearest multiple of step
            return (value / step).to_integral_value(rounding=ROUND_UP) * step

        # Use live last price to satisfy minNotional reliably
        ticker = await asyncio.to_thread(self.bybit.get_ticker, self.signal["symbol"]) or {}
        last_price_str = (
            (ticker.get("result", {}).get("list") or [{}])[0].get("lastPrice")
            if isinstance(ticker, dict)
            else None
        )
        live_price = Decimal(str(last_price_str)) if last_price_str else None

        for i, entry in enumerate(self.signal["entries"], start=1):
            price = live_price if live_price else Decimal(str(entry))
            price = round_up_to_step(price, tick_size)
            # Compute minimal qty to satisfy notional and min_qty
            required_qty = round_up_to_step(min_notional / price, qty_step)
            # Safety factor to exceed min notional comfortably
            safe_qty = round_up_to_step(required_qty * Decimal("2"), qty_step)
            qty = max(safe_qty, min_qty)

            # Try up to 4 times, increasing qty if min notional error persists
            attempts = 0
            while True:
                resp = await asyncio.to_thread(
                    self.bybit.create_entry_order,
                    self.signal["symbol"],
                    side,
                    str(qty),
                    str(price),
                    self.trade_id,
                    i,
                )
                print(f"Entry {i} attempt {attempts + 1} @ qty={qty} price={price} response:", resp)
                if resp.get("retCode") == 0:
                    break
                # 110094: minimum order value not met -> increase qty and retry
                if resp.get("retCode") == 110094 and attempts < 3:
                    qty = round_up_to_step(qty * Decimal("2"), qty_step)
                    attempts += 1
                    continue
                raise Exception(f"Entry {i} failed: {resp}")
        # verify open orders
        check = await asyncio.to_thread(self.bybit.get_open_orders, self.signal["symbol"])
        print("Open orders check:", check)
        self.state = TradeState.ENTRIES_PLACED

    async def confirm_position(self):
        print("🔍 Checking for position...")
        for attempt in range(10):
            resp = await asyncio.to_thread(self.bybit.get_positions, self.signal["symbol"])
            print("Position check:", resp)
            if resp.get("retCode") == 0:
                pos_list = resp.get("result", {}).get("list", [])
                for pos in pos_list:
                    if pos.get("size") and float(pos["size"]) > 0:
                        print("✅ Position confirmed")
                        self.state = TradeState.POSITION_CONFIRMED
                        self.position_size = pos["size"]
                        return
            await asyncio.sleep(3)
        raise Exception("No position found after waiting")

    async def place_tpsl(self):
        print("🎯 Placing TP/SL...")
        side = "Sell" if self.signal["direction"] == "BUY" else "Buy"
        qty = "0.001"  # tiny test size

        for i, tp in enumerate(self.signal.get("tps", []), start=1):
            resp = await asyncio.to_thread(
                self.bybit.create_tp_order,
                self.signal["symbol"],
                side,
                qty,
                tp,
                self.trade_id,
                i,
            )
            print(f"TP{i} resp:", resp)

        if self.signal.get("sl"):
            resp = await asyncio.to_thread(
                self.bybit.create_sl_order,
                self.signal["symbol"],
                side,
                qty,
                self.signal["sl"],
                self.trade_id,
            )
            print("SL resp:", resp)

        # Stabilization delay to allow pending IO to settle on Windows
        await asyncio.sleep(0.05)
        self.state = TradeState.TPSL_PLACED

        # Start OCO monitoring
        oco = OCOManager(self.bybit, self.signal, self.trade_id)
        result = await oco.monitor()
        print("OCO result:", result)