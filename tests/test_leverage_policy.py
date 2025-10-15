#!/usr/bin/env python3
"""Test leverage policy enforcement."""

from decimal import Decimal
from app.core.leverage_policy import LeveragePolicy

def test_block_cross_in_signal():
    """Test that cross margin signals are blocked."""
    msg = "Leverage: Cross 50X"
    assert LeveragePolicy.enforce_isolated_margin_only(msg) is True  # Should reject

def test_allow_isolated_margin():
    """Test that isolated margin signals are allowed."""
    msg = "Leverage: 10x"
    assert LeveragePolicy.enforce_isolated_margin_only(msg) is False  # Should allow

def test_exact_modes():
    """Test exact leverage validation for each mode (FAST removed, FIXED added per CLIENT SPEC)."""
    assert LeveragePolicy.validate_leverage(Decimal("6"), "SWING") is True
    assert LeveragePolicy.validate_leverage(Decimal("10"), "FIXED") is True  # Changed from FAST to FIXED
    assert LeveragePolicy.validate_leverage(Decimal("7.5"), "DYNAMIC") is True
    assert LeveragePolicy.validate_leverage(Decimal("7.4"), "DYNAMIC") is False  # Below minimum
    assert LeveragePolicy.validate_leverage(Decimal("25"), "DYNAMIC") is True  # CLIENT SPEC: DYNAMIC capped at 25x
    assert LeveragePolicy.validate_leverage(Decimal("50"), "DYNAMIC") is False  # CLIENT SPEC: DYNAMIC max is 25x
    assert LeveragePolicy.validate_leverage(Decimal("51"), "DYNAMIC") is False  # Above maximum

def test_forbidden_gap():
    """Test that leverage in forbidden 6-7.5 gap is detected."""
    assert LeveragePolicy.is_forbidden_gap(Decimal("6.5")) is True
    assert LeveragePolicy.is_forbidden_gap(Decimal("7.0")) is True
    assert LeveragePolicy.is_forbidden_gap(Decimal("6.0")) is False  # Exactly 6 is allowed
    assert LeveragePolicy.is_forbidden_gap(Decimal("7.5")) is False  # Exactly 7.5 is allowed

def test_leverage_classification():
    """Test leverage classification logic (FAST removed, FIXED added per CLIENT SPEC)."""
    # Test missing SL -> FIXED (changed from FAST per CLIENT SPEC)
    leverage, mode = LeveragePolicy.classify_leverage(None, False, None)
    assert mode == "FIXED"  # Changed from FAST to FIXED
    assert leverage == Decimal("10")
    
    # Test SWING mode
    leverage, mode = LeveragePolicy.classify_leverage("SWING", True, None)
    assert mode == "SWING"
    assert leverage == Decimal("6")
    
    # Test FIXED mode (changed from FAST per CLIENT SPEC)
    leverage, mode = LeveragePolicy.classify_leverage("FIXED", True, Decimal("10"))
    assert mode == "FIXED"  # Changed from FAST to FIXED
    assert leverage == Decimal("10")
    
    # Test DYNAMIC mode
    leverage, mode = LeveragePolicy.classify_leverage("DYNAMIC", True, Decimal("15"))
    assert mode == "DYNAMIC"
    assert leverage == Decimal("15")

if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
