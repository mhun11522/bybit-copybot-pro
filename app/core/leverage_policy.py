"""Strict leverage policy enforcement for client compliance."""

from decimal import Decimal, ROUND_DOWN
from typing import Tuple, Optional
from app.core.strict_config import STRICT_CONFIG
from app.core.logging import system_logger

class LeveragePolicy:
    """Enforces strict leverage policy according to CLIENT SPECIFICATION."""
    
    @staticmethod
    async def get_instrument_max_leverage(symbol: str) -> Decimal:
        """
        Get maximum leverage allowed for a symbol from Bybit API.
        
        Returns:
            Decimal: Maximum leverage for the instrument (e.g., 50, 25, 12.5)
        """
        try:
            from app.bybit.client import get_bybit_client
            client = get_bybit_client()
            
            instrument_info = await client.get_instrument_info(symbol)
            if instrument_info and instrument_info.get('retCode') == 0:
                instruments = instrument_info.get('result', {}).get('list', [])
                if instruments:
                    leverage_filter = instruments[0].get('leverageFilter', {})
                    max_lev = Decimal(str(leverage_filter.get('maxLeverage', '50')))
                    system_logger.info(f"Instrument max leverage for {symbol}: {max_lev}x")
                    return max_lev
        except Exception as e:
            system_logger.warning(f"Failed to get max leverage for {symbol}: {e}")
        
        # Default fallback
        return Decimal("50")
    
    @staticmethod
    def validate_leverage(leverage: Decimal, mode: str) -> bool:
        """
        Validate leverage against client policy.
        
        CLIENT SPEC (doc/10_15.md):
        - SWING: exactly 6x (no variation)
        - DYNAMIC: ≥7.5x, ≤25x
        - FIXED: explicit value (any valid leverage)
        - Forbidden gap: (6, 7.5) exclusive - MUST NOT exist
        """
        leverage_float = float(leverage)
        
        if mode == "SWING":
            return leverage_float == 6.0
        elif mode == "DYNAMIC":
            return 7.5 <= leverage_float <= 25.0
        elif mode == "FIXED":
            # FIXED mode: explicit leverage, but must not be in forbidden gap
            if 6.0 < leverage_float < 7.5:
                return False  # Forbidden gap
            return True
        else:
            return False
    
    @staticmethod
    def is_forbidden_gap(leverage: Decimal) -> bool:
        """
        Check if leverage is in forbidden (6, 7.5) range.
        
        CLIENT RULE: No leverage between 6 and 7.5 (exclusive) is allowed.
        """
        leverage_float = float(leverage)
        return 6.0 < leverage_float < 7.5
    
    @staticmethod
    def classify_leverage(mode_hint: Optional[str], has_sl: bool, raw_leverage: Optional[Decimal]) -> Tuple[Decimal, str]:
        """
        Classify leverage according to CLIENT SPECIFICATION.
        
        CLIENT SPEC (doc/10_15.md Lines 355-362):
        1. SWING mode → EXACTLY x6.00 (no variation)
        2. DYNAMIC mode → ≥7.5x with two decimals, compute with bounds [7.5, 25]
        3. FIXED mode → explicit value, forbid values between 6 and 7.5
        4. Missing SL → set auto-SL −2% from OEP and lock leverage x10 (safety case, NOT a mode)
        5. Default → DYNAMIC ≥7.5x
        
        Forbidden Gap Rule:
        - If computed leverage lands in (6, 7.5) → promote to 7.5x
        """
        if not has_sl:
            # CLIENT SPEC: Missing SL → auto-SL −2% + lock leverage x10 (safety case)
            system_logger.warning("Missing SL detected, locking leverage at x10 for safety (CLIENT SPEC)")
            # Note: Caller must also create auto-SL at −2% from OEP
            return Decimal("10.00"), "FIXED"  # Treat as FIXED x10 (not a mode, just a safety lock)
        
        if mode_hint == "SWING":
            # SWING mode → EXACTLY x6.00 (NO COMPUTATION, NO VARIATION)
            system_logger.info("SWING mode: enforcing EXACTLY 6.00x leverage (CLIENT SPEC)")
            return Decimal("6.00"), "SWING"
        
        if mode_hint == "FIXED" and raw_leverage:
            # FIXED mode → explicit leverage (must not be in forbidden gap)
            leverage = raw_leverage
            if Decimal("6") < leverage < Decimal("7.5"):
                system_logger.error(
                    f"FIXED leverage {leverage}x in forbidden gap (6, 7.5) - REJECTED (CLIENT SPEC)"
                )
                raise ValueError(f"Forbidden leverage value: {leverage}x is between 6 and 7.5")
            system_logger.info(f"FIXED mode: using explicit {leverage}x leverage")
            return leverage, "FIXED"
        
        if mode_hint == "DYNAMIC" or not mode_hint:
            # Calculate dynamic leverage with strict bounds
            leverage = LeveragePolicy._calculate_dynamic_leverage(raw_leverage)
            system_logger.info(f"DYNAMIC mode: using {leverage}x leverage (bounds: [7.5, 25])")
            return leverage, "DYNAMIC"
        
        # Fallback to DYNAMIC
        leverage = LeveragePolicy._calculate_dynamic_leverage(raw_leverage)
        system_logger.info(f"Unknown mode '{mode_hint}', defaulting to DYNAMIC {leverage}x leverage")
        return leverage, "DYNAMIC"
    
    @staticmethod
    def _calculate_dynamic_leverage(raw_leverage: Optional[Decimal]) -> Decimal:
        """
        Calculate dynamic leverage with CLIENT SPECIFICATION.
        
        RULES:
        - MUST be >= 7.5x (DYN_MIN)
        - MUST be <= 25x (DYN_MAX)
        - Forbidden gap (6, 7.5) → promote to 7.5x
        - If calculated value < 7.5 → force 7.5x
        - If calculated value > 25 → cap at 25x
        """
        DYN_MIN = STRICT_CONFIG.dynamic_leverage_min  # 7.5
        DYN_MAX = STRICT_CONFIG.dynamic_leverage_max  # 25
        
        # If raw leverage provided, validate and clamp it
        if raw_leverage:
            leverage = raw_leverage
            
            # Close forbidden gap: if in (6, 7.5) → promote to 7.5
            if Decimal("6") < leverage < DYN_MIN:
                system_logger.warning(
                    f"Raw leverage {leverage}x in forbidden gap (6, 7.5), "
                    f"promoting to {DYN_MIN}x (client spec)"
                )
                leverage = DYN_MIN
            
            # Enforce minimum: any value < 7.5 → force 7.5
            if leverage < DYN_MIN:
                system_logger.info(f"Raw leverage {leverage}x < {DYN_MIN}x, forcing to {DYN_MIN}x")
                leverage = DYN_MIN
            
            # Enforce maximum: any value > 25 → cap at 25
            if leverage > DYN_MAX:
                system_logger.info(f"Raw leverage {leverage}x > {DYN_MAX}x, capping to {DYN_MAX}x")
                leverage = DYN_MAX
            
            return leverage
        
        # No raw leverage provided - calculate based on IM target
        base_leverage = DYN_MIN  # Start at 7.5x minimum
        
        # Use deterministic calculation based on IM target
        if hasattr(STRICT_CONFIG, 'im_target'):
            im_factor = min(STRICT_CONFIG.im_target / Decimal("20"), Decimal("2.5"))  # Max 2.5x factor
            dynamic_leverage = base_leverage * im_factor
        else:
            dynamic_leverage = base_leverage
        
        # CLIENT SPEC FIX: Round to 2 decimal places (was 1, violates client requirement)
        # doc/requirement.txt Line 20: "Does the leverage have 2 decimal places on dynamic leverage?"
        dynamic_leverage = dynamic_leverage.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        
        # Enforce minimum (7.5x)
        dynamic_leverage = max(dynamic_leverage, DYN_MIN)
        
        # Enforce maximum (25x)
        dynamic_leverage = min(dynamic_leverage, DYN_MAX)
        
        # Final forbidden gap check (should not happen, but safety)
        if Decimal("6") < dynamic_leverage < DYN_MIN:
            system_logger.warning(f"Calculated leverage {dynamic_leverage}x in forbidden gap, forcing to {DYN_MIN}x")
            dynamic_leverage = DYN_MIN
        
        return dynamic_leverage
    
    @staticmethod
    def enforce_isolated_margin_only(message: str) -> bool:
        """
        Check if message contains Cross margin and reject it.
        
        CLIENT REQUIREMENT: Only isolated margin is allowed.
        
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
