import asyncio, sqlite3
from decimal import Decimal
from typing import List, Optional
from app.bybit.client import BybitClient
from app.core.precision import q_price, ensure_min_notional
from app.trade.risk import qty_for_im_step
from app.telegram import output

DB_PATH="trades.sqlite"; CATEGORY="linear"; MAX_ADDS=100
DEFAULT_IM_LADDER = [Decimal("20"), Decimal("40"), Decimal("60"), Decimal("80"), Decimal("100")]

async def _ensure_table():
    def _sync_operation():
        with sqlite3.connect(DB_PATH) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS pyramid_state(
                trade_id TEXT PRIMARY KEY,
                adds_count INTEGER NOT NULL DEFAULT 0
            )""")
            db.commit()
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _sync_operation)

async def _get_count(trade_id: str)->int:
    await _ensure_table()
    def _sync_operation():
        with sqlite3.connect(DB_PATH) as db:
            cur = db.execute("SELECT adds_count FROM pyramid_state WHERE trade_id=?", (trade_id,))
            row = cur.fetchone()
            return int(row[0]) if row else 0
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_operation)

async def _inc_count(trade_id: str, inc: int=1)->int:
    await _ensure_table()
    def _sync_operation():
        with sqlite3.connect(DB_PATH) as db:
            cur = db.execute("SELECT adds_count FROM pyramid_state WHERE trade_id=?", (trade_id,))
            row = cur.fetchone(); current = int(row[0]) if row else 0
        new_val = current + inc
        if row:
            db.execute("UPDATE pyramid_state SET adds_count=? WHERE trade_id=?", (new_val, trade_id))
        else:
            db.execute("INSERT INTO pyramid_state(trade_id,adds_count) VALUES(?,?)", (trade_id, new_val))
        db.commit()
        return new_val
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_operation)

def _im_for_index(idx: int, ladder: List[Decimal]) -> Decimal:
    return ladder[idx] if idx < len(ladder) else ladder[-1]

class PyramidManager:
    def __init__(self, trade_id, symbol, direction, leverage, channel_name, planned_entries: Optional[List[str]] = None, im_ladder: Optional[List[Decimal]] = None):
        self.trade_id=trade_id; self.symbol=symbol; self.direction=direction
        self.leverage=leverage; self.channel_name=channel_name
        self.planned_entries=planned_entries or []
        self.im_ladder = im_ladder or DEFAULT_IM_LADDER
        self.bybit=BybitClient(); self._running=False

    async def _place_add(self, raw_price)->bool:
        count = await _get_count(self.trade_id)
        if count >= MAX_ADDS:
            await output.send_message(f"⛔ Max pyramideringar uppnådd / Max pyramid adds reached ({MAX_ADDS}) • Source: {self.channel_name}")
            return False

        im_step = _im_for_index(count, self.im_ladder)
        price_q = await q_price(CATEGORY, self.symbol, raw_price)
        qty_add = await qty_for_im_step(CATEGORY, self.symbol, price_q, self.leverage, im_step)
        qty_add = await ensure_min_notional(CATEGORY, self.symbol, price_q, qty_add)

        side_enter = "Buy" if self.direction=="BUY" else "Sell"
        link_id = f"{self.trade_id}-PY{count+1}"
        await self.bybit.entry_limit_postonly(CATEGORY, self.symbol, side_enter, str(qty_add), str(price_q), link_id)
        await _inc_count(self.trade_id, 1)
        await output.send_message(f"➕ Pyramid add {link_id} qty={qty_add} @ {price_q} (IM={im_step} USDT) • Source: {self.channel_name}")
        return True

    async def run(self):
        self._running=True
        for e in self.planned_entries:
            if not self._running: break
            try: await self._place_add(e)
            except Exception: pass
            await asyncio.sleep(0.3)
        self._running=False

    async def add_at_price(self, price_now):
        try: await self._place_add(price_now)
        except Exception: pass