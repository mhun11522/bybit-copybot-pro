import pytest
from decimal import Decimal
from app.trade.trailing import TrailingStopManager


@pytest.mark.asyncio
async def test_trailing_moves_sl(monkeypatch):
    # Fake Bybit client with rising price to trigger trailing
    class FakeBybit:
        def __init__(self):
            self.sl_created = []
            self.step = 0

        def get_ticker(self, symbol: str):
            # Simulate +7% move across calls
            prices = ["100", "104", "107"]
            p = prices[min(self.step, len(prices) - 1)]
            self.step += 1
            return {"retCode": 0, "result": {"list": [{"lastPrice": p}]}}

        def create_sl_order(self, **body):
            self.sl_created.append(body)
            return {"retCode": 0}

    bybit = FakeBybit()
    m = TrailingStopManager(bybit, trade_id="TRD-T", symbol="BTCUSDT", direction="BUY", sl_price=None)

    # Run a few loops of monitor
    import asyncio

    async def run_short():
        await m.monitor(entry_price=Decimal("100"), qty="0.01")

    # Monkeypatch sleep to fast-forward
    async def fast_sleep(_):
        return None

    monkeypatch.setattr("asyncio.sleep", fast_sleep)

    # Let it run briefly
    task = asyncio.create_task(run_short())
    await asyncio.sleep(0)  # allow to schedule
    # Stop after a couple loops
    task.cancel()
    assert len(bybit.sl_created) >= 1

