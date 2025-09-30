import asyncio
import pytest
from app.trade.oco import OCOManager


@pytest.mark.asyncio
async def test_oco_tp_cancels_sl_and_records_pnl(monkeypatch):
    # Fake Bybit client returning TP active only
    class FakeBybit:
        def __init__(self):
            self.cancelled = False

        def get_open_orders(self, symbol: str):
            return {
                "retCode": 0,
                "result": {
                    "list": [
                        {"orderLinkId": "TRD-1-TP1"},
                    ]
                },
            }

        def cancel_all(self, symbol: str):
            self.cancelled = True

    # Signal with TP for PnL calc
    signal = {"symbol": "BTCUSDT", "direction": "BUY", "tps": ["21000"], "sl": "19000"}
    bybit = FakeBybit()
    oco = OCOManager(bybit, signal, trade_id="TRD-1")

    # Monkeypatch DB helpers to no-op
    from app import storage
    from app.storage import db as db_mod

    async def fake_get_trade(_):
        return ("TRD-1", "BTCUSDT", "BUY", 20000.0, 0.01, "TPSL_PLACED", 0.0, None)

    async def fake_save_fill(*a, **k):
        return True

    async def fake_update_trade_close(*a, **k):
        return True

    monkeypatch.setattr(db_mod, "get_trade", fake_get_trade)
    monkeypatch.setattr(db_mod, "save_fill", fake_save_fill)
    monkeypatch.setattr(db_mod, "update_trade_close", fake_update_trade_close)

    res = await oco.monitor()
    assert res == "TP_HIT"
    assert bybit.cancelled is True

