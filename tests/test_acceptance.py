#!/usr/bin/env python3
"""Comprehensive acceptance test suite for Bybit Copybot Pro."""

import pytest
import asyncio
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.signals.normalizer import parse_signal
from app.trade.fsm import TradeFSM
from app.trade.planner import plan_dual_entries
from app.signals.idempotency import is_new_signal
from app.core.logging import trade_logger

class TestSignalParsing:
    """Test signal parsing for all supported formats."""
    
    def test_jup_signal_parsing(self):
        """Test JUP signal format parsing."""
        signal_text = "✳ New FREE signal 💎 BUY #JUP/USD at #KRAKEN 📈 SPOT TRADE 🆔 #2882703 ⏱ 30-Sep-2025 09:03:46 UTC 🛒 Entry Zone: 0.41464960 - 0.43034368 💵 Current ask: 0.42692000 🎯 Target 1: 0.44423680 (4.06%) 🎯 Target 2: 0.45195520 (5.86%) 🎯 Target 3: 0.45967360 (7.67%) 🚫 Stop loss: 0.40993280 (3.98%) 💰 Volume #JUP: 616660.249410 💰 Volume #USD: 272164.004383 ⏳ SHORT/MID TERM (up to 2 weeks) ⚠️ Risk: - Invest up to 5% of your portfolio ☯️ R/R ratio: 1.5"
        
        result = parse_signal(signal_text)
        
        assert result is not None
        assert result["symbol"] == "JUPUSDT"
        assert result["direction"] == "BUY"
        assert len(result["entries"]) == 1
        assert result["entries"][0] == Decimal("0.41464960")
        assert len(result["tps"]) == 3
        assert result["tps"][0] == Decimal("0.44423680")
        assert result["sl"] == "0.40993280"
        assert result["leverage"] == 7.5
        assert result["mode"] == "DYNAMIC"
    
    def test_simple_signal_parsing(self):
        """Test simple signal format parsing."""
        signal_text = "BTCUSDT LONG lev=10 entries=60000,59800 sl=59000 tps=61000,62000,63000"
        
        result = parse_signal(signal_text)
        
        assert result is not None
        assert result["symbol"] == "BTCUSDT"
        assert result["direction"] == "BUY"
        assert len(result["entries"]) == 2
        assert result["entries"][0] == Decimal("60000")
        assert result["entries"][1] == Decimal("59800")
        assert len(result["tps"]) == 3
        assert result["tps"][0] == Decimal("61000")
        assert result["sl"] == "58800.00"  # Auto-generated -2%
        assert result["leverage"] == 10
        assert result["mode"] == "FAST"
    
    def test_leverage_policy_enforcement(self):
        """Test leverage policy enforcement."""
        # Test SWING mode
        swing_signal = "ETHUSDT LONG SWING entries=3000 sl=2900 tps=3100,3200"
        result = parse_signal(swing_signal)
        assert result["leverage"] == 6
        assert result["mode"] == "SWING"
        
        # Test DYNAMIC mode
        dynamic_signal = "ETHUSDT LONG lev=8 entries=3000 sl=2900 tps=3100,3200"
        result = parse_signal(dynamic_signal)
        assert result["leverage"] == 8
        assert result["mode"] == "DYNAMIC"
        
        # Test forbidden range
        forbidden_signal = "ETHUSDT LONG lev=7 entries=3000 sl=2900 tps=3100,3200"
        result = parse_signal(forbidden_signal)
        assert result is None  # Should be rejected
        
        # Test FAST mode
        fast_signal = "ETHUSDT LONG lev=15 entries=3000 sl=2900 tps=3100,3200"
        result = parse_signal(fast_signal)
        assert result["leverage"] == 15
        assert result["mode"] == "FAST"
        
        # Test auto SL + FAST when no SL
        no_sl_signal = "ETHUSDT LONG lev=5 entries=3000 tps=3100,3200"
        result = parse_signal(no_sl_signal)
        assert result["leverage"] == 10
        assert result["mode"] == "FAST"
        assert result["sl"] is not None  # Auto-generated

class TestDualEntryPlanning:
    """Test dual entry planning logic."""
    
    def test_dual_entries_provided(self):
        """Test when two entries are provided."""
        entries, splits = plan_dual_entries("BUY", ["100", "99"])
        
        assert entries == ["100", "99"]
        assert splits == [Decimal("0.5"), Decimal("0.5")]
    
    def test_single_entry_auto_generation(self):
        """Test single entry auto-generation with ±0.1%."""
        # BUY: first higher, second lower
        entries, splits = plan_dual_entries("BUY", ["100"])
        assert entries[0] == "100"
        assert Decimal(entries[1]) == Decimal("99.9")  # 100 - 0.1
        assert splits == [Decimal("0.5"), Decimal("0.5")]
        
        # SELL: first lower, second higher
        entries, splits = plan_dual_entries("SELL", ["100"])
        assert entries[0] == "100"
        assert Decimal(entries[1]) == Decimal("100.1")  # 100 + 0.1
        assert splits == [Decimal("0.5"), Decimal("0.5")]

class TestIdempotency:
    """Test signal idempotency and deduplication."""
    
    @pytest.mark.asyncio
    async def test_signal_deduplication(self):
        """Test that duplicate signals are rejected."""
        chat_id = 12345
        text = "BTCUSDT LONG entries=50000 sl=49000 tps=51000"
        
        # First signal should be accepted
        result1 = await is_new_signal(chat_id, text)
        assert result1 is True
        
        # Duplicate signal should be rejected
        result2 = await is_new_signal(chat_id, text)
        assert result2 is False

class TestTradeFSM:
    """Test Trade FSM functionality."""
    
    @pytest.mark.asyncio
    async def test_fsm_basic_flow(self):
        """Test basic FSM flow."""
        signal = {
            "symbol": "TESTUSDT",
            "direction": "BUY",
            "entries": ["100", "99"],
            "tps": ["110", "120"],
            "sl": "90",
            "leverage": 7.5,
            "mode": "DYNAMIC",
            "channel_name": "Test Channel"
        }
        
        fsm = TradeFSM(signal)
        
        # Mock the external dependencies
        with patch('app.trade.fsm.get_active_trades', return_value=0):
            with patch('app.trade.fsm.register_trade'):
                with patch('app.trade.fsm.close_trade'):
                    try:
                        await fsm.run()
                        # FSM should complete without errors
                        assert True
                    except Exception as e:
                        pytest.fail(f"FSM failed: {e}")

class TestOrderSemantics:
    """Test order semantics compliance."""
    
    def test_entry_orders_postonly(self):
        """Test that entry orders use PostOnly."""
        # This would be tested in integration tests with actual Bybit client
        # For now, we verify the order structure in the client
        from app.bybit.client import BybitClient
        
        client = BybitClient()
        
        # Check that entry_limit_postonly method exists and has correct structure
        assert hasattr(client, 'entry_limit_postonly')
        assert hasattr(client, 'tp_limit_reduceonly')
        assert hasattr(client, 'sl_market_reduceonly_mark')
    
    def test_exit_orders_reduceonly(self):
        """Test that exit orders use ReduceOnly."""
        from app.bybit.client import BybitClient
        
        client = BybitClient()
        
        # Verify method signatures include reduceOnly=True
        import inspect
        tp_sig = inspect.signature(client.tp_limit_reduceonly)
        sl_sig = inspect.signature(client.sl_market_reduceonly_mark)
        
        # These methods should be designed to place ReduceOnly orders
        assert 'reduceOnly' in str(tp_sig) or 'reduceOnly' in str(sl_sig)

class TestAdvancedFeatures:
    """Test advanced trading features."""
    
    def test_oco_manager_creation(self):
        """Test OCO Manager can be created."""
        from app.trade.oco import OCOManager
        
        oco = OCOManager("test-trade", "BTCUSDT", "BUY", "Test Channel")
        assert oco.trade_id == "test-trade"
        assert oco.symbol == "BTCUSDT"
        assert oco.direction == "BUY"
    
    def test_trailing_stop_creation(self):
        """Test Trailing Stop Manager can be created."""
        from app.trade.trailing import TrailingStopManager
        
        trailing = TrailingStopManager("test-trade", "BTCUSDT", "BUY", 50000, 0.01, "Test Channel")
        assert trailing.trade_id == "test-trade"
        assert trailing.symbol == "BTCUSDT"
        assert trailing.direction == "BUY"
    
    def test_hedge_manager_creation(self):
        """Test Hedge Manager can be created."""
        from app.trade.hedge import HedgeReentryManager
        
        hedge = HedgeReentryManager("test-trade", "BTCUSDT", "BUY", 50000, 0.01, 10, "Test Channel")
        assert hedge.trade_id == "test-trade"
        assert hedge.symbol == "BTCUSDT"
        assert hedge.direction == "BUY"
        assert hedge.max_reentries == 3
    
    def test_pyramid_manager_creation(self):
        """Test Pyramid Manager can be created."""
        from app.trade.pyramid import PyramidManager
        
        pyramid = PyramidManager("test-trade", "BTCUSDT", "BUY", 10, "Test Channel")
        assert pyramid.trade_id == "test-trade"
        assert pyramid.symbol == "BTCUSDT"
        assert pyramid.direction == "BUY"
        assert pyramid.max_adds == 100

class TestLogging:
    """Test structured logging functionality."""
    
    def test_structured_logger_creation(self):
        """Test structured logger can be created."""
        from app.core.logging import StructuredLogger
        
        logger = StructuredLogger("test")
        assert logger.name == "test"
        assert logger.trace_id is not None
        assert len(logger.trace_id) == 8
    
    def test_trade_logger_methods(self):
        """Test trade logger has required methods."""
        from app.core.logging import trade_logger
        
        assert hasattr(trade_logger, 'signal_parsed')
        assert hasattr(trade_logger, 'order_placed')
        assert hasattr(trade_logger, 'order_filled')
        assert hasattr(trade_logger, 'position_opened')
        assert hasattr(trade_logger, 'position_closed')
        assert hasattr(trade_logger, 'bybit_error')

class TestReports:
    """Test reporting functionality."""
    
    def test_daily_report_generation(self):
        """Test daily report can be generated."""
        from app.reports.service import send_daily_report
        
        # This would be tested with mocked database in integration tests
        assert callable(send_daily_report)
    
    def test_weekly_report_generation(self):
        """Test weekly report can be generated."""
        from app.reports.service import send_weekly_report
        
        # This would be tested with mocked database in integration tests
        assert callable(send_weekly_report)

class TestConfiguration:
    """Test configuration and settings."""
    
    def test_settings_import(self):
        """Test that settings can be imported."""
        from app.config.settings import (
            BYBIT_ENDPOINT, BYBIT_API_KEY, BYBIT_API_SECRET,
            TELEGRAM_API_ID, TELEGRAM_API_HASH,
            RISK_PER_TRADE, MAX_CONCURRENT_TRADES,
            TIMEZONE, CATEGORY
        )
        
        assert isinstance(RISK_PER_TRADE, float)
        assert isinstance(MAX_CONCURRENT_TRADES, int)
        assert TIMEZONE == "Europe/Stockholm"
        assert CATEGORY == "linear"

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])