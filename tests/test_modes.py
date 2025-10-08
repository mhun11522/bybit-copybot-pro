#!/usr/bin/env python3
"""Test trading modes and environment detection."""

import importlib
from importlib import reload
import os

def test_is_dry_run_logic(monkeypatch):
    """Test dry run mode detection."""
    monkeypatch.setenv("TRADING_MODE", "DRY_RUN")
    mod = importlib.import_module("app.config.trading_config")
    reload(mod)
    assert mod.is_dry_run() is True
    assert mod.is_live_trading() is False

def test_is_live_logic(monkeypatch):
    """Test live trading mode detection."""
    monkeypatch.setenv("TRADING_MODE", "LIVE")
    mod = importlib.import_module("app.config.trading_config")
    reload(mod)
    assert mod.is_dry_run() is False
    assert mod.is_live_trading() is True

def test_demo_detection(monkeypatch):
    """Test demo environment detection."""
    monkeypatch.setenv("TRADING_ENV", "testnet")
    from app.core.demo_config import DemoConfig
    assert DemoConfig.is_demo_environment() is True

def test_demo_detection_endpoint(monkeypatch):
    """Test demo environment detection via endpoint."""
    monkeypatch.setenv("BYBIT_ENDPOINT", "https://api-testnet.bybit.com")
    from app.core.demo_config import DemoConfig
    assert DemoConfig.is_demo_environment() is True

if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
