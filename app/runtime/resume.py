import asyncio
from app.bybit_client import BybitClient
from app.storage.db import get_open_trades
from app.trade.oco import OCOManager
from app.trade.trailing import TrailingStopManager
from app.trade.hedge import HedgeReentryManager


async def resume_open_trades():
    bybit = BybitClient()
    rows = await get_open_trades()
    for trade_id, symbol, direction, entry_price, size, state in rows:
        # Minimal signal stub for OCO
        signal = {"symbol": symbol, "direction": direction, "tps": [], "sl": None}

        # OCO monitoring (non-blocking)
        try:
            oco = OCOManager(bybit, signal, trade_id)
            asyncio.create_task(oco.monitor())
        except Exception:
            pass

        # Trailing stop (non-blocking)
        try:
            trailing = TrailingStopManager(bybit, trade_id, symbol, direction, sl_price=None)
            asyncio.create_task(trailing.monitor(entry_price=entry_price, qty=str(size)))
        except Exception:
            pass

        # Hedge / re-entry (non-blocking)
        try:
            hedge = HedgeReentryManager(bybit, trade_id, symbol, direction, leverage=5)
            asyncio.create_task(hedge.monitor(entry_price=entry_price, qty=str(size)))
        except Exception:
            pass

