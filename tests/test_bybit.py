from app.bybit.client import BybitClient


def test_bybit():
    client = BybitClient()
    print("⏱ Server time:", client.get_server_time())
    print("📊 Instrument info:", client.get_instruments_info("BTCUSDT"))
    # NOTE: don't run create_order yet, just test safe calls