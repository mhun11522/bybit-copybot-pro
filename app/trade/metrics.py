from decimal import Decimal

def pnl_pct(direction: str, entry: Decimal, mark: Decimal) -> Decimal:
    """
    Long:  (mark - entry)/entry * 100
    Short: (entry - mark)/entry * 100
    """
    if entry == 0: return Decimal("0")
    if direction.upper() == "BUY":
        return (mark - entry) / entry * Decimal("100")
    return (entry - mark) / entry * Decimal("100")
