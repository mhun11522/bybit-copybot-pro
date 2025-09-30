import asyncio
import pytest
from app.bybit.client import BybitClient


def test_entry_orders_are_limit_postonly_reduceonly_false(monkeypatch):
    captured = {}

    def fake_post(path: str, body: dict):
        captured["path"] = path
        captured["body"] = body
        return {"retCode": 0, "result": {"orderId": "X", "orderLinkId": body.get("orderLinkId", "L")}}

    client = BybitClient()
    monkeypatch.setattr(client, "_post", fake_post)

    resp = client.create_entry_order(
        symbol="BTCUSDT",
        side="Buy",
        qty="0.01",
        price="20000",
        trade_id="TRD-TEST",
        entry_no=1,
    )

    assert resp.get("retCode") == 0
    assert captured["path"] == "/v5/order/create"
    body = captured["body"]
    assert body["orderType"] == "Limit"
    assert body["timeInForce"] == "PostOnly"
    assert body["reduceOnly"] is False
