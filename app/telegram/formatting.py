"""Telegram message formatting utilities (CLIENT SPEC compliance)."""

from datetime import datetime
from decimal import Decimal, ROUND_DOWN, InvalidOperation
import pytz
import uuid
from app.core.logging import system_logger

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
    Format a value as USDT with exactly 2 decimals (Swedish format).
    
    CLIENT SPEC: All currency amounts must show exactly 2 decimals.
    CLIENT SPEC (doc/10_11.md Line 519): Use comma as decimal separator.
    
    Examples:
        19.3645 -> "19,36 USDT"
        20 -> "20,00 USDT"
    
    Args:
        value: Numeric value (Decimal, float, int, or string)
    
    Returns:
        Formatted string like "19,36 USDT" (Swedish format with comma)
    """
    try:
        q = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        return f"{q:.2f} USDT".replace(".", ",")  # Swedish: comma separator
    except Exception:
        return f"{value} USDT"


def fmt_leverage(value) -> str:
    """
    Format leverage with exactly 2 decimals (Swedish format).
    
    CLIENT SPEC: Leverage must always show 2 decimals.
    CLIENT SPEC (doc/10_11.md Line 205): Use comma separator.
    
    Examples:
        6 -> "6,00x"
        7.5 -> "7,50x"
        10 -> "10,00x"
    
    Args:
        value: Leverage value (Decimal, float, int, or string)
    
    Returns:
        Formatted string like "7,50x" (Swedish format with comma)
    """
    try:
        q = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        return f"{q:.2f}x".replace(".", ",")  # Swedish: comma separator
    except Exception:
        return f"{value}x"


def fmt_price(value, decimals: int = 4) -> str:
    """
    Format price with specified decimals (Swedish format).
    
    CLIENT SPEC (doc/10_11.md Line 519): Use comma as decimal separator.
    
    Examples:
        60000.12345 -> "60000,1234" (4 decimals)
        2.5 -> "2,5000" (4 decimals)
    
    Args:
        value: Price value
        decimals: Number of decimal places (default 4)
    
    Returns:
        Formatted price string with comma separator
    """
    try:
        quantizer = Decimal(f"0.{'0' * decimals}")
        q = Decimal(str(value)).quantize(quantizer, rounding=ROUND_DOWN)
        return f"{q:.{decimals}f}".replace(".", ",")  # Swedish: comma separator
    except Exception:
        return str(value)


def fmt_percent(value) -> str:
    """
    Format percentage with 2 decimals (Swedish format).
    
    CLIENT SPEC (doc/10_11.md Line 434): "% always 11 %, NOT 11%"
    CLIENT SPEC (doc/10_11.md Line 519): Use comma as decimal separator.
    
    Examples:
        6.30 -> "+6,30 %"
        -2.15 -> "-2,15 %"
        11 -> "+11,00 %"
    
    Args:
        value: Percentage value (as number, not decimal like 0.05 for 5%)
    
    Returns:
        Formatted string like "+6,30 %" with SPACE before % (Swedish format)
    """
    try:
        val = float(value)
        sign = "+" if val >= 0 else ""
        # Swedish format: comma separator + space before %
        return f"{sign}{val:.2f} %".replace(".", ",")
    except Exception:
        return f"{value} %"


def fmt_quantity(value, decimals: int = 3) -> str:
    """
    Format quantity with specified decimals (Swedish format).
    
    CLIENT SPEC (doc/10_11.md Line 519): Use comma as decimal separator.
    
    Args:
        value: Quantity value
        decimals: Number of decimal places (default 3)
    
    Returns:
        Formatted quantity string with comma separator
    """
    try:
        quantizer = Decimal(f"0.{'0' * decimals}")
        q = Decimal(str(value)).quantize(quantizer, rounding=ROUND_DOWN)
        formatted = f"{q:.{decimals}f}".rstrip('0').rstrip('.')
        return formatted.replace(".", ",")  # Swedish: comma separator
    except Exception:
        return str(value)


# ============================================================================
# NEW FUNCTIONS FOR CLIENT TEMPLATE COMPLIANCE
# ============================================================================

def fmt_leverage_with_type(leverage, trade_type: str) -> str:
    """
    Format leverage with type label (Swedish format).
    
    CLIENT SPEC (doc/10_15.md):
    - SWING: "⚙️ Hävstång SWING: x6,00"
    - Dynamisk: "⚙️ Hävstång Dynamisk: x13,56"
    - FIXED: "⚙️ Hävstång Fast: x10,00" (explicit)
    
    Examples:
        fmt_leverage_with_type(6.00, "Swing") -> "⚙️ Hävstång SWING: x6,00"
        fmt_leverage_with_type(13.56, "Dynamisk") -> "⚙️ Hävstång Dynamisk: x13,56"
        fmt_leverage_with_type(10.00, "FIXED") -> "⚙️ Hävstång Fast: x10,00"
    
    Args:
        leverage: Leverage value (Decimal, float, int, or string)
        trade_type: "Swing", "Dynamisk", or "FIXED"
    
    Returns:
        Formatted string with type label and comma separator
    """
    try:
        lev = Decimal(str(leverage))
        
        # CLIENT FIX: Format leverage without unnecessary decimals
        # x25 instead of x25.00, x10 instead of x10.00
        if lev == lev.to_integral():
            lev_str = str(int(lev))  # x25, x10, x6
        else:
            lev_str = f"{lev:.2f}".replace(".", ",")  # x13,56 for decimal values
        
        if trade_type == "Swing":
            return f"⚙️ Hävstång SWING: x{lev_str}"
        elif trade_type == "Dynamisk":
            return f"⚙️ Hävstång Dynamisk: x{lev_str}"
        elif trade_type == "FIXED":
            return f"⚙️ Hävstång Fast: x{lev_str}"
        else:
            return f"⚙️ Hävstång: x{lev_str}"
    except Exception:
        return f"⚙️ Hävstång: x{leverage}"


def calculate_tp_sl_percentages(entry, tps: list, sl, side: str) -> dict:
    """
    Calculate TP/SL percentages from entry price.
    
    CLIENT SPEC (doc/10_11.md Lines 1274-1278): 
    Show all 4 TPs with percentages calculated from entry.
    
    Examples:
        Entry=60000, TP1=61500, side=LONG
        -> tp1_pct = (61500-60000)/60000*100 = 2.50%
    
    Args:
        entry: Entry price (Decimal)
        tps: List of up to 4 TP prices [TP1, TP2, TP3, TP4]
        sl: SL price (Decimal)
        side: "LONG" or "SHORT"
    
    Returns:
        Dict with tp1_pct, tp2_pct, tp3_pct, tp4_pct, sl_pct (as floats)
    """
    result = {}
    # CRITICAL FIX: Handle invalid entry values safely
    try:
        # First, safely convert entry to string to avoid any property access issues
        if entry is None:
            raise ValueError("Entry is None")
        
        # Safely get string representation first
        entry_str = str(entry)
        if not entry_str or entry_str.strip() == "":
            raise ValueError("Entry is empty")
        
        # Now safely check types and convert
        if isinstance(entry, Decimal):
            entry_dec = entry
        elif isinstance(entry, str):
            # Normalize: replace comma with dot for Swedish format
            entry_clean = entry.replace(",", ".")
            entry_dec = Decimal(entry_clean)
        else:
            # Convert to string first, then to Decimal
            entry_dec = Decimal(str(entry))
            
    except (ValueError, InvalidOperation, TypeError, AttributeError) as e:
        system_logger.error(f"Invalid entry value: {entry} ({type(entry)}), cannot calculate percentages", {"entry": str(entry), "error": str(e)})
        # Return empty result with error indication
        return {
            'tp1_pct': None, 'tp2_pct': None, 'tp3_pct': None, 'tp4_pct': None, 'sl_pct': None,
            'error': f"Invalid entry: {entry}"
        }
    
    # Calculate TP percentages
    for i, tp in enumerate(tps, 1):
        if tp is None or tp == 0 or tp == "":
            result[f'tp{i}_pct'] = None
            continue
        
        # CRITICAL FIX: Handle both Decimal and string values, normalize Swedish format
        try:
            if isinstance(tp, str):
                # Normalize: replace comma with dot for Swedish format
                tp_clean = tp.replace(",", ".")
                tp_dec = Decimal(tp_clean)
            elif isinstance(tp, Decimal):
                tp_dec = tp
            else:
                tp_dec = Decimal(str(tp))
        except (ValueError, InvalidOperation) as e:
            system_logger.warning(f"Invalid TP value at position {i}: {tp} ({type(tp)}), skipping", {"tp": str(tp), "error": str(e)})
            result[f'tp{i}_pct'] = None
            continue
        
        if side.upper() in ("LONG", "BUY"):
            pct = ((tp_dec - entry_dec) / entry_dec) * Decimal("100")
        else:  # SHORT, SELL
            pct = ((entry_dec - tp_dec) / entry_dec) * Decimal("100")
        
        result[f'tp{i}_pct'] = round(float(pct), 2)
    
    # Fill missing TPs
    for i in range(1, 5):
        if f'tp{i}_pct' not in result:
            result[f'tp{i}_pct'] = None
    
    # Calculate SL percentage (always negative for loss)
    if sl and sl != 0 and sl != "":
        # CRITICAL FIX: Handle both Decimal and string values, normalize Swedish format
        try:
            if isinstance(sl, str):
                # Normalize: replace comma with dot for Swedish format
                sl_clean = sl.replace(",", ".")
                sl_dec = Decimal(sl_clean)
            elif isinstance(sl, Decimal):
                sl_dec = sl
            else:
                sl_dec = Decimal(str(sl))
        except (ValueError, InvalidOperation) as e:
            system_logger.warning(f"Invalid SL value: {sl} ({type(sl)}), setting to None", {"sl": str(sl), "error": str(e)})
            result['sl_pct'] = None
            return result
            
        
        if side.upper() in ("LONG", "BUY"):
            sl_pct = ((sl_dec - entry_dec) / entry_dec) * Decimal("100")
        else:  # SHORT, SELL
            sl_pct = ((entry_dec - sl_dec) / entry_dec) * Decimal("100")
        
        result['sl_pct'] = round(float(sl_pct), 2)
    else:
        result['sl_pct'] = None
    
    return result


def detect_trade_type(leverage, has_sl: bool = True) -> str:
    """
    Detect trade type from leverage value.
    
    CLIENT SPEC (doc/10_15.md):
    - SWING: x6.00 (fixed)
    - FIXED: x10.00 or other explicit (typically when SL missing)
    - Dynamisk: ≥x7.50 (formula-based)
    
    Args:
        leverage: Leverage value (Decimal, float, int, or string)
        has_sl: Whether signal has SL
    
    Returns:
        "Swing", "Dynamisk", or "FIXED"
    
    Examples:
        detect_trade_type(6.00, True) -> "Swing"
        detect_trade_type(10.00, False) -> "FIXED"
        detect_trade_type(13.56, True) -> "Dynamisk"
    """
    try:
        lev = Decimal(str(leverage))
        
        # SWING: exactly 6.00
        if lev == Decimal("6.00"):
            return "Swing"
        
        # FIXED: exactly 10.00 and no SL (safety lock per CLIENT SPEC)
        if lev == Decimal("10.00") and not has_sl:
            return "FIXED"
        
        # Dynamisk: >= 7.50
        if lev >= Decimal("7.50"):
            return "Dynamisk"
        
        # Default to Swing for edge cases
        return "Swing"
    
    except Exception:
        return "Dynamisk"  # Safe default

