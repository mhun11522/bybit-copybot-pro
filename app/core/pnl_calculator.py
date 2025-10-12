"""
PNL Calculator - Fix for Requirement #30

CLIENT REQUIREMENT:
"📊 Resultat: +1.59% | +32.00 USD - should be 3.2 USDT not 32 USDT if it is 20 USDT / trade"

ISSUE: PnL was showing 10x too large (32 USD instead of 3.2 USD)
CAUSE: Using notional value instead of IM-based calculation

CORRECT FORMULA:
For leveraged positions, PnL should be based on Initial Margin (IM), not notional:
- PnL_USD = IM × (exit_price - entry_price) / entry_price × leverage
- PnL_PCT = (exit_price - entry_price) / entry_price × 100 × leverage

However, Bybit's unrealisedPnl already includes leverage, so:
- If using Bybit's unrealisedPnl: USE IT DIRECTLY (already includes leverage)
- If calculating manually: PnL_USDT = (exit_price - entry_price) × position_size

For IM-based PnL (what client wants):
- PnL_USDT = unrealisedPnl (from Bybit, already correct)
- PnL_PCT = (unrealisedPnl / IM) × 100
"""

from decimal import Decimal
from typing import Dict, Any, Tuple

def calculate_pnl_from_bybit(
    unrealised_pnl: Decimal,
    initial_margin: Decimal,
    position_size: Decimal,
    entry_price: Decimal,
    exit_price: Decimal
) -> Tuple[Decimal, Decimal]:
    """
    Calculate PnL correctly from Bybit position data.
    
    Args:
        unrealised_pnl: Unrealised PnL from Bybit (in USDT)
        initial_margin: Initial margin used for position (IM in USDT)
        position_size: Position size in contracts
        entry_price: Average entry price
        exit_price: Current or exit price
        
    Returns:
        Tuple of (pnl_usdt, pnl_pct)
        - pnl_usdt: PnL in USDT (based on IM)
        - pnl_pct: PnL percentage (relative to IM, including leverage effect)
    """
    # Use Bybit's unrealisedPnl directly (it's already correct and includes leverage)
    pnl_usdt = unrealised_pnl
    
    # Calculate percentage relative to IM (not notional)
    # This gives the ROI on the margin used
    if initial_margin > 0:
        pnl_pct = (unrealised_pnl / initial_margin) * Decimal("100")
    else:
        pnl_pct = Decimal("0")
    
    return pnl_usdt, pnl_pct


def calculate_pnl_manual(
    position_size: Decimal,
    entry_price: Decimal,
    exit_price: Decimal,
    initial_margin: Decimal,
    side: str
) -> Tuple[Decimal, Decimal]:
    """
    Calculate PnL manually when Bybit data is unavailable.
    
    Args:
        position_size: Position size in contracts
        entry_price: Average entry price
        exit_price: Current or exit price
        initial_margin: Initial margin used (IM in USDT)
        side: Position side ("Buy"/"Long" or "Sell"/"Short")
        
    Returns:
        Tuple of (pnl_usdt, pnl_pct)
    """
    if side.upper() in ["BUY", "LONG"]:
        price_change = exit_price - entry_price
    else:  # SHORT/SELL
        price_change = entry_price - exit_price
    
    # PnL = price_change × position_size
    pnl_usdt = price_change * position_size
    
    # Percentage relative to IM
    if initial_margin > 0:
        pnl_pct = (pnl_usdt / initial_margin) * Decimal("100")
    else:
        pnl_pct = Decimal("0")
    
    return pnl_usdt, pnl_pct


def format_pnl_for_message(pnl_usdt: Decimal, pnl_pct: Decimal) -> Dict[str, str]:
    """
    Format PnL for Swedish templates.
    
    Returns:
        Dict with 'result_usdt' and 'result_pct' formatted for messages
    """
    # Format USDT with 2 decimal places
    result_usdt = f"{float(pnl_usdt):.2f}"
    
    # Format percentage with 2 decimal places
    result_pct = f"{float(pnl_pct):.2f}"
    
    return {
        'result_usdt': result_usdt,
        'result_pct': result_pct
    }


def validate_pnl_calculation(
    pnl_usdt: Decimal,
    initial_margin: Decimal,
    leverage: Decimal
) -> bool:
    """
    Validate that PnL is reasonable given IM and leverage.
    
    CLIENT SPEC: For 20 USDT IM, PnL should NOT exceed 20 USDT × leverage
    
    Returns:
        True if PnL is reasonable, False if it's suspiciously large
    """
    # Maximum possible PnL (100% move) = IM × leverage
    max_possible_pnl = initial_margin * leverage
    
    # If PnL exceeds max possible, it's wrong
    if abs(pnl_usdt) > max_possible_pnl:
        return False
    
    # For 20 USDT IM with 10x leverage:
    # - 1.59% price move should yield ~3.18 USDT PnL
    # - NOT 32 USDT (which would be 160% of IM, impossible with 1.59% move)
    
    return True


# Example calculation for documentation:
"""
EXAMPLE (Client's case):
- Initial Margin (IM): 20 USDT
- Leverage: 10x
- Entry Price: 100 USDT
- Exit Price: 101.59 USDT
- Position Size: (20 × 10) / 100 = 2 contracts

CORRECT CALCULATION:
- Price Change: 101.59 - 100 = 1.59 USDT
- Price Change %: (1.59 / 100) × 100 = 1.59%
- PnL_USDT: 1.59 × 2 = 3.18 USDT ✓ (NOT 31.8 USDT)
- PnL_PCT (vs IM): (3.18 / 20) × 100 = 15.9% ✓
- PnL_PCT (vs notional): (3.18 / 200) × 100 = 1.59% ✓

Note: The 15.9% is the ROI on margin (includes leverage effect)
      The 1.59% is the price movement (excludes leverage)
      
For messages, show: "Resultat: +15.9% inkl. hävstång | +3.18 USDT inkl. hävstång"
"""

