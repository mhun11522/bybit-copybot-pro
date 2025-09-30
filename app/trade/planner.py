from decimal import Decimal

def plan_dual_entries(direction: str, entries: list[str]):
    """
    If two entries were provided -> use them 50/50.
    If only one -> synthesize the second at ±0.1% in the signal direction.
    Returns (planned_prices_as_str, splits_as_decimals).
    """
    if len(entries) >= 2:
        e1, e2 = Decimal(entries[0]), Decimal(entries[1])
    else:
        base = Decimal(entries[0])
        bump = base * Decimal("0.001")  # 0.1%
        if direction == "BUY":
            e1, e2 = base, base - bump
        else:
            e1, e2 = base, base + bump
    return [str(e1), str(e2)], [Decimal("0.5"), Decimal("0.5")]