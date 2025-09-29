import asyncio
from app.trade.fsm import TradeFSM


def test_fsm_run():
    signal = {
        "symbol": "BICOUSDT",
        "direction": "BUY",
        "entries": [0.0868, 0.0901],
        "tps": [0.0920],
        "sl": 0.0840,
        "leverage": 10,
    }
    fsm = TradeFSM(signal, bybit_client=None, telegram_client=None)
    asyncio.run(fsm.run())
    assert fsm.state.name == "DONE"