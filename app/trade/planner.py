"""Dual-entry planner with ±0.1% rule."""

from decimal import Decimal

def plan_dual_entries(direction: str, entries: list[str]):
    """
    Plan dual entries according to client requirements:
    - If 2 entries given -> 50/50 split
    - If 1 entry -> synthesize second at ±0.1% in signal direction
    """
    if len(entries) >= 2:
        # Use provided entries with 50/50 split
        e1, e2 = Decimal(entries[0]), Decimal(entries[1])
        return [str(e1), str(e2)], [Decimal("0.5"), Decimal("0.5")]
    else:
        # Single entry -> create second at ±0.1%
        base = Decimal(entries[0])
        bump = base * Decimal("0.001")  # 0.1%
        
        if direction == "BUY":
            # For BUY: first entry higher, second lower
            e1, e2 = base, base - bump
        else:
            # For SELL: first entry lower, second higher  
            e1, e2 = base, base + bump
            
        return [str(e1), str(e2)], [Decimal("0.5"), Decimal("0.5")]