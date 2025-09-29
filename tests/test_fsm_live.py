import asyncio
from app.trade.fsm import TradeFSM


def test_live_entries():
    signal = {
        "symbol": "BTCUSDT",
        "direction": "BUY",
        "entries": [20000, 20100],  # pick near current price
        "tps": [],
        "sl": None,
        "leverage": 5,
    }
    fsm = TradeFSM(signal)
    asyncio.run(fsm.set_leverage())
    asyncio.run(fsm.place_entries())
    assert fsm.state.name == "ENTRIES_PLACED"