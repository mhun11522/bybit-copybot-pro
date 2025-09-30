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
from app import settings
from app.margin_mode import MarginModeManager
from typing import List


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
        self.position_size = Decimal("0")
        self.avg_entry = None
        self.entry_orders = []
        self.margin_manager = MarginModeManager(self.bybit)

    async def run(self):
        try:
            # Send signal received message
            await self._send_signal_received()
            
            await self.set_leverage()
            
            # Enforce margin mode
            await self.margin_manager.enforce_margin_mode(self.signal["symbol"])
            
            await self.place_entries()
            await self.confirm_position()
            await self.place_tpsl()
            self.state = TradeState.DONE
            print(f"✅ Trade finished: {self.trade_id}")
        except Exception as e:
            print(f"❌ Trade error: {e}")
            self.state = TradeState.ERROR

    async def _send_signal_received(self):
        """Send signal received message."""
        try:
            # Calculate IM based on mode
            im = settings.INITIAL_MARGIN_USDT
            if self.signal.get("mode") == "SWING":
                im = settings.INITIAL_MARGIN_USDT
            
            await send_message(templates.signal_received(
                self.signal["symbol"],
                self.signal["direction"],
                self.signal.get("mode", "DYNAMIC"),
                self.signal.get("source", "Unknown"),
                self.signal["entries"],
                self.signal.get("tps", []),
                self.signal.get("sl"),
                self.signal["leverage"],
                im
            ))
        except Exception as e:
            print(f"Signal received message error: {e}")

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

    @safe_step("place_entries")
    async def place_entries(self):
        side = "Buy" if self.signal["direction"] == "BUY" else "Sell"
        
        # Get instrument info for precision
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

        # Calculate total quantity for 2% risk
        total_qty = Decimal("0")
        if self.signal.get("sl"):
            price_for_risk = q_price(self.signal["symbol"], live_price if live_price else Decimal(str(planned_entries[0])))
            total_qty = await qty_for_2pct_risk(self.signal["symbol"], price_for_risk, self.signal["sl"]) or Decimal("0")
        
        # Split quantity between entries (50/50)
        per_entry_qty = total_qty / Decimal("2") if len(planned_entries) == 2 else total_qty

        confirmed_link_ids = []
        for i, entry in enumerate(planned_entries, start=1):
            raw_price = live_price if live_price else Decimal(str(entry))
            price = await q_price(self.signal["symbol"], raw_price)
            
            # Use calculated quantity or fallback to min notional
            if per_entry_qty > 0:
                qty = await ensure_min_notional(self.signal["symbol"], price, per_entry_qty)
            else:
                # Fallback: use min notional approach
                required_qty = (min_notional / price).quantize(qty_step, rounding=ROUND_UP)
                qty = max(required_qty, min_qty)
                qty = await ensure_min_notional(self.signal["symbol"], price, qty)

            # Place entry order with PostOnly
            resp = await asyncio.to_thread(
                self.bybit.create_entry_order,
                self.signal["symbol"],
                side,
                str(qty),
                str(price),
                self.trade_id,
                i,
            )
            print(f"Entry {i} attempt @ qty={qty} price={price} response:", resp)
            
            if resp.get("retCode") == 0:
                try:
                    order_id = resp.get("result", {}).get("orderId", "")
                    link_id = resp.get("result", {}).get("orderLinkId", f"{self.trade_id}-E{i}")
                    await save_order(order_id, self.trade_id, link_id, "ENTRY_LIMIT", float(str(price)), float(str(qty)), "New")
                    self.entry_orders.append({"order_id": order_id, "link_id": link_id, "price": price, "qty": qty})
                    confirmed_link_ids.append(link_id)
                except Exception as e:
                    print(f"Save order error: {e}")
            else:
                raise Exception(f"Entry {i} failed: {resp}")

        # Send order placed message
        try:
            await send_message(templates.order_placed(
                self.signal["symbol"],
                self.signal["direction"],
                self.signal.get("mode", "DYNAMIC"),
                self.signal.get("source", "Unknown"),
                self.signal["entries"],
                self.signal.get("tps", []),
                self.signal.get("sl"),
                self.signal["leverage"],
                settings.INITIAL_MARGIN_USDT,
                confirmed_link_ids
            ))
        except Exception as e:
            print(f"Order placed message error: {e}")

        self.state = TradeState.ENTRIES_PLACED
        try:
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
                        self.position_size = Decimal(pos["size"])
                        
                        # Calculate volume-weighted average entry
                        self.avg_entry = self._calculate_avg_entry()
                        
                        try:
                            await save_trade(
                                self.trade_id,
                                self.signal["symbol"],
                                self.signal["direction"],
                                float(self.avg_entry),
                                float(self.position_size),
                                "POSITION_CONFIRMED",
                            )
                        except Exception:
                            pass
                        
                        # Send position opened message
                        try:
                            await send_message(templates.position_opened(
                                self.signal["symbol"],
                                self.signal["direction"],
                                self.signal.get("mode", "DYNAMIC"),
                                self.signal.get("source", "Unknown"),
                                self.position_size,
                                self.avg_entry,
                                self.signal["leverage"],
                                settings.INITIAL_MARGIN_USDT
                            ))
                        except Exception as e:
                            print(f"Position opened message error: {e}")
                        
                        return
                        
            await asyncio.sleep(3)
        raise Exception("No position found after waiting")

    def _calculate_avg_entry(self) -> Decimal:
        """Calculate volume-weighted average entry from filled orders."""
        if not self.entry_orders:
            return Decimal(str(self.signal["entries"][0]))
        
        total_value = Decimal("0")
        total_qty = Decimal("0")
        
        for order in self.entry_orders:
            total_value += order["price"] * order["qty"]
            total_qty += order["qty"]
        
        if total_qty > 0:
            return total_value / total_qty
        else:
            return Decimal(str(self.signal["entries"][0]))

    async def place_tpsl(self):
        print("🎯 Placing TP/SL...")
        side = "Sell" if self.signal["direction"] == "BUY" else "Buy"
        
        # Get instrument info for precision
        info = await asyncio.to_thread(self.bybit.get_instruments_info, self.signal["symbol"]) or {}
        details = (info.get("result", {}).get("list") or [{}])[0]
        lot = details.get("lotSizeFilter", {})
        qty_step = Decimal(str(lot.get("qtyStep", "0.001")))

        def round_down_to_step(value: Decimal, step: Decimal) -> Decimal:
            if step == 0:
                return value
            return (value / step).to_integral_value(rounding=ROUND_DOWN) * step

        # Place TP orders
        tps = list(self.signal.get("tps", []))
        if tps:
            # Equal-split TP quantities
            base_qty = round_down_to_step(self.position_size / len(tps), qty_step)
            allocated = Decimal("0")
            
            for i, tp in enumerate(tps, start=1):
                if i < len(tps):
                    tp_qty = base_qty
                    allocated += tp_qty
                else:
                    tp_qty = round_down_to_step(max(self.position_size - allocated, Decimal("0")), qty_step)
                
                price_q = await q_price(self.signal["symbol"], tp)
                tp_qty_final = await ensure_min_notional(self.signal["symbol"], price_q, tp_qty)
                
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
            sl_qty_d = await ensure_min_notional(self.signal["symbol"], sl_trig, q_qty(self.signal["symbol"], self.position_size))
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
            asyncio.create_task(self.trailing.monitor(entry_price=self.signal["entries"][0], qty=str(self.position_size)))
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