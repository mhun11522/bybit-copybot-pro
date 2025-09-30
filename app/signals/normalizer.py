import re
import hashlib
import time
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from app import settings
from app.storage.db import aiosqlite, DB_PATH


def parse_signal(text: str) -> Optional[Dict]:
    """Parse raw Telegram signal text into structured dict.

    Supports multiple formats:
    1. FIDDE format: "Exchange: BYBIT, BINGX 📍Mynt: #CATI/USDT 🟢 LÅNG ..."
    2. Smart Crypto format: "🟢 Opening LONG 📈 🟢 Symbol: SUIUSDT ..."
    3. Lux Leak format: "🔴 Long CHESSUSDT Entry : 1) 0.08255 2) 0.08007 ..."
    4. Simple format: "#RONINUSDT | SHORT • Entry Zone: 0.673 ..."
    5. Bitcoin Bullets format: "📌$ZEN/USDT LONG Leverage: 5-10x ..."
    """

    raw = text
    text = text.upper()

    signal = {
        "symbol": None,
        "direction": None,
        "entries": [],
        "tps": [],
        "sl": None,
        "leverage": None,
        "mode": "DYNAMIC",  # Default mode
        "raw_text": raw,
    }

    # Extract symbol - handle multiple formats
    symbol = _extract_symbol(text)
    if symbol:
        signal["symbol"] = symbol

    # Extract direction
    direction = _extract_direction(text)
    if direction:
        signal["direction"] = direction

    # Extract mode (SWING, DYNAMIC, FIXED)
    mode = _extract_mode(text)
    if mode:
        signal["mode"] = mode

    # Extract entries - handle multiple formats
    entries = _extract_entries(text)
    if entries:
        signal["entries"] = entries

    # Extract targets/TPs
    tps = _extract_targets(text)
    if tps:
        signal["tps"] = tps

    # Extract stop loss
    sl = _extract_stop_loss(text)
    if sl:
        signal["sl"] = sl

    # Extract leverage
    leverage = _extract_leverage(text)
    if leverage:
        signal["leverage"] = leverage
    else:
        # Set default based on mode
        if signal["mode"] == "SWING":
            signal["leverage"] = settings.DEFAULT_LEVERAGE_SWING
        elif signal["mode"] == "FIXED":
            signal["leverage"] = settings.DEFAULT_LEVERAGE_FIXED
        else:
            signal["leverage"] = settings.DEFAULT_LEVERAGE_DYNAMIC

    # Validate required fields
    if not signal["symbol"] or not signal["direction"] or not signal["entries"]:
        return None

    return signal


def _extract_symbol(text: str) -> Optional[str]:
    """Extract symbol from various formats."""
    
    # Format 1: FIDDE - "📍Mynt: #CATI/USDT" or "Mynt: #1000SHIB/USDT"
    m = re.search(r"MYNT:\s*#?([A-Z0-9]+)/(USDT|USDC|BUSD)", text)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    
    # Format 2: Smart Crypto - "🟢 Symbol: SUIUSDT"
    m = re.search(r"SYMBOL:\s*([A-Z0-9]+USDT)", text)
    if m:
        return m.group(1)
    
    # Format 3: Lux Leak - "🔴 Long CHESSUSDT" or "🔴 Long SOLUSDT"
    m = re.search(r"(?:🔴|🟢)\s*(?:LONG|SHORT)\s+([A-Z0-9]+USDT)", text)
    if m:
        return m.group(1)
    
    # Format 4: Simple - "#RONINUSDT | SHORT" or "#FLOWUSDT | SHORT"
    m = re.search(r"#([A-Z0-9]+USDT)\s*\|", text)
    if m:
        return m.group(1)
    
    # Format 5: Bitcoin Bullets - "📌$ZEN/USDT LONG"
    m = re.search(r"\$([A-Z0-9]+)/USDT", text)
    if m:
        return f"{m.group(1)}USDT"
    
    # Format 6: Generic - "BTCUSDT LONG" or "ETHUSDT SHORT"
    m = re.search(r"([A-Z0-9]+USDT)\s+(?:LONG|SHORT)", text)
    if m:
        return m.group(1)
    
    # Format 7: With dots - "1000000MOGUSDT.P"
    m = re.search(r"([A-Z0-9]+USDT\.P)", text)
    if m:
        return m.group(1).replace(".P", "USDT")
    
    # Format 8: JUP/USD format - "#JUP/USD" (convert to JUPUSDT)
    m = re.search(r"#([A-Z0-9]+)/(USD|USDT)", text)
    if m:
        return f"{m.group(1)}USDT"
    
    return None


def _extract_direction(text: str) -> Optional[str]:
    """Extract direction from various formats."""
    
    # JUP signal format - "💎 BUY #JUP/USD" (check first)
    if "💎 BUY" in text or "BUY #" in text:
        return "BUY"
    elif "💎 SELL" in text or "SELL #" in text:
        return "SELL"
    
    # Check for BUY/SELL with # (more specific)
    if re.search(r"BUY\s*#", text):
        return "BUY"
    elif re.search(r"SELL\s*#", text):
        return "SELL"
    
    # Swedish formats
    if any(word in text for word in ["LÅNG", "LONG", "🟢", "🔴 Long"]):
        return "BUY"
    elif any(word in text for word in ["SHORT", "🔵 Opening SHORT", "🔴 Short"]):
        return "SELL"
    
    # Check for explicit LONG/SHORT (but not in context like "SHORT/MID TERM")
    if "LONG" in text and not re.search(r"SHORT/MID|MID.*TERM", text):
        return "BUY"
    elif "SHORT" in text and not re.search(r"SHORT/MID|MID.*TERM", text):
        return "SELL"
    
    return None


def _extract_mode(text: str) -> Optional[str]:
    """Extract trading mode."""
    
    if "SWING" in text:
        return "SWING"
    elif "DYNAMIC" in text or "Dynamisk" in text:
        return "DYNAMIC"
    elif "FIXED" in text or "Fast" in text:
        return "FIXED"
    elif "CROSS" in text and any(x in text for x in ["25X", "50X", "75X"]):
        return "FIXED"  # High leverage usually means fixed
    elif "ISOLATED" in text:
        return "FIXED"
    
    return None


def _extract_entries(text: str) -> List[Decimal]:
    """Extract entry prices from various formats."""
    entries = []
    
    # Format 1: FIDDE - "👉 Ingång: 0.1128 - 0.1098" or "👉 Ingångskurs: 0.01439 - 0.01400"
    m = re.search(r"INGÅNG(?:SKURS)?:\s*([\d\.]+)\s*[-–]\s*([\d\.]+)", text)
    if m:
        entries = [Decimal(m.group(1)), Decimal(m.group(2))]
    
    # Format 2: Lux Leak - "Entry : 1) 0.08255 2) 0.08007"
    elif re.search(r"ENTRY\s*:\s*1\)\s*([\d\.]+)\s*2\)\s*([\d\.]+)", text):
        matches = re.findall(r"ENTRY\s*:\s*1\)\s*([\d\.]+)\s*2\)\s*([\d\.]+)", text)
        if matches:
            entries = [Decimal(matches[0][0]), Decimal(matches[0][1])]
    
    # Format 3: Simple - "• Entry Zone: 0.673" (single entry)
    elif re.search(r"ENTRY\s*ZONE:\s*([\d\.]+)", text):
        m = re.search(r"ENTRY\s*ZONE:\s*([\d\.]+)", text)
        if m:
            entries = [Decimal(m.group(1))]
    
    # Format 4: Smart Crypto - "💰 Price: 3.0166" (single entry)
    elif re.search(r"PRICE:\s*([\d\.]+)", text):
        m = re.search(r"PRICE:\s*([\d\.]+)", text)
        if m:
            entries = [Decimal(m.group(1))]
    
    # Format 5: Bitcoin Bullets - "Entry: 7.26" (single entry)
    elif re.search(r"ENTRY:\s*([\d\.]+)", text):
        m = re.search(r"ENTRY:\s*([\d\.]+)", text)
        if m:
            entries = [Decimal(m.group(1))]
    
    # Format 6: Multiple entries - "Entry: 0.8705 - 0.8727"
    elif re.search(r"ENTRY\s*[:\-]?\s*([\d\.]+)\s*[-–]\s*([\d\.]+)", text):
        m = re.search(r"ENTRY\s*[:\-]?\s*([\d\.]+)\s*[-–]\s*([\d\.]+)", text)
        if m:
            entries = [Decimal(m.group(1)), Decimal(m.group(2))]
    
    # Format 7: Multiple entries with commas - "Entry: 6.600 , 6.800 , 6.900"
    elif re.search(r"ENTRY:\s*([\d\.,\s]+)", text):
        m = re.search(r"ENTRY:\s*([\d\.,\s]+)", text)
        if m:
            entry_str = m.group(1).replace(",", "").replace(" ", "")
            entry_parts = [x for x in entry_str.split() if x]
            entries = [Decimal(x) for x in entry_parts if x]
    
    # Format 8: JUP signal - "🛒 Entry Zone: 0.41464960 - 0.43034368"
    elif re.search(r"ENTRY\s*ZONE:\s*([\d\.]+)\s*[-–]\s*([\d\.]+)", text):
        m = re.search(r"ENTRY\s*ZONE:\s*([\d\.]+)\s*[-–]\s*([\d\.]+)", text)
        if m:
            entries = [Decimal(m.group(1)), Decimal(m.group(2))]
    
    return entries


def _extract_targets(text: str) -> List[Decimal]:
    """Extract target prices from various formats."""
    targets = []
    
    # Format 1: FIDDE - "🎯 Mål 1: 0.1139 🎯 Mål 2: 0.1150 ..."
    mål_matches = re.findall(r"MÅL\s*\d+:\s*([\d\.]+)", text)
    if mål_matches:
        targets = [Decimal(x) for x in mål_matches]
    
    # Format 2: Lux Leak - "Targets : 1) 0.08302 2) 0.08474 ..."
    elif re.search(r"TARGETS?\s*:\s*1\)", text):
        target_matches = re.findall(r"\d+\)\s*([\d\.]+)", text)
        targets = [Decimal(x) for x in target_matches]
    
    # Format 3: Simple - "• Targets: 0.670, 0.653, 0.633, 0.606"
    elif re.search(r"TARGETS?:\s*([\d\.,\s]+)", text):
        m = re.search(r"TARGETS?:\s*([\d\.,\s]+)", text)
        if m:
            target_str = m.group(1).replace(" ", "")
            target_parts = [x for x in target_str.split(",") if x]
            targets = [Decimal(x) for x in target_parts if x]
    
    # Format 4: Smart Crypto - "🎯 TP1: 3.2300 🎯 TP2: 3.4500 ..."
    elif re.search(r"TP\d+:\s*([\d\.]+)", text):
        tp_matches = re.findall(r"TP\d+:\s*([\d\.]+)", text)
        targets = [Decimal(x) for x in tp_matches]
    
    # Format 5: Bitcoin Bullets - "Targets: 7.4 - 7.6 - 8.5"
    elif re.search(r"TARGETS?:\s*([\d\.\s\-]+)", text):
        m = re.search(r"TARGETS?:\s*([\d\.\s\-]+)", text)
        if m:
            target_str = m.group(1).replace(" ", "")
            target_parts = [x for x in target_str.split("-") if x]
            targets = [Decimal(x) for x in target_parts if x]
    
    # Format 6: JUP signal - "🎯 Target 1: 0.44423680 (4.06%)"
    elif re.search(r"TARGET\s*\d+:\s*([\d\.]+)", text):
        target_matches = re.findall(r"TARGET\s*\d+:\s*([\d\.]+)", text)
        targets = [Decimal(x) for x in target_matches]
    
    return targets


def _extract_stop_loss(text: str) -> Optional[Decimal]:
    """Extract stop loss from various formats."""
    
    # Format 1: FIDDE - "❌ StopLoss: 0.1058"
    m = re.search(r"STOPLOSS?:\s*([\d\.]+)", text)
    if m:
        return Decimal(m.group(1))
    
    # Format 2: Lux Leak - "🛑Stop : 0.07734"
    m = re.search(r"STOP\s*:\s*([\d\.]+)", text)
    if m:
        return Decimal(m.group(1))
    
    # Format 3: Simple - "• Stop-Loss: 0.693"
    m = re.search(r"STOP\s*[-_]?LOSS:\s*([\d\.]+)", text)
    if m:
        return Decimal(m.group(1))
    
    # Format 4: Smart Crypto - "🛑 Stop Loss: 2.8500"
    m = re.search(r"STOP\s*LOSS:\s*([\d\.]+)", text)
    if m:
        return Decimal(m.group(1))
    
    # Format 5: Bitcoin Bullets - "SL: 7.072"
    m = re.search(r"SL:\s*([\d\.]+)", text)
    if m:
        return Decimal(m.group(1))
    
    # Format 6: JUP signal - "🚫 Stop loss: 0.40993280 (3.98%)"
    m = re.search(r"STOP\s*LOSS:\s*([\d\.]+)", text)
    if m:
        return Decimal(m.group(1))
    
    return None


def _extract_leverage(text: str) -> Optional[int]:
    """Extract leverage from various formats."""
    
    # Format 1: FIDDE - "🌐 Hävstång: 20x"
    m = re.search(r"HÄVSTÅNG:\s*(\d+)X?", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    
    # Format 2: Lux Leak - "Leverage : 10x [Isolated]"
    m = re.search(r"LEVERAGE\s*:\s*(\d+)X?", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    
    # Format 3: Simple - "Leverage: Cross 50X"
    m = re.search(r"LEVERAGE:\s*(?:CROSS\s*)?(\d+)X?", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    
    # Format 4: Bitcoin Bullets - "Leverage: 5-10x"
    m = re.search(r"LEVERAGE:\s*(\d+)(?:-\d+)?X?", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    
    # Format 5: X30, X50, etc.
    m = re.search(r"X(\d+)", text)
    if m:
        return int(m.group(1))
    
    return None


def signal_fingerprint(signal: Dict) -> str:
    """Create a fingerprint for cross-group deduplication."""
    key_parts = [
        signal.get("symbol", ""),
        signal.get("direction", ""),
        str(signal.get("entries", [])),
        str(signal.get("sl", "")),
        str(signal.get("tps", [])),
    ]
    fingerprint = "|".join(key_parts)
    return hashlib.sha256(fingerprint.encode()).hexdigest()[:16]


async def is_similar_signal_blocked(signal: Dict, channel_id: int) -> bool:
    """Check if a similar signal from another channel is blocked within the time window."""
    if not signal.get("symbol") or not signal.get("direction"):
        return False
    
    fingerprint = signal_fingerprint(signal)
    current_time = int(time.time())
    block_duration = settings.SIGNAL_BLOCK_DURATION_HOURS * 3600
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Create table if not exists
        await db.execute("""
            CREATE TABLE IF NOT EXISTS signal_blocks (
                fingerprint TEXT,
                channel_id INTEGER,
                blocked_at INTEGER,
                PRIMARY KEY (fingerprint, channel_id)
            )
        """)
        
        # Check for similar signals from other channels within block window
        async with db.execute("""
            SELECT channel_id, blocked_at FROM signal_blocks 
            WHERE fingerprint = ? AND channel_id != ? 
            AND blocked_at > ?
        """, (fingerprint, channel_id, current_time - block_duration)) as cur:
            rows = await cur.fetchall()
            
        if rows:
            return True
        
        # Record this signal
        try:
            await db.execute("""
                INSERT OR REPLACE INTO signal_blocks (fingerprint, channel_id, blocked_at)
                VALUES (?, ?, ?)
            """, (fingerprint, channel_id, current_time))
            await db.commit()
        except Exception:
            pass
    
    return False


async def cleanup_old_blocks():
    """Clean up old signal blocks."""
    current_time = int(time.time())
    block_duration = settings.SIGNAL_BLOCK_DURATION_HOURS * 3600
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            DELETE FROM signal_blocks 
            WHERE blocked_at < ?
        """, (current_time - block_duration,))
        await db.commit()