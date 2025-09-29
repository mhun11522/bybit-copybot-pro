import asyncio
from app.trade.fsm import TradeFSM


def test_trailing_demo():
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
	asyncio.run(fsm.place_tpsl())
	# trailing runs in background, check logs manually
	asyncio.run(asyncio.sleep(5))