import re
from decimal import Decimal

# More flexible symbol patterns
SYM_RE   = r"([A-Z]{2,}USDT|#[A-Z]{2,}\/USDT|#[A-Z]{2,}\/USD)"
LONG_RE  = r"(LONG|BUY|🟢|💎\s*BUY)"
SHORT_RE = r"(SHORT|SELL|🔴|💎\s*SELL)"

def _clean_symbol(s: str) -> str:
    s = s.upper().replace("#", "").replace("/", "")
    return s if s.endswith("USDT") else s + "USDT"

def _dir(text: str):
    if re.search(SHORT_RE, text, re.I): return "SELL"
    if re.search(LONG_RE,  text, re.I): return "BUY"
    return None

def parse_signal(text: str):
    t = " ".join((text or "").strip().split())

    m_sym = re.search(SYM_RE, t, re.I)
    if not m_sym: return None
    symbol = _clean_symbol(m_sym.group(1))

    direction = _dir(t)
    if not direction: return None

    # entries: "entries=60000,59800" | "entry=60000" | "at 60000" | "Entry Zone: X - Y"
    entries: list[str] = []
    
    # Try different entry patterns
    m_ent = re.search(r"\bentries?\s*[:=]\s*([0-9\.,\s]+)", t, re.I) or \
            re.search(r"\bentry\s*[:=]\s*([0-9\.,\s]+)", t, re.I) or \
            re.search(r"Entry Zone:\s*([0-9\.,\s]+)", t, re.I) or \
            re.search(r"🛒\s*Entry Zone:\s*([0-9\.,\s]+)", t, re.I)
    
    if m_ent:
        # Handle entry zone format "0.41464960 - 0.43034368"
        entry_text = m_ent.group(1).strip()
        if " - " in entry_text:
            # Split on " - " and take both values
            parts = entry_text.split(" - ")
            entries = [p.strip() for p in parts if p.strip()]
        else:
            # Split on commas
            entries = [x.strip() for x in entry_text.split(",") if x.strip()]
    else:
        m_at = re.search(r"\b(?:at|@)\s*([0-9]+(?:\.[0-9]+)?)", t, re.I)
        if m_at: entries = [m_at.group(1)]
    
    if not entries: return None
    entries = entries[:2]  # cap at two (planner may synthesize second if one only)

    # SL - try multiple patterns
    m_sl = re.search(r"\bsl\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", t, re.I) or \
           re.search(r"Stop loss:\s*([0-9]+(?:\.[0-9]+)?)", t, re.I) or \
           re.search(r"🚫\s*Stop loss:\s*([0-9]+(?:\.[0-9]+)?)", t, re.I)
    sl = m_sl.group(1) if m_sl else None

    # TPs - try multiple patterns
    tps = []
    m_tps = re.search(r"\btps?\s*[:=]\s*([0-9\.,\s]+)", t, re.I) or \
            re.search(r"Target\s+[0-9]+:\s*([0-9\.,\s]+)", t, re.I) or \
            re.search(r"🎯\s*Target\s+[0-9]+:\s*([0-9\.,\s]+)", t, re.I)
    
    if m_tps:
        tps = [x.strip() for x in m_tps.group(1).split(",") if x.strip()]
    else:
        m_tp1 = re.search(r"\btp\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", t, re.I)
        if m_tp1: tps = [m_tp1.group(1)]

    # leverage/mode policy
    mode = None
    lev  = None

    if re.search(r"\bSWING\b", t, re.I):   mode, lev = "SWING", 6
    if re.search(r"\bFAST\b",  t, re.I):   mode, lev = "FAST", 10

    m_lev = re.search(r"\blev(?:erage)?\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", t, re.I)
    if m_lev and lev is None:
        f = float(m_lev.group(1))
        if abs(f - 6.0) < 1e-9:
            mode, lev = "SWING", 6
        elif f >= 7.5 and f < 10:
            mode, lev = "DYNAMIC", f
        elif f >= 10:
            mode, lev = "FAST", int(round(f))
        else:
            # forbidden leverage gap (6, 7.5)
    return None

    # Set defaults if not specified
    if lev is None:
        if not sl:
            # missing SL ⇒ auto SL −2% and lock FAST x10
            mode, lev = "FAST", 10
        else:
            # default DYNAMIC 7.5 if SL present and no mode/lev given
            mode, lev = "DYNAMIC", 7.5

    # Auto SL −2% if missing
    if not sl:
        e0 = Decimal(entries[0])
        sl = str(e0 * (Decimal("0.98") if direction == "BUY" else Decimal("1.02")))

    return {
        "symbol": symbol,
        "direction": direction,   # BUY/SELL
        "entries": entries,       # up to 2
        "sl": sl,
        "tps": tps,               # 0..N
        "mode": mode,             # SWING/DYNAMIC/FAST
        "leverage": lev,          # 6, ≥7.5, ≥10
    }