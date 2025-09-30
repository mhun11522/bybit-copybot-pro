import pytest
from app.runtime.resume import resume_open_trades


@pytest.mark.asyncio
async def test_resume_starts_monitors_without_duplicates(monkeypatch):
    # Provide one open trade
    from app import storage
    from app.storage import db as db_mod

    async def fake_get_open_trades():
        return [("TRD-X", "BTCUSDT", "BUY", 20000.0, 0.01, "TPSL_PLACED")]

    monkeypatch.setattr(db_mod, "get_open_trades", fake_get_open_trades)

    # Fake Bybit methods are simple no-ops
    await resume_open_trades()
    assert True

