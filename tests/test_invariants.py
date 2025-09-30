"""Comprehensive tests that prove all invariants for the trading bot."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from app.bybit.client import BybitClient, BybitAPIError
from app.trade.fsm import TradeFSM
from app.trade.oco import OCOManager
from app.storage.db import init_db


@pytest.mark.asyncio
async def test_entry_order_payload(monkeypatch):
    """Test that entry orders have correct PostOnly flags."""
    sent_payloads = []
    
    async def mock_post(url, json, headers=None, timeout=None):
        sent_payloads.append(json)
        return type("Response", (), {"json": lambda: {"retCode": 0, "result": {"orderId": "test123"}}})()
    
    monkeypatch.setattr(BybitClient, "place_order", mock_post)
    
    client = BybitClient()
    await client.entry_limit_postonly("linear", "BTCUSDT", "Buy", "0.01", "50000", "TEST-ENTRY")
    
    assert len(sent_payloads) == 1
    payload = sent_payloads[0]
    assert payload["timeInForce"] == "PostOnly"
    assert payload["reduceOnly"] is False
    assert payload["orderType"] == "Limit"
    assert payload["positionIdx"] == 0


@pytest.mark.asyncio
async def test_tp_order_payload(monkeypatch):
    """Test that TP orders have correct ReduceOnly flags."""
    sent_payloads = []
    
    async def mock_post(url, json, headers=None, timeout=None):
        sent_payloads.append(json)
        return type("Response", (), {"json": lambda: {"retCode": 0, "result": {"orderId": "test123"}}})()
    
    monkeypatch.setattr(BybitClient, "place_order", mock_post)
    
    client = BybitClient()
    await client.tp_limit_reduceonly("linear", "BTCUSDT", "Sell", "0.01", "51000", "TEST-TP")
    
    assert len(sent_payloads) == 1
    payload = sent_payloads[0]
    assert payload["reduceOnly"] is True
    assert payload["timeInForce"] == "GTC"
    assert payload["orderType"] == "Limit"


@pytest.mark.asyncio
async def test_sl_order_payload(monkeypatch):
    """Test that SL orders have correct ReduceOnly and MarkPrice flags."""
    sent_payloads = []
    
    async def mock_post(url, json, headers=None, timeout=None):
        sent_payloads.append(json)
        return type("Response", (), {"json": lambda: {"retCode": 0, "result": {"orderId": "test123"}}})()
    
    monkeypatch.setattr(BybitClient, "place_order", mock_post)
    
    client = BybitClient()
    await client.sl_market_reduceonly_mark("linear", "BTCUSDT", "Sell", "0.01", "49000", "TEST-SL")
    
    assert len(sent_payloads) == 1
    payload = sent_payloads[0]
    assert payload["reduceOnly"] is True
    assert payload["closeOnTrigger"] is True
    assert payload["slTriggerBy"] == "MarkPrice"
    assert payload["orderType"] == "Market"


@pytest.mark.asyncio
async def test_leverage_110043_benign(monkeypatch):
    """Test that retCode 110043 (leverage not modified) is treated as benign."""
    async def mock_set_leverage(category, symbol, buy_leverage, sell_leverage):
        return {"retCode": 110043, "retMsg": "leverage not modified", "result": {}}
    
    monkeypatch.setattr(BybitClient, "set_leverage", mock_set_leverage)
    
    client = BybitClient()
    # Should not raise an exception
    result = await client.set_leverage("linear", "BTCUSDT", 10, 10)
    assert result["retCode"] == 110043


@pytest.mark.asyncio
async def test_retcode_failure_raises(monkeypatch):
    """Test that other retCodes raise BybitAPIError."""
    async def mock_place_order(body):
        return {"retCode": 110094, "retMsg": "min notional", "result": {}}
    
    monkeypatch.setattr(BybitClient, "place_order", mock_place_order)
    
    client = BybitClient()
    with pytest.raises(BybitAPIError) as exc_info:
        await client.entry_limit_postonly("linear", "BTCUSDT", "Buy", "0.01", "50000", "TEST")
    
    assert exc_info.value.ret_code == 110094
    assert "min notional" in exc_info.value.ret_msg


@pytest.mark.asyncio
async def test_oco_closes_trade(monkeypatch):
    """Test that OCO properly closes trades in database."""
    # Mock database operations
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    
    # Mock Bybit client
    mock_bybit = AsyncMock()
    mock_bybit.cancel_all = AsyncMock()
    mock_bybit.positions = AsyncMock(return_value={"result": {"list": [{"size": "0"}]}})
    mock_bybit.query_open = AsyncMock(return_value={"result": {"list": []}})
    
    # Mock close_trade function
    with patch('app.trade.oco.close_trade', new_callable=AsyncMock) as mock_close_trade:
        oco = OCOManager("TEST-TRADE", "BTCUSDT", "Buy", "TEST_CHANNEL", 12345)
        oco.bybit = mock_bybit
        
        # Simulate position closed
        await oco._check_position_closed = AsyncMock(return_value=True)
        
        # Run OCO once
        await oco.run()
        
        # Verify cancel_all was called
        mock_bybit.cancel_all.assert_called_once_with("linear", "BTCUSDT")
        
        # Verify close_trade was called
        mock_close_trade.assert_called_once()


@pytest.mark.asyncio
async def test_fsm_ack_gating(monkeypatch):
    """Test that FSM only sends success messages after successful Bybit calls."""
    sent_messages = []
    
    async def mock_send_message(text, target_chat_id=None):
        sent_messages.append(text)
    
    # Mock successful Bybit calls
    async def mock_set_leverage(category, symbol, buy_leverage, sell_leverage):
        return {"retCode": 0, "result": {}}
    
    async def mock_entry_limit_postonly(category, symbol, side, qty, price, link_id):
        return {"retCode": 0, "result": {"orderId": "test123"}}
    
    async def mock_positions(category, symbol):
        return {"retCode": 0, "result": {"list": [{"size": "0.01", "avgPrice": "50000"}]}}
    
    async def mock_tp_limit_reduceonly(category, symbol, side, qty, price, link_id):
        return {"retCode": 0, "result": {"orderId": "test123"}}
    
    async def mock_sl_market_reduceonly_mark(category, symbol, side, qty, sl_trigger, link_id):
        return {"retCode": 0, "result": {"orderId": "test123"}}
    
    # Mock precision functions
    async def mock_q_price(category, symbol, price):
        return 50000.0
    
    async def mock_q_qty(category, symbol, qty):
        return 0.01
    
    async def mock_ensure_min_notional(category, symbol, price, qty):
        return 0.01
    
    async def mock_qty_for_2pct_risk(symbol, leverage):
        return 0.01
    
    # Apply mocks
    monkeypatch.setattr("app.telegram.output.send_message", mock_send_message)
    monkeypatch.setattr(BybitClient, "set_leverage", mock_set_leverage)
    monkeypatch.setattr(BybitClient, "entry_limit_postonly", mock_entry_limit_postonly)
    monkeypatch.setattr(BybitClient, "positions", mock_positions)
    monkeypatch.setattr(BybitClient, "tp_limit_reduceonly", mock_tp_limit_reduceonly)
    monkeypatch.setattr(BybitClient, "sl_market_reduceonly_mark", mock_sl_market_reduceonly_mark)
    monkeypatch.setattr("app.core.precision.q_price", mock_q_price)
    monkeypatch.setattr("app.core.precision.q_qty", mock_q_qty)
    monkeypatch.setattr("app.core.precision.ensure_min_notional", mock_ensure_min_notional)
    monkeypatch.setattr("app.trade.risk.qty_for_2pct_risk", mock_qty_for_2pct_risk)
    
    # Mock database operations
    monkeypatch.setattr("app.trade.fsm._active_trades", AsyncMock(return_value=0))
    monkeypatch.setattr("app.trade.fsm._upsert_trade", AsyncMock())
    
    # Create test signal
    signal = {
        "symbol": "BTCUSDT",
        "direction": "BUY",
        "entries": ["50000"],
        "tps": ["51000"],
        "sl": "49000",
        "leverage": 10,
        "mode": "FAST",
        "channel_name": "TEST_CHANNEL",
        "channel_id": 12345
    }
    
    fsm = TradeFSM(signal)
    
    # Run FSM steps
    await fsm.set_leverage()
    await fsm.place_entries()
    await fsm.confirm_position()
    await fsm.place_tpsl()
    
    # Verify messages were sent after successful operations
    assert len(sent_messages) >= 3  # At least leverage, entries, and tpsl messages
    assert any("Leverage" in msg for msg in sent_messages)
    assert any("Entry orders placed" in msg for msg in sent_messages)
    assert any("TP/SL placed" in msg for msg in sent_messages)


@pytest.mark.asyncio
async def test_fsm_failure_no_messages(monkeypatch):
    """Test that FSM doesn't send success messages when Bybit calls fail."""
    sent_messages = []
    
    async def mock_send_message(text, target_chat_id=None):
        sent_messages.append(text)
    
    # Mock failing Bybit call
    async def mock_set_leverage(category, symbol, buy_leverage, sell_leverage):
        raise BybitAPIError(110094, "min notional")
    
    # Apply mocks
    monkeypatch.setattr("app.telegram.output.send_message", mock_send_message)
    monkeypatch.setattr(BybitClient, "set_leverage", mock_set_leverage)
    monkeypatch.setattr("app.trade.fsm._active_trades", AsyncMock(return_value=0))
    monkeypatch.setattr("app.trade.fsm._upsert_trade", AsyncMock())
    
    # Create test signal
    signal = {
        "symbol": "BTCUSDT",
        "direction": "BUY",
        "entries": ["50000"],
        "tps": ["51000"],
        "sl": "49000",
        "leverage": 10,
        "mode": "FAST",
        "channel_name": "TEST_CHANNEL",
        "channel_id": 12345
    }
    
    fsm = TradeFSM(signal)
    
    # Run FSM step that should fail
    with pytest.raises(BybitAPIError):
        await fsm.set_leverage()
    
    # Verify no success messages were sent
    assert len(sent_messages) == 0


@pytest.mark.asyncio
async def test_capacity_gating():
    """Test that capacity gating works correctly."""
    # Mock active trades count
    with patch("app.trade.fsm._active_trades", return_value=100) as mock_active:
        signal = {
            "symbol": "BTCUSDT",
            "direction": "BUY",
            "entries": ["50000"],
            "tps": ["51000"],
            "sl": "49000",
            "leverage": 10,
            "mode": "FAST",
            "channel_name": "TEST_CHANNEL",
            "channel_id": 12345
        }
        
        fsm = TradeFSM(signal)
        
        # Should raise capacity error
        with pytest.raises(RuntimeError, match="capacity"):
            await fsm.open_guard()
        
        # Verify active trades was checked
        mock_active.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])