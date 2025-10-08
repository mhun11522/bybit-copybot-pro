"""
Unit tests for CLIENT SPECIFICATION compliance.

Tests all leverage rules and pyramid steps exactly as specified by client.
"""

import pytest
import os
import sys
from decimal import Decimal
from dotenv import load_dotenv

# Load environment variables for testing
load_dotenv()

# Set minimal required env vars if not present (for testing only)
os.environ.setdefault("BYBIT_API_KEY", "test_key")
os.environ.setdefault("BYBIT_API_SECRET", "test_secret")
os.environ.setdefault("TELEGRAM_API_ID", "12345")
os.environ.setdefault("TELEGRAM_API_HASH", "test_hash")

from app.core.leverage_policy import LeveragePolicy
from app.core.strict_config import STRICT_CONFIG


class TestLeverageRules:
    """Test exact leverage rules from client specification."""
    
    def test_swing_exactly_6x(self):
        """SWING must be EXACTLY 6x, no variation."""
        # Test with different inputs - all must return 6x
        leverage, mode = LeveragePolicy.classify_leverage("SWING", has_sl=True, raw_leverage=None)
        assert leverage == Decimal("6"), "SWING must be exactly 6x"
        assert mode == "SWING"
        
        # Even if raw leverage is provided, SWING must be 6x
        leverage, mode = LeveragePolicy.classify_leverage("SWING", has_sl=True, raw_leverage=Decimal("8"))
        assert leverage == Decimal("6"), "SWING must ignore raw leverage and be exactly 6x"
    
    def test_fast_exactly_10x(self):
        """FAST must be EXACTLY 10x."""
        leverage, mode = LeveragePolicy.classify_leverage("FAST", has_sl=True, raw_leverage=None)
        assert leverage == Decimal("10"), "FAST must be exactly 10x"
        assert mode == "FAST"
    
    def test_missing_sl_forces_fast_10x(self):
        """Missing SL must force FAST 10x."""
        leverage, mode = LeveragePolicy.classify_leverage("DYNAMIC", has_sl=False, raw_leverage=None)
        assert leverage == Decimal("10"), "Missing SL must force FAST 10x"
        assert mode == "FAST"
    
    def test_dynamic_minimum_7_5x(self):
        """DYNAMIC must be >= 7.5x."""
        # Test with low raw leverage
        leverage, mode = LeveragePolicy.classify_leverage("DYNAMIC", has_sl=True, raw_leverage=Decimal("5"))
        assert leverage >= Decimal("7.5"), "DYNAMIC must be >= 7.5x"
        assert mode == "DYNAMIC"
    
    def test_dynamic_maximum_25x(self):
        """DYNAMIC must be <= 25x."""
        # Test with high raw leverage
        leverage, mode = LeveragePolicy.classify_leverage("DYNAMIC", has_sl=True, raw_leverage=Decimal("60"))
        assert leverage <= Decimal("25"), "DYNAMIC must be <= 25x"
        assert mode == "DYNAMIC"
    
    def test_forbidden_gap_closed(self):
        """Values in (6, 7.5) must be promoted to 7.5x."""
        test_values = [Decimal("6.1"), Decimal("6.5"), Decimal("7.0"), Decimal("7.4")]
        
        for val in test_values:
            leverage, mode = LeveragePolicy.classify_leverage("DYNAMIC", has_sl=True, raw_leverage=val)
            assert leverage == Decimal("7.5"), f"Leverage {val}x in forbidden gap must be promoted to 7.5x"
            assert mode == "DYNAMIC"
    
    def test_forbidden_gap_detection(self):
        """Test forbidden gap detection."""
        assert LeveragePolicy.is_forbidden_gap(Decimal("6.5")) is True
        assert LeveragePolicy.is_forbidden_gap(Decimal("7.0")) is True
        assert LeveragePolicy.is_forbidden_gap(Decimal("6.0")) is False  # Exactly 6 is OK (SWING)
        assert LeveragePolicy.is_forbidden_gap(Decimal("7.5")) is False  # Exactly 7.5 is OK (DYNAMIC min)
    
    def test_dynamic_bounds(self):
        """Test DYNAMIC leverage bounds [7.5, 25]."""
        # Test within bounds
        leverage, mode = LeveragePolicy.classify_leverage("DYNAMIC", has_sl=True, raw_leverage=Decimal("15"))
        assert Decimal("7.5") <= leverage <= Decimal("25")
        assert mode == "DYNAMIC"


class TestPyramidSteps:
    """Test exact pyramid step thresholds from client specification."""
    
    def test_pyramid_step_thresholds(self):
        """Test all 7 pyramid step thresholds are correct."""
        expected_thresholds = [
            Decimal("1.5"),   # Step 1
            Decimal("2.3"),   # Step 2
            Decimal("2.4"),   # Step 3
            Decimal("2.5"),   # Step 4
            Decimal("4.0"),   # Step 5
            Decimal("6.0"),   # Step 6
            Decimal("8.1"),   # Step 7 (FIXED from 8.6%)
        ]
        
        for i, level in enumerate(STRICT_CONFIG.pyramid_levels):
            assert level["trigger"] == expected_thresholds[i], \
                f"Pyramid step {i+1} must trigger at {expected_thresholds[i]}%"
    
    def test_step1_im_total_20(self):
        """Step 1 (+1.5%): IM total to 20 USDT."""
        step1 = STRICT_CONFIG.pyramid_levels[0]
        assert step1["trigger"] == Decimal("1.5")
        assert step1["action"] == "im_total"
        assert step1["target_im"] == 20
    
    def test_step2_sl_breakeven(self):
        """Step 2 (+2.3%): SL to breakeven."""
        step2 = STRICT_CONFIG.pyramid_levels[1]
        assert step2["trigger"] == Decimal("2.3")
        assert step2["action"] == "sl_breakeven"
    
    def test_step3_set_full_leverage(self):
        """Step 3 (+2.4%): Set full leverage (ETH=50x cap)."""
        step3 = STRICT_CONFIG.pyramid_levels[2]
        assert step3["trigger"] == Decimal("2.4")
        assert step3["action"] == "set_full_leverage"
    
    def test_step4_im_total_40(self):
        """Step 4 (+2.5%): IM total to 40 USDT."""
        step4 = STRICT_CONFIG.pyramid_levels[3]
        assert step4["trigger"] == Decimal("2.5")
        assert step4["action"] == "im_total"
        assert step4["target_im"] == 40
    
    def test_step5_im_total_60(self):
        """Step 5 (+4.0%): IM total to 60 USDT."""
        step5 = STRICT_CONFIG.pyramid_levels[4]
        assert step5["trigger"] == Decimal("4.0")
        assert step5["action"] == "im_total"
        assert step5["target_im"] == 60
    
    def test_step6_im_total_80(self):
        """Step 6 (+6.0%): IM total to 80 USDT."""
        step6 = STRICT_CONFIG.pyramid_levels[5]
        assert step6["trigger"] == Decimal("6.0")
        assert step6["action"] == "im_total"
        assert step6["target_im"] == 80
    
    def test_step7_im_total_100(self):
        """Step 7 (+8.1%): IM total to 100 USDT (FIXED from 8.6%)."""
        step7 = STRICT_CONFIG.pyramid_levels[6]
        assert step7["trigger"] == Decimal("8.1"), "Step 7 must be 8.1% (not 8.6%)"
        assert step7["action"] == "im_total"
        assert step7["target_im"] == 100


class TestTrailingStop:
    """Test trailing stop thresholds from client specification."""
    
    def test_trailing_trigger_6_1_percent(self):
        """Trailing must activate at +6.1% (not 8.6%)."""
        assert STRICT_CONFIG.trailing_trigger == Decimal("6.1"), \
            "Trailing must activate at 6.1% (client spec)"
    
    def test_trailing_distance_2_5_percent(self):
        """Trailing must maintain 2.5% distance."""
        assert STRICT_CONFIG.trailing_distance == Decimal("2.5"), \
            "Trailing must maintain 2.5% distance (client spec)"


class TestLeverageValidation:
    """Test leverage validation against client policy."""
    
    def test_swing_validation(self):
        """SWING validation must only accept 6x."""
        assert LeveragePolicy.validate_leverage(Decimal("6"), "SWING") is True
        assert LeveragePolicy.validate_leverage(Decimal("5.9"), "SWING") is False
        assert LeveragePolicy.validate_leverage(Decimal("6.1"), "SWING") is False
    
    def test_fast_validation(self):
        """FAST validation must only accept 10x."""
        assert LeveragePolicy.validate_leverage(Decimal("10"), "FAST") is True
        assert LeveragePolicy.validate_leverage(Decimal("9.9"), "FAST") is False
        assert LeveragePolicy.validate_leverage(Decimal("10.1"), "FAST") is False
    
    def test_dynamic_validation(self):
        """DYNAMIC validation must accept [7.5, 25]."""
        assert LeveragePolicy.validate_leverage(Decimal("7.5"), "DYNAMIC") is True
        assert LeveragePolicy.validate_leverage(Decimal("15"), "DYNAMIC") is True
        assert LeveragePolicy.validate_leverage(Decimal("25"), "DYNAMIC") is True
        assert LeveragePolicy.validate_leverage(Decimal("7.4"), "DYNAMIC") is False
        assert LeveragePolicy.validate_leverage(Decimal("25.1"), "DYNAMIC") is False


class TestCalculationDetails:
    """Test calculation details between 6 and 7.5."""
    
    def test_calc_6_8_promotes_to_7_5(self):
        """Calculated 6.8x must promote to 7.5x."""
        leverage = LeveragePolicy._calculate_dynamic_leverage(Decimal("6.8"))
        assert leverage == Decimal("7.5"), "6.8x must promote to 7.5x"
    
    def test_calc_7_0_promotes_to_7_5(self):
        """Calculated 7.0x must promote to 7.5x."""
        leverage = LeveragePolicy._calculate_dynamic_leverage(Decimal("7.0"))
        assert leverage == Decimal("7.5"), "7.0x must promote to 7.5x"
    
    def test_calc_5_2_promotes_to_7_5(self):
        """Calculated 5.2x must promote to 7.5x (< minimum)."""
        leverage = LeveragePolicy._calculate_dynamic_leverage(Decimal("5.2"))
        assert leverage == Decimal("7.5"), "5.2x must promote to 7.5x (minimum)"
    
    def test_calc_22_stays_22(self):
        """Calculated 22x within bounds stays 22x."""
        leverage = LeveragePolicy._calculate_dynamic_leverage(Decimal("22"))
        assert leverage == Decimal("22"), "22x is valid, must stay 22x"
    
    def test_calc_60_caps_at_25(self):
        """Calculated 60x must cap at 25x."""
        leverage = LeveragePolicy._calculate_dynamic_leverage(Decimal("60"))
        assert leverage == Decimal("25"), "60x must cap at 25x (maximum)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

