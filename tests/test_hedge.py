import asyncio
from app.trade.fsm import TradeFSM


def test_hedge_demo():
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
	# give hedge monitor time to react (manual log inspection)
	asyncio.run(asyncio.sleep(15))