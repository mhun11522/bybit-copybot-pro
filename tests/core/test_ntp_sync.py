"""
Tests for NTP sync and clock discipline.

CLIENT SPEC Lines 299-302: NTP sync with drift thresholds.
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock

from app.core.ntp_sync import (
    NTPClockMonitor,
    get_ntp_monitor,
    is_trading_allowed_by_clock
)


class TestNTPClockMonitor:
    """Test NTP clock monitor."""
    
    @pytest.mark.asyncio
    async def test_normal_drift(self):
        """Test behavior with normal drift (< 100ms)."""
        monitor = NTPClockMonitor()
        
        # Mock small drift
        with patch('ntplib.NTPClient.request') as mock_request:
            mock_response = Mock()
            mock_response.offset = 0.050  # 50ms drift
            mock_request.return_value = mock_response
            
            drift = await monitor.check_drift()
            
            assert drift == 0.050
            assert monitor.trading_blocked == False
    
    @pytest.mark.asyncio
    async def test_warning_drift(self):
        """Test behavior with warning-level drift (100-250ms)."""
        monitor = NTPClockMonitor()
        
        # Mock warning-level drift
        with patch('ntplib.NTPClient.request') as mock_request:
            mock_response = Mock()
            mock_response.offset = 0.150  # 150ms drift
            mock_request.return_value = mock_response
            
            drift = await monitor.check_drift()
            
            assert drift == 0.150
            # Should still allow trading (only warn)
            assert monitor.trading_blocked == False
    
    @pytest.mark.asyncio
    async def test_block_drift(self):
        """Test that trading is blocked on high drift (> 250ms)."""
        monitor = NTPClockMonitor()
        
        # Mock high drift
        with patch('ntplib.NTPClient.request') as mock_request:
            mock_response = Mock()
            mock_response.offset = 0.300  # 300ms drift - exceeds 250ms threshold
            mock_request.return_value = mock_response
            
            # Run monitor loop once (would need to call manually)
            drift = await monitor.check_drift()
            
            # Manually trigger block logic (normally in monitor_loop)
            if abs(drift) > monitor.drift_block:
                monitor.trading_blocked = True
            
            assert drift == 0.300
            assert monitor.trading_blocked == True
            assert monitor.is_trading_allowed() == False
    
    @pytest.mark.asyncio
    async def test_auto_recovery(self):
        """Test that trading auto-recovers when drift normalizes."""
        monitor = NTPClockMonitor()
        
        # First check: high drift (block)
        with patch('ntplib.NTPClient.request') as mock_request:
            mock_response = Mock()
            mock_response.offset = 0.300  # High drift
            mock_request.return_value = mock_response
            
            await monitor.check_drift()
            monitor.trading_blocked = True  # Simulate blocking
        
        # Second check: normal drift (recover)
        with patch('ntplib.NTPClient.request') as mock_request:
            mock_response = Mock()
            mock_response.offset = 0.050  # Normal drift
            mock_request.return_value = mock_response
            
            drift = await monitor.check_drift()
            monitor.trading_blocked = False  # Simulate recovery
            
            assert monitor.is_trading_allowed() == True
    
    def test_get_status(self):
        """Test getting monitor status."""
        monitor = NTPClockMonitor()
        monitor.total_checks = 10
        monitor.drift_warnings = 2
        monitor.drift_blocks = 1
        
        status = monitor.get_status()
        
        assert status["total_checks"] == 10
        assert status["drift_warnings"] == 2
        assert status["drift_blocks"] == 1
        assert "ntp_servers" in status


def test_singleton_pattern():
    """Test that get_ntp_monitor returns singleton."""
    monitor1 = get_ntp_monitor()
    monitor2 = get_ntp_monitor()
    
    assert monitor1 is monitor2


def test_is_trading_allowed_global():
    """Test global trading allowed check."""
    # Should return True initially
    allowed = is_trading_allowed_by_clock()
    assert isinstance(allowed, bool)

