"""Strict leverage policy enforcement for client compliance."""

from decimal import Decimal
from typing import Tuple, Optional
from app.core.strict_config import STRICT_CONFIG
from app.core.logging import system_logger

class LeveragePolicy:
    """Enforces strict leverage policy according to client requirements."""
    
    @staticmethod
    def validate_leverage(leverage: Decimal, mode: str) -> bool:
        """
        Validate leverage against client policy.
        
        Rules:
        - SWING: exactly 6x
        - FAST: exactly 10x  
        - DYNAMIC: ≥7.5x, ≤50x
        - Forbidden gap: 6-7.5x (exclusive)
        """
        leverage_float = float(leverage)
        
        if mode == "SWING":
            return leverage_float == 6.0
        elif mode == "FAST":
            return leverage_float == 10.0
        elif mode == "DYNAMIC":
            return 7.5 <= leverage_float <= 50.0
        else:
            return False
    
    @staticmethod
    def is_forbidden_gap(leverage: Decimal) -> bool:
        """Check if leverage is in forbidden 6-7.5 range."""
        leverage_float = float(leverage)
        return 6.0 < leverage_float < 7.5
    
    @staticmethod
    def classify_leverage(mode_hint: Optional[str], has_sl: bool, raw_leverage: Optional[Decimal]) -> Tuple[Decimal, str]:
        """
        Classify leverage according to client rules.
        
        Rules:
        - Missing SL → FAST x10
        - SWING mode → x6
        - FAST mode → x10
        - DYNAMIC mode → ≥7.5x (use raw if provided, otherwise calculate)
        - Default → DYNAMIC ≥7.5x
        """
        if not has_sl:
            # Missing SL → FAST x10
            system_logger.info("Missing SL detected, forcing FAST x10 leverage")
            return STRICT_CONFIG.fast_leverage, "FAST"
        
        if mode_hint == "SWING":
            system_logger.info("SWING mode detected, using x6 leverage")
            return STRICT_CONFIG.swing_leverage, "SWING"
        
        if mode_hint == "FAST":
            system_logger.info("FAST mode detected, using x10 leverage")
            return STRICT_CONFIG.fast_leverage, "FAST"
        
        if mode_hint == "DYNAMIC":
            # Calculate dynamic leverage
            leverage = LeveragePolicy._calculate_dynamic_leverage(raw_leverage)
            system_logger.info(f"DYNAMIC mode detected, using {leverage}x leverage")
            return leverage, "DYNAMIC"
        
        # Default to DYNAMIC with calculated leverage
        leverage = LeveragePolicy._calculate_dynamic_leverage(raw_leverage)
        system_logger.info(f"Default mode, using DYNAMIC {leverage}x leverage")
        return leverage, "DYNAMIC"
    
    @staticmethod
    def _calculate_dynamic_leverage(raw_leverage: Optional[Decimal]) -> Decimal:
        """Calculate dynamic leverage based on position size and IM target."""
        from decimal import ROUND_DOWN
        
        # If raw leverage provided, use it but ensure it's within bounds
        if raw_leverage:
            leverage = max(raw_leverage, STRICT_CONFIG.min_dynamic_leverage)
            leverage = min(leverage, Decimal("50"))  # Max leverage limit
            
            # Ensure not in forbidden gap
            if LeveragePolicy.is_forbidden_gap(leverage):
                system_logger.warning(f"Raw leverage {leverage} in forbidden gap, adjusting to minimum")
                leverage = STRICT_CONFIG.min_dynamic_leverage
            
            return leverage
        
        # Calculate dynamic leverage based on IM target and position size
        base_leverage = STRICT_CONFIG.min_dynamic_leverage
        
        # Use deterministic calculation based on IM target
        # Higher IM targets can use higher leverage
        if hasattr(STRICT_CONFIG, 'im_target'):
            im_factor = min(STRICT_CONFIG.im_target / Decimal("20"), Decimal("2.5"))  # Max 2.5x factor
            dynamic_leverage = base_leverage * im_factor
        else:
            dynamic_leverage = base_leverage
        
        # Round to 1 decimal place for realistic dynamic values
        dynamic_leverage = dynamic_leverage.quantize(Decimal('0.1'), rounding=ROUND_DOWN)
        
        # Ensure it's within bounds
        dynamic_leverage = max(dynamic_leverage, STRICT_CONFIG.min_dynamic_leverage)
        dynamic_leverage = min(dynamic_leverage, Decimal("50"))
        
        return dynamic_leverage
    
    @staticmethod
    def enforce_isolated_margin_only(message: str) -> bool:
        """
        Check if message contains Cross margin and reject it.
        
        Returns:
            True if signal should be rejected (contains Cross margin)
            False if signal is acceptable (isolated margin)
        """
        cross_patterns = [
            r'Cross\s*\(',  # Cross (12.5X)
            r'Cross\s*\d+',  # Cross 50X
            r'Leverage\s*:\s*Cross',  # Leverage: Cross 50X
            r'Apalancamiento:\s*Cross',  # Spanish: Apalancamiento: Cross 50x
        ]
        
        import re
        for pattern in cross_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                system_logger.warning(f"Cross margin detected in signal: {pattern}")
                # Reject Cross margin to comply with client policy
                return True
        return False
