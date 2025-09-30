from decimal import Decimal
from app.trade.risk import qty_for_2pct_risk


def test_two_percent_risk_example(monkeypatch):
    # Mock wallet equity to 1000 USDT
    from app import trade as trade_pkg
    from app.trade import risk as risk_mod

    def fake_equity():
        return Decimal("1000")

    monkeypatch.setattr(risk_mod, "wallet_equity_usdt", fake_equity)

    qty = qty_for_2pct_risk("BTCUSDT", Decimal("20000"), Decimal("19000"))
    # 1000 * 0.02 / 1000 = 0.02 → allow tick/step rounding elsewhere
    assert qty > Decimal("0.015") and qty < Decimal("0.03")
