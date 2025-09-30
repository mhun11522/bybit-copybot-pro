from __future__ import annotations
import asyncio
import time
from decimal import Decimal, ROUND_UP, ROUND_DOWN
from enum import Enum, auto
from app.bybit_client import BybitClient
from app.trade.oco import OCOManager
from app.trade.pyramid import PyramidManager
from app.trade.trailing import TrailingStopManager
from app.trade.hedge import HedgeReentryManager
from app.core.errors import safe_step
from app.core.precision import q_price, q_qty, ensure_min_notional
from app.trade.risk import qty_for_2pct_risk
from app.storage.db import save_trade, save_order, save_fill, close_trade
from app.core.leverage import enforce_leverage
from app.telegram.output import send_message
from app.telegram import templates


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
            # Error already handled by @safe_step wrappers where applicable
            self.state = TradeState.ERROR

    @safe_step("set_leverage")
    async def set_leverage(self):
        print(f"🔧 Setting leverage {self.signal['leverage']}x for {self.signal['symbol']}")
        # Enforce leverage policy (mode inferred from signal.get('mode'))
        lev = enforce_leverage(self.signal.get("mode", "DYNAMIC"), int(self.signal["leverage"]))
        resp = await asyncio.to_thread(
            self.bybit.set_leverage,
            self.signal["symbol"],
            lev,
            lev,
        )
        print("Leverage response:", resp)
        # retCode 0 OK; 110043 means leverage unchanged – acceptable
        if resp.get("retCode") not in (0, 110043):
            raise Exception(f"Leverage failed: {resp}")
        self.state = TradeState.LEVERAGE_SET
        try:
            await save_trade(self.trade_id, self.signal["symbol"], self.signal["direction"], 0.0, 0.0, "LEVERAGE_SET")
        except Exception:
            pass
        # Notify leverage set
        try:
            await send_message(templates.leverage_set(self.signal["symbol"], lev, self.signal.get("source")))
        except Exception:
            pass

    @safe_step("place_entries")
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
        # Enforce at least 20 USDT notional per order
        if min_notional < Decimal("20"):
            min_notional = Decimal("20")
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

        planned_entries = list(self.signal["entries"])
        # If only one entry is provided, auto-create a second at ±0.1% in the trade direction
        if len(planned_entries) == 1:
            base = live_price if live_price else Decimal(str(planned_entries[0]))
            if self.signal["direction"] == "BUY":
                planned_entries = [base, base * Decimal("0.999")]  # 0.1% below
            else:
                planned_entries = [base, base * Decimal("1.001")]  # 0.1% above

        # Enforce 2% risk sizing when SL is present.
        # If two entries, split equally; else use full risk sizing for the single entry.
        per_entry_qty_override = None
        if self.signal.get("sl"):
            price_for_risk = q_price(self.signal["symbol"], live_price if live_price else Decimal(str(planned_entries[0])))
            total_qty = qty_for_2pct_risk(self.signal["symbol"], price_for_risk, self.signal["sl"]) or Decimal("0")
            if len(planned_entries) == 2 and total_qty > 0:
                per_entry_qty_override = (total_qty / Decimal("2"))
            elif len(planned_entries) == 1:
                per_entry_qty_override = total_qty

        confirmed_link_ids: list[str] = []
        for i, entry in enumerate(planned_entries, start=1):
            raw_price = live_price if live_price else Decimal(str(entry))
            price = q_price(self.signal["symbol"], raw_price)
            # Prefer risk-based sizing if available; else fallback to min-notional approach
            if per_entry_qty_override is not None:
                qty = ensure_min_notional(self.signal["symbol"], price, q_qty(self.signal["symbol"], per_entry_qty_override))
            elif self.signal.get("sl"):
                qty_risk = qty_for_2pct_risk(self.signal["symbol"], price, self.signal["sl"]) or Decimal("0")
                qty = ensure_min_notional(self.signal["symbol"], price, qty_risk)
            else:
                required_qty = round_up_to_step(min_notional / price, qty_step)
                safe_qty = round_up_to_step(required_qty * Decimal("2"), qty_step)
                qty = max(safe_qty, min_qty)
                qty = ensure_min_notional(self.signal["symbol"], price, qty)

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
                    try:
                        order_id = resp.get("result", {}).get("orderId", "")
                        link_id = resp.get("result", {}).get("orderLinkId", f"{self.trade_id}-E{i}")
                        await save_order(order_id, self.trade_id, link_id, "ENTRY_LIMIT", float(str(price)), float(str(qty)), "New")
                        # ACK: wait until order visible by link id
                        await self._wait_order_visible(link_id)
                        confirmed_link_ids.append(link_id)
                    except Exception:
                        pass
                    break
                # 110094: minimum order value not met -> increase qty and retry
                if resp.get("retCode") == 110094 and attempts < 3:
                    qty = round_up_to_step(qty * Decimal("2"), qty_step)
                    attempts += 1
                    continue
                raise Exception(f"Entry {i} failed: {resp}")
        # Verify open orders overall (debug log)
        check = await asyncio.to_thread(self.bybit.get_open_orders, self.signal["symbol"])
        print("Open orders check:", check)
        self.state = TradeState.ENTRIES_PLACED
        try:
            # Persist without hardcoded size; use 0.0 until confirmed
            await save_trade(
                self.trade_id,
                self.signal["symbol"],
                self.signal["direction"],
                float(str(self.signal["entries"][0])),
                0.0,
                "ENTRIES_PLACED",
            )
        except Exception:
            pass
        # Notify entries placed with confirmed link ids only
        try:
            if confirmed_link_ids:
                await send_message(templates.entries_placed(self.signal["symbol"], confirmed_link_ids, self.signal.get("source")))
        except Exception:
            pass

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
                        # Try to capture avg entry (VWAP) if provided by API
                        avg_entry = None
                        try:
                            avg_entry = pos.get("avgPrice") or pos.get("sessionAvgPrice")
                        except Exception:
                            avg_entry = None
                        try:
                            await save_trade(
                                self.trade_id,
                                self.signal["symbol"],
                                self.signal["direction"],
                                float(str(self.signal["entries"][0])),
                                float(self.position_size),
                                "POSITION_CONFIRMED",
                            )
                        except Exception:
                            pass
                        # Notify position confirmed
                        try:
                            from decimal import Decimal as _D
                            await send_message(templates.position_confirmed(self.signal["symbol"], _D(str(self.position_size)), _D(str(avg_entry)) if avg_entry else None, self.signal.get("source")))
                        except Exception:
                            pass
                        # Initialize pyramid manager for subsequent adds
                        self.pyramid = PyramidManager(
                            self.bybit,
                            self.trade_id,
                            self.signal["symbol"],
                            self.signal["direction"],
                            self.signal["leverage"],
                        )
                        # Start hedge/re-entry monitor in background
                        try:
                            self.hedge = HedgeReentryManager(
                                self.bybit,
                                self.trade_id,
                                self.signal["symbol"],
                                self.signal["direction"],
                                self.signal["leverage"],
                            )
                            asyncio.create_task(self.hedge.monitor(entry_price=self.signal["entries"][0], qty=str(self.position_size)))
                        except Exception as e:
                            print("Hedge initialization error:", e)
                        return
                        
            await asyncio.sleep(3)
        raise Exception("No position found after waiting")

    async def place_tpsl(self):
        print("🎯 Placing TP/SL...")
        side = "Sell" if self.signal["direction"] == "BUY" else "Buy"
        # Use actual confirmed position size
        size_str = getattr(self, "position_size", "0")
        size_d = Decimal(str(size_str)) if size_str else Decimal("0")

        # Fetch qty step for precise allocation
        info = await asyncio.to_thread(self.bybit.get_instruments_info, self.signal["symbol"]) or {}
        details = (info.get("result", {}).get("list") or [{}])[0]
        lot = details.get("lotSizeFilter", {})
        qty_step = Decimal(str(lot.get("qtyStep", "0.001")))

        def round_down_to_step(value: Decimal, step: Decimal) -> Decimal:
            if step == 0:
                return value
            return (value / step).to_integral_value(rounding=ROUND_DOWN) * step

        tps = list(self.signal.get("tps", []))
        num_tps = len(tps)
        # Equal-split TP quantities; last TP gets remainder to match size
        base_qty = round_down_to_step((size_d / num_tps) if num_tps else Decimal("0"), qty_step) if num_tps else Decimal("0")
        allocated = Decimal("0")
        for i, tp in enumerate(tps, start=1):
            if num_tps == 0 or size_d <= 0:
                break
            if i < num_tps:
                tp_qty_d = base_qty
                allocated += tp_qty_d
            else:
                tp_qty_d = round_down_to_step(max(size_d - allocated, Decimal("0")), qty_step)
            price_q = q_price(self.signal["symbol"], tp)
            tp_qty_q = q_qty(self.signal["symbol"], tp_qty_d)
            tp_qty_final = ensure_min_notional(self.signal["symbol"], price_q, tp_qty_q)
            qty = str(tp_qty_final)
            resp = await asyncio.to_thread(
                self.bybit.create_tp_order,
                self.signal["symbol"],
                side,
                qty,
                price_q,
                self.trade_id,
                i,
            )
            print(f"TP{i} resp:", resp)
            if resp.get("retCode") == 0:
                try:
                    order_id = resp.get("result", {}).get("orderId", "")
                    link_id = resp.get("result", {}).get("orderLinkId", f"{self.trade_id}-TP{i}")
                    await save_order(order_id, self.trade_id, link_id, "TP_LIMIT", float(str(price_q)), float(qty), "New")
                    # ACK-gate: verify TP is visible in open orders by link id
                    await self._wait_order_visible(link_id)
                except Exception:
                    pass

        if self.signal.get("sl"):
            sl_trig = q_price(self.signal["symbol"], self.signal["sl"])
            sl_qty_d = ensure_min_notional(self.signal["symbol"], sl_trig, q_qty(self.signal["symbol"], size_d))
            sl_qty = str(sl_qty_d)
            resp = await asyncio.to_thread(
                self.bybit.create_sl_order,
                self.signal["symbol"],
                side,
                sl_qty,
                sl_trig,
                self.trade_id,
            )
            print("SL resp:", resp)
            if resp.get("retCode") == 0:
                try:
                    order_id = resp.get("result", {}).get("orderId", "")
                    link_id = resp.get("result", {}).get("orderLinkId", f"{self.trade_id}-SL")
                    await save_order(order_id, self.trade_id, link_id, "SL_STOP_MARKET", float(str(sl_trig)), float(sl_qty), "New")
                    # ACK-gate: verify SL is visible in open orders by link id (conditional list may differ; best-effort)
                    await self._wait_order_visible(link_id)
                except Exception:
                    pass

        # Stabilization delay to allow pending IO to settle on Windows
        await asyncio.sleep(0.05)
        self.state = TradeState.TPSL_PLACED
        try:
            await save_trade(
                self.trade_id,
                self.signal["symbol"],
                self.signal["direction"],
                float(str(self.signal["entries"][0])),
                float(self.position_size) if hasattr(self, "position_size") else 0.0,
                "TPSL_PLACED",
            )
        except Exception:
            pass
        # Notify TP/SL placed only after verification
        try:
            tp_links = [f"{self.trade_id}-TP{i}" for i in range(1, len(tps) + 1)]
            sl_link = f"{self.trade_id}-SL" if self.signal.get("sl") else None
            confirmed = 0
            for lid in tp_links:
                ok = await self._wait_order_visible(lid)
                confirmed += 1 if ok else 0
            if sl_link:
                ok = await self._wait_order_visible(sl_link)
                # do not increment; message shows counts based on config, but only send if all visible
                all_ok = (confirmed == len(tp_links)) and ok
            else:
                all_ok = (confirmed == len(tp_links))
            if all_ok:
                await send_message(templates.tpsl_placed(self.signal["symbol"], len(tps), str(self.signal.get("sl")), self.signal.get("source")))
        except Exception:
            pass

        # Start OCO monitoring (non-blocking)
        try:
            self.oco = OCOManager(self.bybit, self.signal, self.trade_id, fsm=self)
            asyncio.create_task(self.oco.monitor())
        except Exception as e:
            print("OCO initialization error:", e)

        # Start trailing stop in background (non-blocking)
        try:
            self.trailing = TrailingStopManager(
                self.bybit,
                self.trade_id,
                self.signal["symbol"],
                self.signal["direction"],
                self.signal.get("sl"),
            )
            asyncio.create_task(self.trailing.monitor(entry_price=self.signal["entries"][0], qty=str(size_d)))
        except Exception as e:
            print("Trailing initialization error:", e)

    async def record_exit(self, order: dict, exit_price: str | float, qty: str | float, side: str):
        direction_factor = Decimal("1") if self.signal.get("direction") == "BUY" else Decimal("-1")
        entry_price = Decimal(str(self.signal.get("entries", [0])[0]))
        exit_p = Decimal(str(exit_price))
        qty_d = Decimal(str(qty))
        leverage = Decimal(str(self.signal.get("leverage", 1) or 1))
        pnl_d = (exit_p - entry_price) * qty_d * direction_factor * leverage
        fee = 0.0
        try:
            await save_fill(
                self.trade_id,
                order.get("orderId", ""),
                order.get("orderLinkId", ""),
                side,
                float(exit_p),
                float(qty_d),
                fee,
                float(pnl_d),
            )
            await close_trade(self.trade_id, float(pnl_d))
            print(f"💰 Recorded PnL for {self.trade_id}: {pnl_d} USDT")
            # Notify exit
            try:
                if (side or "").upper().startswith("TP"):
                    await send_message(templates.tp_hit(self.signal["symbol"], str(exit_price), self.signal.get("source")))
                else:
                    await send_message(templates.sl_hit(self.signal["symbol"], str(exit_price), self.signal.get("source")))
            except Exception:
                pass
        except Exception as e:
            print("record_exit error:", e)

    async def _wait_order_visible(self, order_link_id: str, retries: int = 5, delay_sec: float = 0.5) -> bool:
        symbol = self.signal["symbol"]
        for _ in range(retries):
            try:
                resp = await asyncio.to_thread(self.bybit.get_open_orders, symbol)
                if isinstance(resp, dict) and resp.get("retCode") == 0:
                    order_list = resp.get("result", {}).get("list", [])
                    if any((o.get("orderLinkId") == order_link_id) for o in order_list):
                        return True
            except Exception:
                pass
            await asyncio.sleep(delay_sec)
        # If not visible, we still continue, but report not confirmed
        return False