"""Test suite for advanced strategies."""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from app.strategies.breakeven_v2 import BreakevenStrategyV2
from app.strategies.pyramid_v2 import PyramidStrategyV2
from app.strategies.trailing_v2 import TrailingStopStrategyV2
from app.strategies.hedge_v2 import HedgeStrategyV2
from app.strategies.reentry_v2 import ReentryStrategyV2

class TestBreakevenStrategy:
    """Test breakeven strategy."""
    
    @pytest.fixture
    def breakeven_strategy(self):
        """Create breakeven strategy instance."""
        return BreakevenStrategyV2("TEST_TRADE", "MOVEUSDT", "BUY", "TEST_CHANNEL")
    
    @pytest.mark.asyncio
    async def test_breakeven_activation(self, breakeven_strategy):
        """Test breakeven activation at TP2 trigger."""
        # Mock Bybit client
        breakeven_strategy.bybit.place_order = AsyncMock(return_value={"retCode": 0})
        
        # Test activation at 0.15% gain
        current_price = Decimal("1.0015")  # 0.15% above entry
        avg_entry = Decimal("1.0000")
        
        result = await breakeven_strategy.check_and_activate(current_price, avg_entry)
        assert result == True, "Breakeven should be activated"
        assert breakeven_strategy.activated == True, "Strategy should be marked as activated"
    
    @pytest.mark.asyncio
    async def test_breakeven_no_activation(self, breakeven_strategy):
        """Test breakeven not activated below trigger."""
        # Test no activation at 0.1% gain (below 0.15% trigger)
        current_price = Decimal("1.0010")  # 0.1% above entry
        avg_entry = Decimal("1.0000")
        
        result = await breakeven_strategy.check_and_activate(current_price, avg_entry)
        assert result == False, "Breakeven should not be activated"
        assert breakeven_strategy.activated == False, "Strategy should not be marked as activated"

class TestPyramidStrategy:
    """Test pyramid strategy."""
    
    @pytest.fixture
    def pyramid_strategy(self):
        """Create pyramid strategy instance."""
        return PyramidStrategyV2("TEST_TRADE", "MOVEUSDT", "BUY", Decimal("1.0000"), "TEST_CHANNEL")
    
    @pytest.mark.asyncio
    async def test_pyramid_level_1_5(self, pyramid_strategy):
        """Test pyramid level at +1.5%."""
        # Mock Bybit client
        pyramid_strategy.bybit.place_order = AsyncMock(return_value={"retCode": 0})
        pyramid_strategy.bybit.set_leverage = AsyncMock(return_value={"retCode": 0})
        
        # Test activation at +1.5%
        current_price = Decimal("1.0150")  # 1.5% above original entry
        
        result = await pyramid_strategy.check_and_activate(current_price)
        assert result == True, "Pyramid should be activated"
        assert Decimal("1.5") in pyramid_strategy.activated_levels, "Level 1.5% should be activated"
    
    @pytest.mark.asyncio
    async def test_pyramid_level_2_4(self, pyramid_strategy):
        """Test pyramid level at +2.4% (max leverage)."""
        # Mock Bybit client
        pyramid_strategy.bybit.place_order = AsyncMock(return_value={"retCode": 0})
        pyramid_strategy.bybit.set_leverage = AsyncMock(return_value={"retCode": 0})
        
        # Test activation at +2.4%
        current_price = Decimal("1.0240")  # 2.4% above original entry
        
        result = await pyramid_strategy.check_and_activate(current_price)
        assert result == True, "Pyramid should be activated"
        assert Decimal("2.4") in pyramid_strategy.activated_levels, "Level 2.4% should be activated"

class TestTrailingStopStrategy:
    """Test trailing stop strategy."""
    
    @pytest.fixture
    def trailing_strategy(self):
        """Create trailing stop strategy instance."""
        return TrailingStopStrategyV2("TEST_TRADE", "MOVEUSDT", "BUY", "TEST_CHANNEL")
    
    @pytest.mark.asyncio
    async def test_trailing_activation(self, trailing_strategy):
        """Test trailing stop activation at +6.1%."""
        # Mock Bybit client
        trailing_strategy.bybit.place_order = AsyncMock(return_value={"retCode": 0})
        trailing_strategy.bybit.get_open_orders = AsyncMock(return_value={"result": {"list": []}})
        
        # Test activation at +6.1%
        current_price = Decimal("1.0610")  # 6.1% above original entry
        original_entry = Decimal("1.0000")
        
        result = await trailing_strategy.check_and_update(current_price, original_entry)
        assert result == True, "Trailing should be activated"
        assert trailing_strategy.armed == True, "Trailing should be armed"
    
    @pytest.mark.asyncio
    async def test_trailing_update(self, trailing_strategy):
        """Test trailing stop update."""
        # Mock Bybit client
        trailing_strategy.bybit.place_order = AsyncMock(return_value={"retCode": 0})
        
        # First activate trailing
        current_price = Decimal("1.0610")  # 6.1% above original entry
        original_entry = Decimal("1.0000")
        await trailing_strategy.check_and_update(current_price, original_entry)
        
        # Then test update with higher price
        higher_price = Decimal("1.0700")  # 7% above original entry
        result = await trailing_strategy.check_and_update(higher_price, original_entry)
        assert result == True, "Trailing should be updated"
        assert trailing_strategy.highest_price == higher_price, "Highest price should be updated"

class TestHedgeStrategy:
    """Test hedge strategy."""
    
    @pytest.fixture
    def hedge_strategy(self):
        """Create hedge strategy instance."""
        return HedgeStrategyV2("TEST_TRADE", "MOVEUSDT", "BUY", "TEST_CHANNEL")
    
    @pytest.mark.asyncio
    async def test_hedge_activation(self, hedge_strategy):
        """Test hedge activation at -2%."""
        # Mock Bybit client
        hedge_strategy.bybit.place_order = AsyncMock(return_value={"retCode": 0})
        hedge_strategy.bybit.positions = AsyncMock(return_value={
            "result": {"list": [{"size": "100", "avgPrice": "1.0000"}]}
        })
        
        # Test activation at -2%
        current_price = Decimal("0.9800")  # 2% below original entry
        original_entry = Decimal("1.0000")
        
        result = await hedge_strategy.check_and_activate(current_price, original_entry)
        assert result == True, "Hedge should be activated"
        assert hedge_strategy.activated == True, "Hedge should be marked as activated"
        assert hedge_strategy.hedge_size == Decimal("100"), "Hedge size should be set"

class TestReentryStrategy:
    """Test re-entry strategy."""
    
    @pytest.fixture
    def reentry_strategy(self):
        """Create re-entry strategy instance."""
        return ReentryStrategyV2("TEST_TRADE", "MOVEUSDT", "BUY", Decimal("1.0000"), "TEST_CHANNEL")
    
    @pytest.mark.asyncio
    async def test_reentry_attempt(self, reentry_strategy):
        """Test re-entry attempt."""
        # Mock Bybit client
        reentry_strategy.bybit.place_order = AsyncMock(return_value={"retCode": 0})
        reentry_strategy.bybit.positions = AsyncMock(return_value={
            "result": {"list": [{"size": "100", "avgPrice": "1.0000"}]}
        })
        
        # Test re-entry with 0.5% price movement
        current_price = Decimal("1.0050")  # 0.5% above last entry
        
        result = await reentry_strategy.attempt_reentry(current_price)
        assert result == True, "Re-entry should be attempted"
        assert reentry_strategy.attempts == 1, "Attempt count should be incremented"
    
    def test_max_attempts(self, reentry_strategy):
        """Test maximum re-entry attempts."""
        reentry_strategy.attempts = 3  # Set to max attempts
        
        assert reentry_strategy.can_attempt_more() == False, "Should not allow more attempts"
        assert reentry_strategy.get_attempts_remaining() == 0, "Should have 0 attempts remaining"

if __name__ == "__main__":
    pytest.main([__file__])
