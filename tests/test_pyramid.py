import asyncio
from app.trade.fsm import TradeFSM


def test_pyramid_add():
    signal = {
        "symbol": "BTCUSDT",
        "direction": "BUY",
        "entries": [20000],
        "tps": [21000],
        "sl": 19000,
        "leverage": 5,
    }
    fsm = TradeFSM(signal)
    asyncio.run(fsm.set_leverage())
    asyncio.run(fsm.place_entries())
    asyncio.run(fsm.confirm_position())
    resp = fsm.pyramid.add_entry(price=19950)
    print("Pyramid add resp:", resp)
    assert resp is not None