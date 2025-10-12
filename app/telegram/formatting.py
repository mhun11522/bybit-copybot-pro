"""Telegram message formatting utilities (CLIENT SPEC compliance)."""

from datetime import datetime
from decimal import Decimal, ROUND_DOWN
import pytz
import uuid

# Stockholm timezone for all timestamps
STO_TZ = pytz.timezone("Europe/Stockholm")


def now_hms_stockholm() -> str:
    """
    Get current time in Stockholm timezone formatted as HH:MM:SS.
    
    Returns:
        Time string like "15:15:05"
    """
    return datetime.now(STO_TZ).strftime("%H:%M:%S")


def format_datetime_stockholm(dt: datetime = None) -> str:
    """
    Format a datetime object to Stockholm time HH:MM:SS.
    
    Args:
        dt: datetime object (if None, uses current time)
    
    Returns:
        Time string like "15:15:05"
    """
    if dt is None:
        dt = datetime.now(STO_TZ)
    elif dt.tzinfo is None:
        # Assume UTC if no timezone
        dt = pytz.utc.localize(dt).astimezone(STO_TZ)
    else:
        dt = dt.astimezone(STO_TZ)
    
    return dt.strftime("%H:%M:%S")


def symbol_hashtags(symbol: str) -> str:
    """
    Generate hashtags for a symbol.
    
    Examples:
        "BTCUSDT" -> "#btc #btcusdt"
        "ETHUSDT" -> "#eth #ethusdt"
    
    Args:
        symbol: Trading symbol
    
    Returns:
        Hashtag string like "#btc #btcusdt"
    """
    s = symbol.upper().strip()
    base = s.replace("USDT", "").replace("PERP", "")
    return f"#{base.lower()} #{s.lower()}"


def ensure_trade_id(existing: str = None) -> str:
    """
    Ensure a trade ID exists, creating one if needed.
    
    Trade ID is used to track all messages related to a single trade.
    
    Args:
        existing: Existing trade ID (if any)
    
    Returns:
        Trade ID string (10 character uppercase hex)
    """
    if existing and existing.strip():
        return existing.strip()
    return uuid.uuid4().hex[:10].upper()


def fmt_usdt(value) -> str:
    """
    Format a value as USDT with exactly 2 decimals.
    
    CLIENT SPEC: All currency amounts must show exactly 2 decimals.
    
    Examples:
        19.3645 -> "19.36 USDT"
        20 -> "20.00 USDT"
    
    Args:
        value: Numeric value (Decimal, float, int, or string)
    
    Returns:
        Formatted string like "19.36 USDT"
    """
    try:
        q = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        return f"{q:.2f} USDT"
    except Exception:
        return f"{value} USDT"


def fmt_leverage(value) -> str:
    """
    Format leverage with exactly 2 decimals.
    
    CLIENT SPEC: Leverage must always show 2 decimals.
    
    Examples:
        6 -> "6.00x"
        7.5 -> "7.50x"
        10 -> "10.00x"
    
    Args:
        value: Leverage value (Decimal, float, int, or string)
    
    Returns:
        Formatted string like "7.50x"
    """
    try:
        q = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        return f"{q:.2f}x"
    except Exception:
        return f"{value}x"


def fmt_price(value, decimals: int = 4) -> str:
    """
    Format price with specified decimals.
    
    Args:
        value: Price value
        decimals: Number of decimal places (default 4)
    
    Returns:
        Formatted price string
    """
    try:
        quantizer = Decimal(f"0.{'0' * decimals}")
        q = Decimal(str(value)).quantize(quantizer, rounding=ROUND_DOWN)
        return f"{q:.{decimals}f}"
    except Exception:
        return str(value)


def fmt_percent(value) -> str:
    """
    Format percentage with 2 decimals.
    
    Args:
        value: Percentage value (as number, not decimal like 0.05 for 5%)
    
    Returns:
        Formatted string like "+6.30%" or "-2.15%"
    """
    try:
        val = float(value)
        sign = "+" if val >= 0 else ""
        return f"{sign}{val:.2f}%"
    except Exception:
        return f"{value}%"


def fmt_quantity(value, decimals: int = 3) -> str:
    """
    Format quantity with specified decimals.
    
    Args:
        value: Quantity value
        decimals: Number of decimal places (default 3)
    
    Returns:
        Formatted quantity string
    """
    try:
        quantizer = Decimal(f"0.{'0' * decimals}")
        q = Decimal(str(value)).quantize(quantizer, rounding=ROUND_DOWN)
        return f"{q:.{decimals}f}".rstrip('0').rstrip('.')
    except Exception:
        return str(value)

