"""Test suite for parser compliance with client requirements."""

import pytest
import asyncio
from decimal import Decimal
from app.signals.strict_parser import get_strict_parser
from app.core.leverage_policy import LeveragePolicy

class TestParserCompliance:
    """Test parser compliance with exact client requirements."""
    
    @pytest.fixture
    def parser(self):
        """Get parser instance."""
        return get_strict_parser()
    
    @pytest.mark.asyncio
    async def test_cross_margin_rejection(self, parser):
        """Test that Cross margin signals are rejected."""
        cross_signal = """🪙 MOVE/USDT
Exchanges: BYBIT

🟢 LONG  
Cross (12.5X)

Entry Targets: 
 0.10769

🎯 TP: 
 1) 0.108786 
 2) 0.109856 

⛔️ SL: 
 0.10501276"""
        
        result = await parser.parse_signal(cross_signal, "TEST_CHANNEL")
        assert result is None, "Cross margin signal should be rejected"
    
    @pytest.mark.asyncio
    async def test_invalid_tp_rejection(self, parser):
        """Test that invalid TPs like 'To the moon 🌖' are rejected."""
        invalid_tp_signal = """🪙 MOVE/USDT
Exchanges: BYBIT

🟢 LONG  
Leverage: 12.5x [Isolated]

Entry Targets: 
 0.10769

🎯 TP: 
 1) 0.108786 
 2) 0.109856 
 3) 0.110936 
 4) 0.112016 
 5) 0.113096 
 6) 0.114166 
 7) To the moon 🌖

⛔️ SL: 
 0.10501276"""
        
        result = await parser.parse_signal(invalid_tp_signal, "TEST_CHANNEL")
        assert result is not None, "Signal should be parsed"
        assert len(result['tps']) == 4, "Should only have 4 TPs, invalid ones rejected"
        assert "To the moon 🌖" not in str(result['tps']), "Invalid TP should be filtered out"
    
    @pytest.mark.asyncio
    async def test_entry_synthesis(self, parser):
        """Test that single entries are synthesized to dual entries."""
        single_entry_signal = """🪙 MOVE/USDT
Exchanges: BYBIT

🟢 LONG  
Leverage: 12.5x [Isolated]

Entry Targets: 
 0.10769

🎯 TP: 
 1) 0.108786 
 2) 0.109856 

⛔️ SL: 
 0.10501276"""
        
        result = await parser.parse_signal(single_entry_signal, "TEST_CHANNEL")
        assert result is not None, "Signal should be parsed"
        assert len(result['entries']) == 2, "Should have 2 entries (synthesized)"
        assert result['synthesized_entry2'] == True, "Entry2 should be synthesized"
    
    @pytest.mark.asyncio
    async def test_leverage_policy_swing(self, parser):
        """Test SWING leverage policy (x6)."""
        swing_signal = """🪙 MOVE/USDT
Exchanges: BYBIT

🟢 LONG  
SWING
Leverage: 6x [Isolated]

Entry Targets: 
 0.10769

🎯 TP: 
 1) 0.108786 
 2) 0.109856 

⛔️ SL: 
 0.10501276"""
        
        result = await parser.parse_signal(swing_signal, "TEST_CHANNEL")
        assert result is not None, "Signal should be parsed"
        assert result['leverage'] == 6.0, "SWING should use x6 leverage"
        assert result['mode'] == "SWING", "Mode should be SWING"
    
    @pytest.mark.asyncio
    async def test_leverage_policy_fast(self, parser):
        """Test FAST leverage policy (x10)."""
        fast_signal = """🪙 MOVE/USDT
Exchanges: BYBIT

🟢 LONG  
FAST
Leverage: 10x [Isolated]

Entry Targets: 
 0.10769

🎯 TP: 
 1) 0.108786 
 2) 0.109856 

⛔️ SL: 
 0.10501276"""
        
        result = await parser.parse_signal(fast_signal, "TEST_CHANNEL")
        assert result is not None, "Signal should be parsed"
        assert result['leverage'] == 10.0, "FAST should use x10 leverage"
        assert result['mode'] == "FAST", "Mode should be FAST"
    
    @pytest.mark.asyncio
    async def test_leverage_policy_dynamic(self, parser):
        """Test DYNAMIC leverage policy (≥7.5x)."""
        dynamic_signal = """🪙 MOVE/USDT
Exchanges: BYBIT

🟢 LONG  
DYNAMIC
Leverage: 12.5x [Isolated]

Entry Targets: 
 0.10769

🎯 TP: 
 1) 0.108786 
 2) 0.109856 

⛔️ SL: 
 0.10501276"""
        
        result = await parser.parse_signal(dynamic_signal, "TEST_CHANNEL")
        assert result is not None, "Signal should be parsed"
        assert result['leverage'] >= 7.5, "DYNAMIC should use ≥7.5x leverage"
        assert result['mode'] == "DYNAMIC", "Mode should be DYNAMIC"
    
    @pytest.mark.asyncio
    async def test_missing_sl_forces_fast(self, parser):
        """Test that missing SL forces FAST x10 leverage."""
        no_sl_signal = """🪙 MOVE/USDT
Exchanges: BYBIT

🟢 LONG  
Leverage: 12.5x [Isolated]

Entry Targets: 
 0.10769

🎯 TP: 
 1) 0.108786 
 2) 0.109856"""
        
        result = await parser.parse_signal(no_sl_signal, "TEST_CHANNEL")
        assert result is not None, "Signal should be parsed"
        assert result['leverage'] == 10.0, "Missing SL should force x10 leverage"
        assert result['mode'] == "FAST", "Missing SL should force FAST mode"
        assert result['synthesized_sl'] == True, "SL should be synthesized"
    
    def test_leverage_policy_validation(self):
        """Test leverage policy validation."""
        # Valid leverages
        assert LeveragePolicy.validate_leverage(Decimal("6"), "SWING") == True
        assert LeveragePolicy.validate_leverage(Decimal("10"), "FAST") == True
        assert LeveragePolicy.validate_leverage(Decimal("7.5"), "DYNAMIC") == True
        assert LeveragePolicy.validate_leverage(Decimal("50"), "DYNAMIC") == True
        
        # Invalid leverages
        assert LeveragePolicy.validate_leverage(Decimal("5"), "SWING") == False
        assert LeveragePolicy.validate_leverage(Decimal("7"), "FAST") == False
        assert LeveragePolicy.validate_leverage(Decimal("6.5"), "DYNAMIC") == False  # Forbidden gap
        assert LeveragePolicy.validate_leverage(Decimal("51"), "DYNAMIC") == False
    
    def test_forbidden_leverage_gap(self):
        """Test forbidden leverage gap detection."""
        # Forbidden gap (6-7.5 exclusive)
        assert LeveragePolicy.is_forbidden_gap(Decimal("6.1")) == True
        assert LeveragePolicy.is_forbidden_gap(Decimal("7.0")) == True
        assert LeveragePolicy.is_forbidden_gap(Decimal("7.4")) == True
        
        # Allowed leverages
        assert LeveragePolicy.is_forbidden_gap(Decimal("6.0")) == False
        assert LeveragePolicy.is_forbidden_gap(Decimal("7.5")) == False
        assert LeveragePolicy.is_forbidden_gap(Decimal("5.0")) == False
        assert LeveragePolicy.is_forbidden_gap(Decimal("10.0")) == False
    
    def test_cross_margin_detection(self):
        """Test Cross margin detection."""
        # Should detect Cross margin
        assert LeveragePolicy.enforce_isolated_margin_only("Cross (12.5X)") == True
        assert LeveragePolicy.enforce_isolated_margin_only("Cross 50X") == True
        assert LeveragePolicy.enforce_isolated_margin_only("Leverage: Cross 50X") == True
        assert LeveragePolicy.enforce_isolated_margin_only("Apalancamiento: Cross 50x") == True
        
        # Should allow isolated margin
        assert LeveragePolicy.enforce_isolated_margin_only("Leverage: 12.5x [Isolated]") == False
        assert LeveragePolicy.enforce_isolated_margin_only("10x [Isolated]") == False
        assert LeveragePolicy.enforce_isolated_margin_only("No leverage mentioned") == False

if __name__ == "__main__":
    pytest.main([__file__])
