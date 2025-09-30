import re
from decimal import Decimal

# More flexible symbol patterns - handle all formats
SYM_RE   = r"([A-Z0-9]{1,}USDT|#[A-Z0-9]{1,}\/USDT|#[A-Z0-9]{1,}\/USD|[A-Z0-9]{1,}\/USDT|#([A-Z0-9]{1,})USDT|([A-Z0-9]{1,})USDT\.P|#([A-Z0-9]{1,})ETHUSDT|([A-Z0-9]{1,})ETHUSDT)"
LONG_RE  = r"(LONG|LÅNG|BUY|🟢|💎\s*BUY|🔴\s*Long|Opening\s+LONG|Position:\s*LONG|Long\s+Set-Up)"
SHORT_RE = r"(SHORT|SELL|🔴|💎\s*SELL|Opening\s+SHORT|Position:\s*SHORT|Short\s+Set-Up|premium\s+signals\s+short)"

def _clean_symbol(s: str) -> str:
    s = s.upper().replace("#", "").replace("/", "").replace(".P", "")
    return s if s.endswith("USDT") else s + "USDT"

def _dir(text: str):
    if re.search(SHORT_RE, text, re.I): return "SELL"
    if re.search(LONG_RE,  text, re.I): return "BUY"
    return None

def parse_signal(text: str):
    # Keep original text for numbered format matching
    original_text = (text or "").strip()
    t = " ".join(original_text.split())

    m_sym = re.search(SYM_RE, t, re.I)
    if not m_sym: return None
    symbol = _clean_symbol(m_sym.group(1))

    direction = _dir(t)
    if not direction: 
        # Try to infer direction from context
        if re.search(r"premium\s+signals\s+short", t, re.I):
            direction = "SELL"
        elif re.search(r"long\s+set-up", t, re.I):
            direction = "BUY"
        else:
            # If no direction found, we'll try to infer it later after parsing entries and targets
            direction = None

    # entries: handle all entry patterns
    entries: list[str] = []
    
    # First try numbered format with original text (preserves newlines)
    m_ent_numbered = re.search(r"Entry\s*:\s*\n\s*1\)\s*([0-9]+(?:\.[0-9]+)?)\s*\n\s*2\)\s*([0-9]+(?:\.[0-9]+)?)", original_text, re.I)
    if m_ent_numbered:
        entries = [m_ent_numbered.group(1), m_ent_numbered.group(2)]
    else:
        # Try single numbered entry
        m_ent_single = re.search(r"Entry\s*:\s*\n\s*1\)\s*([0-9]+(?:\.[0-9]+)?)", original_text, re.I)
        if m_ent_single:
            entries = [m_ent_single.group(1)]
        else:
                # Try different entry patterns - comprehensive list
                m_ent = re.search(r"\bentries?\s*[:=]\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"\bentry\s*[:=]\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"Entry Zone:\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"🛒\s*Entry Zone:\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"➤\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"Ingång:\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"Ingångskurs:\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"Entry Price:\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"Entry:\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"Entry\s+([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"👉\s*Ingång:\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"📊\s*Entry Price:\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"Entry\s+([0-9\.,\s\-]+)\s*-\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"💰\s*Price:\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"Price:\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"Entrada\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"Coin.*Entry\s*([0-9\.,\s\-]+)", t, re.I)
    
    if m_ent:
                    # Handle different entry formats
                    if len(m_ent.groups()) > 1:
                        # Multiple numbered entries (1) 0.08255, 2) 0.08007, etc.)
                        entries = [group.strip() for group in m_ent.groups() if group and group.strip()]
                    else:
                        # Handle entry zone format "0.41464960 - 0.43034368"
                        entry_text = m_ent.group(1).strip()
                        if " - " in entry_text:
                            # Split on " - " and take both values
                            parts = entry_text.split(" - ")
                            entries = [p.strip() for p in parts if p.strip()]
                        else:
                            # Split on commas
                            entries = [x.strip() for x in entry_text.split(",") if x.strip()]
    
    if not entries:
        # Try to find multiple ➤ entries
        arrow_entries = re.findall(r"➤\s*([0-9]+(?:\.[0-9]+)?)", t, re.I)
        if arrow_entries:
            entries = arrow_entries
    else:
        m_at = re.search(r"\b(?:at|@)\s*([0-9]+(?:\.[0-9]+)?)", t, re.I)
        if m_at: entries = [m_at.group(1)]
    
    if not entries: return None
    entries = entries[:2]  # cap at two (planner may synthesize second if one only)

    # SL - try multiple patterns - comprehensive list
    m_sl = re.search(r"\bsl\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", t, re.I) or \
           re.search(r"Stop loss:\s*([0-9]+(?:\.[0-9]+)?)", t, re.I) or \
           re.search(r"🚫\s*Stop loss:\s*([0-9]+(?:\.[0-9]+)?)", t, re.I) or \
           re.search(r"Stop-Loss:\s*([0-9]+(?:\.[0-9]+)?)", t, re.I) or \
           re.search(r"StopLoss:\s*([0-9]+(?:\.[0-9]+)?)", t, re.I) or \
           re.search(r"Stop\s*:\s*([0-9]+(?:\.[0-9]+)?)", t, re.I) or \
           re.search(r"Stop\s*=\s*([0-9]+(?:\.[0-9]+)?)", t, re.I) or \
           re.search(r"❌\s*StopLoss:\s*([0-9]+(?:\.[0-9]+)?)", t, re.I) or \
           re.search(r"🛑Stop\s*:\s*([0-9]+(?:\.[0-9]+)?)", t, re.I) or \
           re.search(r"Stoploss:\s*([0-9]+(?:\.[0-9]+)?)", t, re.I) or \
           re.search(r"Stoploss\s*=\s*([0-9]+(?:\.[0-9]+)?)", t, re.I)
    sl = m_sl.group(1) if m_sl else None

    # TPs - try multiple patterns - comprehensive list
    tps = []
    
    # First try numbered format with original text (preserves newlines)
    m_tps_numbered = re.search(r"Targets\s*:\s*\n\s*1\)\s*([0-9]+(?:\.[0-9]+)?)\s*\n\s*2\)\s*([0-9]+(?:\.[0-9]+)?)\s*\n\s*3\)\s*([0-9]+(?:\.[0-9]+)?)\s*\n\s*4\)\s*([0-9]+(?:\.[0-9]+)?)", original_text, re.I)
    if m_tps_numbered:
        tps = [m_tps_numbered.group(1), m_tps_numbered.group(2), m_tps_numbered.group(3), m_tps_numbered.group(4)]
    else:
        # Try 2 numbered targets
        m_tps_2 = re.search(r"Targets\s*:\s*\n\s*1\)\s*([0-9]+(?:\.[0-9]+)?)\s*\n\s*2\)\s*([0-9]+(?:\.[0-9]+)?)", original_text, re.I)
        if m_tps_2:
            tps = [m_tps_2.group(1), m_tps_2.group(2)]
        else:
            # Try single numbered target
            m_tps_1 = re.search(r"Targets\s*:\s*\n\s*1\)\s*([0-9]+(?:\.[0-9]+)?)", original_text, re.I)
            if m_tps_1:
                tps = [m_tps_1.group(1)]
            else:
                # Try other patterns
                m_tps = re.search(r"\btps?\s*[:=]\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"Target\s+[0-9]+:\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"🎯\s*Target\s+[0-9]+:\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"[🥇🥈🏁]\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"Mål\s+[0-9]+:\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"🎯\s*Mål\s+[0-9]+:\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"Targets:\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"Targets\s*:\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"Take-Profit\s*:\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"TP[0-9]*:\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"🎯\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"Objetivo\s*🎯\s*([0-9\.,\s\-]+)", t, re.I) or \
                        re.search(r"Target\s*🎯\s*([0-9\.,\s\-]+)", t, re.I)
        
                if m_tps:
                    # Handle different target formats
                    if len(m_tps.groups()) > 1:
                        # Multiple numbered targets (1) 0.08302, 2) 0.08474, etc.)
                        tps = [group.strip() for group in m_tps.groups() if group and group.strip()]
                    else:
                        # Handle comma-separated targets
                        target_text = m_tps.group(1).strip()
                        tps = [x.strip() for x in target_text.split(",") if x.strip()]
    
    if not tps:
        # Try to find multiple medal targets
        medal_targets = re.findall(r"[🥇🥈🏁]\s*([0-9]+(?:\.[0-9]+)?)", t, re.I)
        if medal_targets:
            tps = medal_targets
        else:
            # Try numbered targets (TP1, TP2, etc.)
            numbered_targets = re.findall(r"TP[0-9]*:\s*([0-9]+(?:\.[0-9]+)?)", t, re.I)
            if numbered_targets:
                tps = numbered_targets
            else:
                # Try Mål patterns
                mal_targets = re.findall(r"Mål\s+[0-9]+:\s*([0-9]+(?:\.[0-9]+)?)", t, re.I)
                if mal_targets:
                    tps = mal_targets
                else:
                    # Try multi-line targets in original text
                    multi_line_targets = re.findall(r"Objetivo\s*🎯\s*\n\s*([0-9\.,\s\-]+)", original_text, re.I)
                    if multi_line_targets:
                        # Split by newlines and clean up
                        target_text = multi_line_targets[0]
                        tps = [x.strip() for x in target_text.split() if x.strip() and re.match(r'^[0-9]+(?:\.[0-9]+)?$', x.strip())]
                    else:
                        # Try single line targets with multiple values
                        single_line_targets = re.findall(r"Objetivo\s*🎯\s*([0-9\.,\s\-]+)", t, re.I)
                        if single_line_targets:
                            target_text = single_line_targets[0]
                            tps = [x.strip() for x in target_text.split() if x.strip() and re.match(r'^[0-9]+(?:\.[0-9]+)?$', x.strip())]
    else:
        m_tp1 = re.search(r"\btp\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", t, re.I)
        if m_tp1: tps = [m_tp1.group(1)]

    # leverage/mode policy
    mode = None
    lev  = None

    if re.search(r"\bSWING\b", t, re.I):   mode, lev = "SWING", 6
    if re.search(r"\bFAST\b",  t, re.I):   mode, lev = "FAST", 10

    m_lev = re.search(r"\blev(?:erage)?\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", t, re.I) or \
            re.search(r"Hävstång:\s*([0-9]+(?:\.[0-9]+)?)", t, re.I) or \
            re.search(r"Leverage:\s*([0-9]+(?:\.[0-9]+)?)", t, re.I) or \
            re.search(r"Leverage\s*=\s*([0-9]+(?:\.[0-9]+)?)", t, re.I) or \
            re.search(r"X([0-9]+)", t, re.I)
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

    # Infer direction from entry vs target prices if not specified
    if not direction and entries and tps:
        try:
            entry_price = Decimal(entries[0])
            # Check if targets are generally higher (LONG) or lower (SHORT) than entry
            target_prices = [Decimal(tp) for tp in tps if tp.strip()]
            if target_prices:
                avg_target = sum(target_prices) / len(target_prices)
                direction = "BUY" if avg_target > entry_price else "SELL"
        except (ValueError, TypeError):
            pass
    
    # If still no direction, return None
    if not direction:
        return None

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