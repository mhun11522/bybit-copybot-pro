import re
from typing import Optional

# Patterns to capture common variants across 14–16 channels
# Supports crypto (BTCUSDT, BTC/USDT) with # prefix or standalone FOREX (GBPNZD, EURUSD - 6 chars)
# Also supports "Instrument: BTCUSD" format and GOLD trading
# Word boundary before USDT prevents matching "FOLLOWED" as "LLOWEDUSDT"
SYMBOL_RE   = re.compile(r"#([A-Z0-9]{2,10})(?:/USDT|USDT|/USDC|USDC)\b|#?([A-Z]{2,4})(?:/USDT|USDT)\b|^([A-Z]{6})\s+(?:BUY|SELL|LONG|SHORT)|(?:Instrument|Symbol)[\s:：]+([A-Z]{3,10}(?:USD|USDT|USDC)?)|🌟GOLD\s+(?:Buy|Sell|Long|Short)", re.I | re.M)
SIDE_RE     = re.compile(r"\b(LONG|BUY|SHORT|SELL|LARGA|CORTA)\b", re.I)
ENTRY_LIST  = re.compile(r"(?:entry|entries|entrada|entradas|вход)(?:\s+price)?[\s:：🚀]+\$?(.+?)(?=\n.*(?:target|tp|stop|sl|leverage)|$)", re.I | re.DOTALL)
ENTRY_ONE   = re.compile(r"(?:entry|entrada|вход)(?:\s+price)?[\s:：🚀]+\$?([0-9\.]+)", re.I)
# GOLD entry pattern (e.g., "🌟GOLD Buy 3873-3871")
GOLD_ENTRY  = re.compile(r"🌟GOLD\s+(?:Buy|Sell|Long|Short)\s+([0-9\.]+)(?:-([0-9\.]+))?", re.I)
# FOREX-style entry (e.g., "GBPNZD SELL 2.3185")
FOREX_ENTRY = re.compile(r"\b(?:BUY|SELL|LONG|SHORT)\s+\$?([0-9]+\.[0-9]+)", re.I)
SL_RE       = re.compile(r"(?:sl|stop[-\s]?loss|stoploss|stop)[\s:：]+\$?([0-9\.]+)|❎STOP\s+LOSS\s+([0-9\.]+)", re.I)
TPS_RE      = re.compile(r"(?:tp|targets?|objetivo|objetivos|цель)[\s:：]+\$?(.+?)(?=\n|$)|🔛TP\s*=\s*([0-9\.]+)|(?:^|\n)\s*TP\d*[\s:：]+\$?([0-9]+(?:\.[0-9]+)?)", re.I | re.DOTALL)
LEV_RE      = re.compile(r"(?:lev|leverage|апаланч|apalancamiento)[\s:：⬆️]?\s*([0-9]+(?:\.[0-9]+)?)x?", re.I)

UPDATE_RE   = re.compile(r"\b(update|cancel|adjust|закрыт|закрываем|закрыть|close|close partial|closed)\b", re.I)

def _symbol(text: str) -> Optional[str]:
    # Search for symbol directly (don't remove direction words - FOREX needs them)
    m = SYMBOL_RE.search(text.upper())
    if not m: return None
    
    # Check which group matched
    if m.group(1):  # Crypto with # prefix (e.g., #BTC/USDT, #BTCUSDT)
        s = m.group(1).upper()
        if not s.endswith("USDT") and not s.endswith("USDC"):
            s = s + "USDT"
        if s.endswith("USDC"): 
            s = s[:-4] + "USDT"
        return s
    elif m.group(2):  # Short crypto without full suffix (e.g., #BTC, #SOMI)
        return m.group(2).upper() + "USDT"
    elif m.group(3):  # FOREX pair at start of line (e.g., "GBPNZD SELL")
        return m.group(3).upper() + "USDT"
    elif m.group(4):  # Instrument: BTCUSD or Instrument: BTCUSDT format
        s = m.group(4).upper()
        # Convert BTCUSD (inverse) to BTCUSDT (linear perpetual)
        if s.endswith("USD") and not s.endswith("USDT") and not s.endswith("USDC"):
            s = s + "T"  # BTCUSD → BTCUSDT
        if s.endswith("USDC"):
            s = s[:-4] + "USDT"
        if not s.endswith("USDT"):
            s = s + "USDT"
        return s
    elif m.group(5):  # GOLD trading (🌟GOLD Buy/Sell)
        return "GOLDUSDT"  # Convert GOLD to GOLDUSDT for Bybit
    return None

def _side(text: str) -> Optional[str]:
    m = SIDE_RE.search(text)
    if not m: return None
    v = m.group(1).upper()
    return "BUY" if v in ("LONG","BUY","LARGA") else "SELL"

def _list_numbers(blob: str) -> list[str]:
    # Extract all numbers from text, ignoring numbered list markers like "1)", "1:", "1."
    numbers = re.findall(r"(?<!\d)(\d+\.\d+|\d+)(?!\d)", blob)
    # Filter out small integers that are likely list markers (1-9)
    return [x for x in numbers if not (re.match(r"^[1-9]$", x))]

def _entries(text: str) -> list[str]:
    # Try GOLD entry pattern first
    gold_m = GOLD_ENTRY.search(text)
    if gold_m:
        entries = [gold_m.group(1)]
        if gold_m.group(2):  # Second entry exists
            entries.append(gold_m.group(2))
        return entries
    
    # Try standard entry patterns
    m = ENTRY_LIST.search(text) or ENTRY_ONE.search(text)
    
    # If no standard entry, try FOREX-style (e.g., "GBPNZD SELL 2.3185")
    if not m:
        forex_m = FOREX_ENTRY.search(text)
        if forex_m:
            return [forex_m.group(1)]
        return []
    
    # Extract all numbers from the captured section, removing $ symbols
    entry_text = m.group(1).replace('$', '').replace(',', '')
    
    # The regex is non-greedy and stops too early. 
    # Let's manually extend until we hit a keyword
    start_pos = m.end(1)
    remaining = text[start_pos:]
    
    # Keep adding lines until we hit a keyword
    for line in remaining.split('\n'):
        if re.search(r'(target|tp|stop|sl|leverage|📈|🎯|🛑)', line, re.I):
            break
        # If line has numbers, include it
        if re.search(r'\d+\.\d+', line):
            entry_text += '\n' + line.replace('$', '').replace(',', '')
    
    # Find all decimal numbers and integers (but skip single digits 1-9 which are list markers)
    all_numbers = re.findall(r'\d+\.\d+|\d{2,}', entry_text)
    
    if not all_numbers:
        return []
    if len(all_numbers) == 1:
        return [all_numbers[0]]
    # Return first 2 entries
    return all_numbers[:2]

def _sl(text: str) -> Optional[str]:
    m = SL_RE.search(text)
    if not m: return None
    # Check both groups for different patterns
    return m.group(1) if m.group(1) else m.group(2)

def _tps(text: str) -> list[str]:
    # First, try to find numbered TPs (TP1:, TP2:, TP3:, etc.)
    numbered_tps = re.findall(r'(?:^|\n)\s*TP\d*[\s:：]+\$?([0-9]+(?:\.[0-9]+)?)', text, re.I)
    if numbered_tps:
        return numbered_tps[:6]  # Max 6 TPs
    
    # Fallback to original pattern matching
    m = TPS_RE.search(text)
    if not m: return []
    
    # Check if it's the emoji pattern (🔛TP =)
    if m.group(2):
        return [m.group(2)]
    
    # Extract all decimal numbers from the targets section, removing $ and commas
    tp_text = m.group(1).replace('$', '').replace(',', '')
    # Find all numbers (including decimals), but skip single digits 1-9 which are list markers
    all_nums = re.findall(r'\d+\.\d+|\d{2,}', tp_text)
    return all_nums[:6]  # Max 6 TPs

def _lev(text: str) -> Optional[str]:
    m = LEV_RE.search(text); return m.group(1) if m else None

def is_update_or_spam(text: str) -> bool:
    return bool(UPDATE_RE.search(text))

def parse_signal(text: str) -> Optional[dict]:
    if is_update_or_spam(text):
        return None

    sym = _symbol(text)
    side = _side(text)
    if not sym or not side:
        return None

    entries = _entries(text)
    sl = _sl(text)
    tps = _tps(text)
    lev = _lev(text)

    return {
        "symbol": sym,
        "direction": side,
        "entries": entries,
        "sl": sl,
        "tps": tps,
        "leverage_hint": lev
    }
