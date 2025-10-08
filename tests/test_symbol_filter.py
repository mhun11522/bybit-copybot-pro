#!/usr/bin/env python3
"""Test symbol registry filtering."""

import asyncio
import types
from decimal import Decimal
from app.core.symbol_registry import SymbolRegistry

class FakeClient:
    """Fake Bybit client for testing."""
    
    async def instruments(self, category, symbol):
        """Return fake instrument data."""
        return {"retCode": 0, "result": {"list": [
            {
                "symbol": "BTCUSDT", 
                "status": "Trading", 
                "lotSizeFilter": {"minOrderQty": "0.001", "maxOrderQty": "1000000", "qtyStep": "0.001", "minNotionalValue": "5"},
                "priceFilter": {"tickSize": "0.01"},
                "leverageFilter": {"maxLeverage": "50"}
            },
            {
                "symbol": "ETHUSD", 
                "status": "Trading", 
                "lotSizeFilter": {"minOrderQty": "0.001", "maxOrderQty": "1000000", "qtyStep": "0.001", "minNotionalValue": "5"},
                "priceFilter": {"tickSize": "0.01"},
                "leverageFilter": {"maxLeverage": "50"}
            },
            {
                "symbol": "ETHUSDT", 
                "status": "Trading", 
                "lotSizeFilter": {"minOrderQty": "0.001", "maxOrderQty": "1000000", "qtyStep": "0.001", "minNotionalValue": "5"},
                "priceFilter": {"tickSize": "0.01"},
                "leverageFilter": {"maxLeverage": "50"}
            },
            {
                "symbol": "BTCUSD", 
                "status": "Trading", 
                "lotSizeFilter": {"minOrderQty": "0.001", "maxOrderQty": "1000000", "qtyStep": "0.001", "minNotionalValue": "5"},
                "priceFilter": {"tickSize": "0.01"},
                "leverageFilter": {"maxLeverage": "50"}
            }
        ]}}

async def _get_bybit_client(self):
    """Fake client getter."""
    return FakeClient()

def test_usdt_only_filter(monkeypatch):
    """Test that only USDT symbols are included."""
    reg = SymbolRegistry()
    monkeypatch.setattr(SymbolRegistry, "_get_bybit_client", _get_bybit_client, raising=False)
    
    # Run the async function
    symbols = asyncio.get_event_loop().run_until_complete(reg._fetch_symbols())
    
    # Should include USDT symbols
    assert "BTCUSDT" in symbols
    assert "ETHUSDT" in symbols
    
    # Should exclude non-USDT symbols
    assert "ETHUSD" not in symbols
    assert "BTCUSD" not in symbols

def test_symbol_info_creation():
    """Test that SymbolInfo objects are created correctly."""
    from app.core.symbol_registry import SymbolInfo
    
    fake_data = {
        "symbol": "BTCUSDT",
        "status": "Trading",
        "lotSizeFilter": {"minOrderQty": "0.001", "maxOrderQty": "1000000", "qtyStep": "0.001", "minNotionalValue": "5"},
        "priceFilter": {"tickSize": "0.01"},
        "leverageFilter": {"maxLeverage": "50"}
    }
    
    info = SymbolInfo("BTCUSDT", fake_data)
    
    assert info.symbol == "BTCUSDT"
    assert info.status == "Trading"
    assert info.is_trading is True
    assert info.min_qty == Decimal("0.001")
    assert info.max_qty == Decimal("1000000")
    assert info.step_size == Decimal("0.001")
    assert info.min_notional == Decimal("5")
    assert info.tick_size == Decimal("0.01")
    assert info.max_leverage == Decimal("50")

if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
