from decimal import Decimal
import asyncio
import sqlite3
from app.config.settings import CATEGORY, MAX_CONCURRENT_TRADES
from app.bybit.client import BybitClient
from app.core.precision import q_price, q_qty, ensure_min_notional
from app.core.errors import safe_step, breaker_reset
from app.trade.planner import plan_dual_entries
from app.trade.risk import qty_for_2pct_risk
from app.telegram.templates import leverage_set, entries_placed, position_confirmed, tpsl_placed
from app.telegram.output import send_message

from app.trade.oco import OCOManager
from app.trade.trailing import TrailingStopManager
from app.trade.hedge import HedgeReentryManager
from app.trade.pyramid import PyramidManager
from app.trade.tp2_be import TP2BreakEvenManager

DB_PATH = "trades.sqlite"

async def _active_trades() -> int:
    def _sync_operation():
        with sqlite3.connect(DB_PATH) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS trades(
                    trade_id TEXT PRIMARY KEY,
                    symbol TEXT,
                    direction TEXT,
                    avg_entry REAL,
                    position_size REAL,
                    leverage REAL,
                    channel_name TEXT,
                    realized_pnl REAL DEFAULT 0,
                    state TEXT
                )
            """)
            cur = db.execute("SELECT COUNT(*) FROM trades WHERE state!='DONE'")
            return cur.fetchone()[0] or 0
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_operation)

async def _upsert_trade(trade_id, **fields):
    keys = ["symbol","direction","avg_entry","position_size","leverage","channel_name","state"]
    vals = [fields.get(k) for k in keys]
    
    def _sync_operation():
        with sqlite3.connect(DB_PATH) as db:
            db.execute("""
                INSERT INTO trades(trade_id,symbol,direction,avg_entry,position_size,leverage,channel_name,state)
                VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(trade_id) DO UPDATE SET
                    symbol=excluded.symbol,
                    direction=excluded.direction,
                    avg_entry=excluded.avg_entry,
                    position_size=excluded.position_size,
                    leverage=excluded.leverage,
                    channel_name=excluded.channel_name,
                    state=excluded.state
            """, (trade_id, *vals))
            db.commit()
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _sync_operation)

class TradeFSM:
    def __init__(self, sig: dict):
        self.sig = sig
        self.bybit = BybitClient()
        self.trade_id = f"{sig['symbol']}-{sig['direction']}-{int(abs(hash(str(sig)))%1e8)}"
        self.position_size = Decimal("0")
        self.avg_entry = None

    @safe_step("open_guard")
    async def open_guard(self):
        if await _active_trades() >= MAX_CONCURRENT_TRADES:
            await send_message(f"⛔ Kapacitetsgräns {MAX_CONCURRENT_TRADES} uppnådd / Capacity reached")
            raise RuntimeError("capacity")
        await _upsert_trade(self.trade_id,
                            symbol=self.sig["symbol"],
                            direction=self.sig["direction"],
                            avg_entry=0,
                            position_size=0,
                            leverage=self.sig["leverage"],
                            channel_name=self.sig["channel_name"],
                            state="OPENING")

    @safe_step("set_leverage")
    async def set_leverage(self):
        # Validate leverage policy
        lev = self.sig["leverage"]
        mode = self.sig["mode"]
        
        if mode == "SWING" and lev != 6:
            raise ValueError(f"SWING mode requires exactly 6x leverage, got {lev}")
        elif mode == "DYNAMIC" and lev < 7.5:
            raise ValueError(f"DYNAMIC mode requires ≥7.5x leverage, got {lev}")
        elif mode == "FAST" and lev < 10:
            raise ValueError(f"FAST mode requires ≥10x leverage, got {lev}")
        elif 6 < lev < 7.5:
            raise ValueError(f"Leverage {lev} is forbidden (must be 6, ≥7.5, or ≥10)")
        
        r = await self.bybit.set_leverage(CATEGORY, self.sig["symbol"], lev, lev)
        breaker_reset()
        await send_message(leverage_set(self.sig["symbol"], lev, self.sig["channel_name"], mode))
        return r

    @safe_step("place_entries")
    async def place_entries(self):
        side = "Buy" if self.sig["direction"] == "BUY" else "Sell"
        plan_entries, splits = plan_dual_entries(self.sig["direction"], self.sig["entries"])
        base_qty = await qty_for_2pct_risk(CATEGORY, self.sig["symbol"], plan_entries[0], self.sig["sl"])
        if base_qty <= 0:
            raise Exception("2% risk produced non-positive qty")

        for i, (e_raw, frac) in enumerate(zip(plan_entries, splits), start=1):
            price_q = await q_price(CATEGORY, self.sig["symbol"], e_raw)
            qty_q   = await ensure_min_notional(CATEGORY, self.sig["symbol"], price_q, (base_qty * frac))
            await self.bybit.entry_limit_postonly(
                CATEGORY, self.sig["symbol"], side,
                str(qty_q), str(price_q), f"{self.trade_id}-E{i}"
            )
        breaker_reset()
        await send_message(entries_placed(self.sig["symbol"], plan_entries, self.trade_id, self.sig["channel_name"]))

    @safe_step("confirm_position")
    async def confirm_position(self):
        # Poll Bybit for a filled position
        for _ in range(60):
            pos = await self.bybit.positions(CATEGORY, self.sig["symbol"])
            try:
                row = pos["result"]["list"][0]
                size = Decimal(str(row.get("size") or "0"))
                if size > 0:
                    self.position_size = size
                    self.avg_entry = Decimal(str(row.get("avgPrice") or self.sig["entries"][0]))
                    await _upsert_trade(self.trade_id,
                                        symbol=self.sig["symbol"],
                                        direction=self.sig["direction"],
                                        avg_entry=float(self.avg_entry),
                                        position_size=float(self.position_size),
                                        leverage=self.sig["leverage"],
                                        channel_name=self.sig["channel_name"],
                                        state="OPEN")
                    breaker_reset()
                    await send_message(position_confirmed(self.sig["symbol"], self.position_size, self.avg_entry, self.sig["channel_name"]))
                    return
            except Exception:
                pass
            await asyncio.sleep(1)
        raise Exception("Position not confirmed")

    @safe_step("place_tpsl")
    async def place_tpsl(self):
        exit_side = "Sell" if self.sig["direction"] == "BUY" else "Buy"
        splits = [Decimal("0.5"), Decimal("0.3"), Decimal("0.2")][:len(self.sig["tps"])]

        for i, (tp_raw, frac) in enumerate(zip(self.sig["tps"], splits), start=1):
            p = await q_price(CATEGORY, self.sig["symbol"], tp_raw)
            q = await q_qty(CATEGORY, self.sig["symbol"], self.position_size * frac)
            q = await ensure_min_notional(CATEGORY, self.sig["symbol"], p, q)
            await self.bybit.tp_limit_reduceonly(CATEGORY, self.sig["symbol"], exit_side, str(q), str(p), f"{self.trade_id}-TP{i}")

        sl = await q_price(CATEGORY, self.sig["symbol"], self.sig["sl"])
        full_q = await q_qty(CATEGORY, self.sig["symbol"], self.position_size)
        await self.bybit.sl_market_reduceonly_mark(CATEGORY, self.sig["symbol"], exit_side, str(full_q), str(sl), f"{self.trade_id}-SL")
        breaker_reset()
        await send_message(tpsl_placed(self.sig["symbol"], self.sig["tps"], self.sig["sl"], self.sig["channel_name"]))

    async def run(self):
        await self.open_guard()
        await self.set_leverage()
        await self.place_entries()
        await self.confirm_position()
        await self.place_tpsl()

        # Start controllers (background best-effort)
        oco = OCOManager(self.trade_id, self.sig["symbol"], self.sig["direction"], self.sig["channel_name"])
        trail = TrailingStopManager(self.trade_id, self.sig["symbol"], self.sig["direction"], self.avg_entry, self.position_size, self.sig["channel_name"])
        hedge = HedgeReentryManager(self.trade_id, self.sig["symbol"], self.sig["direction"], self.avg_entry, self.position_size, self.sig["leverage"], self.sig["channel_name"])
        pyramid = PyramidManager(self.trade_id, self.sig["symbol"], self.sig["direction"], self.sig["leverage"], self.sig["channel_name"], planned_entries=self.sig.get("entries", [])[1:])
        tp2be = TP2BreakEvenManager(self.trade_id, self.sig["symbol"], self.sig["direction"], self.avg_entry, self.sig["channel_name"])

        asyncio.create_task(oco.run())
        asyncio.create_task(trail.run())
        asyncio.create_task(hedge.run())
        asyncio.create_task(pyramid.run())
        asyncio.create_task(tp2be.run())