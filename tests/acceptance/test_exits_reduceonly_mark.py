import pytest
from app.bybit.client import BybitClient


def test_tp_is_limit_reduceonly(monkeypatch):
    captured = {}

    def fake_post(path: str, body: dict):
        captured["path"] = path
        captured["body"] = body
        return {"retCode": 0, "result": {"orderId": "TPX"}}

    client = BybitClient()
    monkeypatch.setattr(client, "_post", fake_post)
    client.create_tp_order("BTCUSDT", "Sell", "0.01", "21000", "TRD-T", 1)

    assert captured["path"] == "/v5/order/create"
    body = captured["body"]
    assert body["orderType"] == "Limit"
    assert body["reduceOnly"] is True
    assert body["timeInForce"] == "GTC"


def test_sl_is_stop_market_reduceonly_markprice(monkeypatch):
    captured = {}

    def fake_post(path: str, body: dict):
        captured["path"] = path
        captured["body"] = body
        return {"retCode": 0, "result": {"orderId": "SLX"}}

    client = BybitClient()
    monkeypatch.setattr(client, "_post", fake_post)
    client.create_sl_order("BTCUSDT", "Sell", "0.01", "19000", "TRD-S")

    assert captured["path"] == "/v5/order/create"
    body = captured["body"]
    assert body["orderType"] == "Market"
    assert body["reduceOnly"] is True
    assert body["triggerBy"] == "MarkPrice"
