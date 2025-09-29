import re
from decimal import Decimal


def parse_signal(text: str) -> dict:
    """Parse raw Telegram signal text into structured dict."""

    text = text.upper()

    # Default template
    signal = {
        "symbol": None,
        "direction": None,
        "entries": [],
        "tps": [],
        "sl": None,
        "leverage": None,
    }

    # Symbol (e.g., BTCUSDT, BICO/USDT)
    m = re.search(r"([A-Z]{3,5})[\/]?USDT", text)
    if m:
        signal["symbol"] = m.group(1) + "USDT"

    # Direction (BUY / SELL / LONG / SHORT)
    if "BUY" in text or "LONG" in text:
        signal["direction"] = "BUY"
    elif "SELL" in text or "SHORT" in text:
        signal["direction"] = "SELL"

    # Entry zone
    m = re.search(r"ENTRY.*?([\d\.]+).*?([\d\.]+)", text)
    if m:
        signal["entries"] = [Decimal(m.group(1)), Decimal(m.group(2))]
    else:
        m = re.findall(r"([\d\.]+)", text)
        if m:
            # Fallback: first two numbers are entries
            signal["entries"] = [Decimal(x) for x in m[:2]]

    # Take Profits (TP1, TP2, TP3...)
    for m in re.findall(r"TP\d?\s*[:\-]?\s*([\d\.]+)", text):
        signal["tps"].append(Decimal(m))

    # Stop Loss (SL)
    m = re.search(r"SL\s*[:\-]?\s*([\d\.]+)", text)
    if m:
        signal["sl"] = Decimal(m.group(1))

    # Leverage
    m = re.search(r"LEV(?:ERAGE)?\s*[:\-]?\s*(\d+)", text)
    if m:
        signal["leverage"] = int(m.group(1))

    return signal