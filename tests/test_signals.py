from app.signals.normalizer import parse_signal


def test_basic_signal():
    text = """
    ✳ New FREE signal
    💎 BUY #BICO/USDT
    📈 SPOT TRADE
    🛒 Entry Zone: 0.08683660 - 0.09012328
    🎯 TP1: 0.092000
    🛑 SL: 0.084000
    Leverage 10x
    """
    sig = parse_signal(text)
    print(sig)
    assert sig["symbol"] == "BICOUSDT"
    assert sig["direction"] == "BUY"
    assert len(sig["entries"]) == 2
    assert float(sig["sl"]) == 0.084000