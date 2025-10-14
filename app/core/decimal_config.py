"""Decimal precision configuration and validation."""

from decimal import Decimal, getcontext, ROUND_DOWN, ROUND_UP, ROUND_FLOOR
from typing import Union, Any
import warnings

# Set global decimal precision to 28 as required
getcontext().prec = 28

# Rounding modes for different operations
# CLIENT SPEC Requirements (doc/10_12_requirement.txt):
# Line 285: "Price quantization: ROUND_DOWN"
# Line 286: "Quantity quantization: ROUND_FLOOR (not ROUND_DOWN)" ← CRITICAL!
PRICE_ROUNDING = ROUND_DOWN   # Line 285: Prices use ROUND_DOWN
QTY_ROUNDING = ROUND_FLOOR    # Line 286: Quantities use ROUND_FLOOR (NOT ROUND_DOWN!)
PNL_ROUNDING = ROUND_DOWN     # Conservative PnL rounding

def to_decimal(value: Union[str, int, float, Decimal]) -> Decimal:
    """Convert any numeric value to Decimal with validation."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        # Convert to string first to avoid float precision issues
        return Decimal(str(value))
    if isinstance(value, str):
        return Decimal(value)
    raise ValueError(f"Cannot convert {type(value)} to Decimal: {value}")

def quantize_price(price: Decimal, tick_size: Decimal) -> Decimal:
    """Quantize price to tick size using price rounding."""
    return price.quantize(tick_size, rounding=PRICE_ROUNDING)

def quantize_qty(qty: Decimal, step_size: Decimal) -> Decimal:
    """Quantize quantity to step size using quantity rounding."""
    return qty.quantize(step_size, rounding=QTY_ROUNDING)

def quantize_pnl(pnl: Decimal, precision: int = 8) -> Decimal:
    """Quantize PnL to specified precision."""
    return pnl.quantize(Decimal('0.' + '0' * precision), rounding=PNL_ROUNDING)

def validate_decimal_usage():
    """Validate that no floats are used in critical calculations."""
    import inspect
    import sys
    
    # Get all modules that should use Decimal
    critical_modules = [
        'app.trade.executor',
        'app.trade.manager', 
        'app.signals.processor',
        'app.core.risk',
        'app.strategies'
    ]
    
    for module_name in critical_modules:
        if module_name in sys.modules:
            module = sys.modules[module_name]
            for name, obj in inspect.getmembers(module):
                if inspect.isfunction(obj) or inspect.ismethod(obj):
                    source = inspect.getsource(obj)
                    if 'float(' in source and 'price' in source.lower():
                        warnings.warn(f"Potential float usage in {module_name}.{name}")

# Global decimal context validation
def ensure_decimal_precision():
    """Ensure decimal precision is set correctly."""
    if getcontext().prec < 28:
        getcontext().prec = 28
        warnings.warn("Decimal precision was less than 28, corrected to 28")

# Initialize on import
ensure_decimal_precision()