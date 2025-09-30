import pytest
from decimal import Decimal
from app.trade.hedge import HedgeReentryManager


@pytest.mark.asyncio
async def test_hedge_flips_after_2pct_loss(monkeypatch):
    class FakeBybit:
        def __init__(self):
            self.sl_orders = []
            self.entry_orders = []
            self.step = 0

        def get_ticker(self, symbol: str):
            # Price drops by ~3%
            prices = ["100", "98", "97"]
            p = prices[min(self.step, len(prices) - 1)]
            self.step += 1
            return {"retCode": 0, "result": {"list": [{"lastPrice": p}]}}

        def create_sl_order(self, **body):
            self.sl_orders.append(body)
            return {"retCode": 0}

        def create_entry_order(self, **body):
            self.entry_orders.append(body)
            return {"retCode": 0}

    bybit = FakeBybit()
    h = HedgeReentryManager(bybit, trade_id="TRD-H", symbol="BTCUSDT", direction="BUY", leverage=5)

    # Speed up loop
    async def fast_sleep(_):
        return None

    monkeypatch.setattr("asyncio.sleep", fast_sleep)

    import asyncio

    async def run_short():
        await h.monitor(entry_price=Decimal("100"), qty="0.01")

    task = asyncio.create_task(run_short())
    await asyncio.sleep(0)
    task.cancel()

    assert len(bybit.sl_orders) >= 1
    assert len(bybit.entry_orders) >= 1

