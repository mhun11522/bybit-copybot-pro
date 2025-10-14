"""Decimal utilities for financial calculations."""

from decimal import Decimal, ROUND_DOWN, ROUND_UP, ROUND_FLOOR
from typing import Union, Any
import re

def to_decimal(value: Any) -> Decimal:
    """Convert any value to Decimal with proper precision."""
    if isinstance(value, Decimal):
        return value
    elif isinstance(value, (int, float)):
        return Decimal(str(value))
    elif isinstance(value, str):
        # Clean string and convert
        cleaned = re.sub(r'[^\d.-]', '', value)
        return Decimal(cleaned)
    else:
        raise ValueError(f"Cannot convert {type(value)} to Decimal")

def quantize_price(price: Decimal, tick_size: Decimal) -> Decimal:
    """
    Quantize price to tick size.
    
    CLIENT SPEC Line 285: Use ROUND_DOWN for prices to avoid overpaying.
    """
    if tick_size == 0:
        return price
    return price.quantize(tick_size, rounding=ROUND_DOWN)

def quantize_qty(qty: Decimal, step_size: Decimal) -> Decimal:
    """
    Quantize quantity to step size.
    
    CLIENT SPEC Line 286: Use ROUND_FLOOR for quantities (NOT ROUND_DOWN).
    
    Difference:
    - ROUND_DOWN: rounds toward zero (e.g., -1.5 → -1, 1.5 → 1)
    - ROUND_FLOOR: rounds toward negative infinity (e.g., -1.5 → -2, 1.5 → 1)
    
    For positive quantities (normal case), both give same result.
    For negative quantities (short positions), ROUND_FLOOR is more conservative.
    
    This is a BLOCKER requirement - must be ROUND_FLOOR per spec!
    """
    if step_size == 0:
        return qty
    return qty.quantize(step_size, rounding=ROUND_FLOOR)

def safe_divide(numerator: Decimal, denominator: Decimal, default: Decimal = Decimal('0')) -> Decimal:
    """Safely divide two decimals, returning default if denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator

def safe_multiply(a: Decimal, b: Decimal) -> Decimal:
    """Safely multiply two decimals."""
    return a * b

def format_decimal(value: Decimal, precision: int = 8) -> str:
    """Format decimal with specified precision."""
    return f"{value:.{precision}f}".rstrip('0').rstrip('.')

def is_positive(value: Decimal) -> bool:
    """Check if decimal is positive."""
    return value > 0

def is_negative(value: Decimal) -> bool:
    """Check if decimal is negative."""
    return value < 0

def is_zero(value: Decimal) -> bool:
    """Check if decimal is zero."""
    return value == 0

def abs_decimal(value: Decimal) -> Decimal:
    """Get absolute value of decimal."""
    return abs(value)

def min_decimal(a: Decimal, b: Decimal) -> Decimal:
    """Get minimum of two decimals."""
    return min(a, b)

def max_decimal(a: Decimal, b: Decimal) -> Decimal:
    """Get maximum of two decimals."""
    return max(a, b)

def clamp_decimal(value: Decimal, min_val: Decimal, max_val: Decimal) -> Decimal:
    """Clamp decimal value between min and max."""
    return max_decimal(min_val, min_decimal(value, max_val))
