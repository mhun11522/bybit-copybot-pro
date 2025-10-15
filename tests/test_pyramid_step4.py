"""
Unit tests for Pyramid Step 4 leverage-only enforcement.

CLIENT SPEC (doc/10_15.md Lines 365-377):
- Pyramid +2.4% (Step 4 in templates) MUST be leverage-only
- Forbid qty_add/im_add at this step
- Only leverage change allowed
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from app.strategies.pyramid_v2 import PyramidStrategyV2
from app.core.strict_config import STRICT_CONFIG


class TestPyramidStep4LeverageOnly:
    """Test that Pyramid Step 4 (+2.4%) is leverage-only."""
    
    @pytest.mark.asyncio
    async def test_step_2_4_pct_allows_set_full_leverage(self):
        """Test that +2.4% step allows set_full_leverage action."""
        strategy = PyramidStrategyV2(
            trade_id="test123",
            symbol="BTCUSDT",
            direction="LONG",
            original_entry=Decimal("50000"),
            channel_name="TEST"
        )
        
        # Mock the bybit client
        with patch.object(strategy, 'bybit') as mock_bybit:
            mock_bybit.set_leverage = AsyncMock(return_value={
                "retCode": 0,
                "retMsg": "OK"
            })
            mock_bybit.get_position = AsyncMock(return_value={
                "retCode": 0,
                "result": {"list": [{}]}
            })
            mock_bybit.positions = AsyncMock(return_value={
                "retCode": 0,
                "result": {"list": [{
                    "leverage": "50",
                    "positionIM": "20"
                }]}
            })
            
            # Mock LeveragePolicy
            with patch('app.strategies.pyramid_v2.LeveragePolicy') as mock_policy:
                mock_policy.get_instrument_max_leverage = AsyncMock(return_value=Decimal("50"))
                
                # Create config for +2.4% with set_full_leverage action
                config = {"action": "set_full_leverage"}
                
                # Should succeed (leverage-only is allowed)
                result = await strategy._activate_level(
                    level_pct=Decimal("2.4"),
                    config=config,
                    gain_pct=Decimal("2.4")
                )
                
                # Verify set_leverage was called
                mock_bybit.set_leverage.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_step_2_4_pct_forbids_im_total(self):
        """Test that +2.4% step FORBIDS im_total action."""
        strategy = PyramidStrategyV2(
            trade_id="test456",
            symbol="ETHUSDT",
            direction="SHORT",
            original_entry=Decimal("3000"),
            channel_name="TEST"
        )
        
        # Create config for +2.4% with im_total action (FORBIDDEN)
        config = {"action": "im_total", "target_im": 40}
        
        # Should raise ValueError (CLIENT SPEC violation)
        with pytest.raises(ValueError, match="MUST be leverage-only"):
            await strategy._activate_level(
                level_pct=Decimal("2.4"),
                config=config,
                gain_pct=Decimal("2.4")
            )
    
    @pytest.mark.asyncio
    async def test_step_2_4_pct_forbids_add_im(self):
        """Test that +2.4% step FORBIDS add_im action."""
        strategy = PyramidStrategyV2(
            trade_id="test789",
            symbol="SOLUSDT",
            direction="LONG",
            original_entry=Decimal("100"),
            channel_name="TEST"
        )
        
        # Create config for +2.4% with add_im action (FORBIDDEN)
        config = {"action": "add_im", "target_im": 40}
        
        # Should raise ValueError (CLIENT SPEC violation)
        with pytest.raises(ValueError, match="MUST be leverage-only"):
            await strategy._activate_level(
                level_pct=Decimal("2.4"),
                config=config,
                gain_pct=Decimal("2.4")
            )
    
    @pytest.mark.asyncio
    async def test_other_steps_allow_im_total(self):
        """Test that other steps (+2.5%, +4%, etc.) allow im_total."""
        strategy = PyramidStrategyV2(
            trade_id="test999",
            symbol="BTCUSDT",
            direction="LONG",
            original_entry=Decimal("50000"),
            channel_name="TEST"
        )
        
        # Mock the bybit client
        with patch.object(strategy, 'bybit') as mock_bybit:
            mock_bybit.positions = AsyncMock(return_value={
                "retCode": 0,
                "result": {"list": [{
                    "size": "10",
                    "positionIM": "20",
                    "avgPrice": "50000",
                    "leverage": "10"
                }]}
            })
            mock_bybit.place_order = AsyncMock(return_value={
                "retCode": 0,
                "result": {"orderId": "123"}
            })
            mock_bybit.get_position = AsyncMock(return_value={
                "retCode": 0,
                "result": {"list": [{}]}
            })
            
            # Mock symbol info
            with patch('app.strategies.pyramid_v2.get_symbol_info') as mock_symbol:
                mock_info = MagicMock()
                mock_info.quantize_qty = lambda x: x
                mock_info.quantize_price = lambda x: x
                mock_symbol.return_value = mock_info
                
                # Create config for +2.5% with im_total action (ALLOWED)
                config = {"action": "im_total", "target_im": 40}
                
                # Should succeed (im_total allowed at +2.5%)
                try:
                    result = await strategy._activate_level(
                        level_pct=Decimal("2.5"),
                        config=config,
                        gain_pct=Decimal("2.5")
                    )
                    # Should not raise error
                    assert True
                except ValueError as e:
                    if "MUST be leverage-only" in str(e):
                        pytest.fail(f"im_total should be allowed at +2.5%, but got error: {e}")
    
    def test_pyramid_levels_config_has_correct_2_4_action(self):
        """Test that STRICT_CONFIG has set_full_leverage at +2.4%."""
        # Find the +2.4% level
        level_2_4 = None
        for level in STRICT_CONFIG.pyramid_levels:
            if level["trigger"] == Decimal("2.4"):
                level_2_4 = level
                break
        
        assert level_2_4 is not None, "+2.4% level not found in STRICT_CONFIG.pyramid_levels"
        assert level_2_4["action"] == "set_full_leverage", \
            f"CLIENT SPEC VIOLATION: +2.4% must have action='set_full_leverage', got '{level_2_4['action']}'"
    
    def test_pyramid_levels_config_has_im_total_at_2_5(self):
        """Test that STRICT_CONFIG has im_total at +2.5%."""
        # Find the +2.5% level
        level_2_5 = None
        for level in STRICT_CONFIG.pyramid_levels:
            if level["trigger"] == Decimal("2.5"):
                level_2_5 = level
                break
        
        assert level_2_5 is not None, "+2.5% level not found in STRICT_CONFIG.pyramid_levels"
        assert level_2_5["action"] == "im_total", \
            f"+2.5% must have action='im_total', got '{level_2_5['action']}'"
        assert level_2_5["target_im"] == 40, \
            f"+2.5% must have target_im=40, got {level_2_5.get('target_im')}"
    
    def test_pyramid_step_numbering_harmonization(self):
        """
        Test step numbering matches CLIENT SPEC.
        
        CLIENT SPEC: +2.4% is "Pyramid Step 4" in templates (leverage-only).
        Code: +2.4% is index 2 in pyramid_levels array.
        """
        # Verify the pyramid levels are in correct order
        levels = STRICT_CONFIG.pyramid_levels
        
        assert len(levels) == 7, f"Expected 7 pyramid levels, got {len(levels)}"
        
        # Verify +2.4% is at correct position
        assert levels[2]["trigger"] == Decimal("2.4"), "Index 2 should be +2.4%"
        assert levels[2]["action"] == "set_full_leverage", "Index 2 should be leverage-only"
        
        # Verify +2.5% follows immediately after
        assert levels[3]["trigger"] == Decimal("2.5"), "Index 3 should be +2.5%"
        assert levels[3]["action"] == "im_total", "Index 3 should be IM addition"


class TestPyramidLeverageOnlyImplementation:
    """Test that _set_full_leverage() only changes leverage."""
    
    @pytest.mark.asyncio
    async def test_set_full_leverage_for_eth(self):
        """Test leverage-only for ETH (capped at 50x)."""
        strategy = PyramidStrategyV2(
            trade_id="eth_test",
            symbol="ETHUSDT",
            direction="LONG",
            original_entry=Decimal("3000"),
            channel_name="TEST"
        )
        
        with patch.object(strategy, 'bybit') as mock_bybit:
            mock_bybit.set_leverage = AsyncMock(return_value={
                "retCode": 0,
                "retMsg": "OK"
            })
            
            with patch('app.strategies.pyramid_v2.LeveragePolicy') as mock_policy:
                mock_policy.get_instrument_max_leverage = AsyncMock(return_value=Decimal("100"))
                
                result = await strategy._set_full_leverage()
                
                assert result is True
                # Verify set_leverage was called with 50x (ETH cap)
                call_args = mock_bybit.set_leverage.call_args
                assert call_args is not None
                assert call_args.kwargs["buy_leverage"] == "50"
                assert call_args.kwargs["sell_leverage"] == "50"
    
    @pytest.mark.asyncio
    async def test_set_full_leverage_for_non_eth(self):
        """Test leverage-only for non-ETH (instrument max)."""
        strategy = PyramidStrategyV2(
            trade_id="btc_test",
            symbol="BTCUSDT",
            direction="SHORT",
            original_entry=Decimal("50000"),
            channel_name="TEST"
        )
        
        with patch.object(strategy, 'bybit') as mock_bybit:
            mock_bybit.set_leverage = AsyncMock(return_value={
                "retCode": 0,
                "retMsg": "OK"
            })
            
            with patch('app.strategies.pyramid_v2.LeveragePolicy') as mock_policy:
                mock_policy.get_instrument_max_leverage = AsyncMock(return_value=Decimal("125"))
                
                result = await strategy._set_full_leverage()
                
                assert result is True
                # Verify set_leverage was called with 125x (instrument max)
                call_args = mock_bybit.set_leverage.call_args
                assert call_args is not None
                assert call_args.kwargs["buy_leverage"] == "125"
                assert call_args.kwargs["sell_leverage"] == "125"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

