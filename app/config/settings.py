# app/config/settings.py
# Strict schema configuration for Bybit Copybot Pro

import os
from decimal import Decimal
from dotenv import load_dotenv
load_dotenv()  # load from .env only; never set secrets in code

# === STRICT SCHEMA CONFIGURATION ===

# Environment Configuration
TIMEZONE = os.getenv("TIMEZONE", "Europe/Stockholm")
RISK_PER_TRADE = Decimal(os.getenv("RISK_PER_TRADE", "0.02"))  # 2% risk per trade
BASE_IM = Decimal(os.getenv("BASE_IM", "20"))  # 20 USDT base initial margin
MAX_CONCURRENT_TRADES = int(os.getenv("MAX_CONCURRENT_TRADES", "100"))  # Max 100 concurrent trades

# Bybit Configuration
BYBIT_ENDPOINT = os.getenv("BYBIT_ENDPOINT", "https://api-testnet.bybit.com")  # TESTNET by default
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY") or ""
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET") or ""
BYBIT_RECV_WINDOW = os.getenv("BYBIT_RECV_WINDOW", "30000")

# Whitelist "3 always" channels (strict requirement)
ALWAYS_WHITELIST_CHANNELS = [
    "VIP Trading Channel",
    "Elite Trading Signals", 
    "Crypto Pump Club"
]

TELEGRAM_SESSION = os.getenv("TELEGRAM_SESSION", "bybit_copybot_session")
TELEGRAM_API_ID  = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH= os.getenv("TELEGRAM_API_HASH", "")


# Multi-channel support: whitelisted source names and IDs
SRC_CHANNEL_NAMES = [x.strip() for x in os.getenv("SRC_CHANNEL_NAMES", "").split(",") if x.strip()]

def _parse_int_list(env_value: str) -> list[int]:
    """Parse comma-separated integer list, skipping invalid values."""
    out = []
    for tok in (env_value or "").split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            out.append(int(tok))
        except ValueError:
            # skip garbage (e.g., "...")
            continue
    return out

ALLOWED_CHANNEL_IDS = _parse_int_list(os.getenv("TELEGRAM_ALLOWED_CHANNELS",""))

# Channel ID to name mapping for templates
CHANNEL_ID_NAME_MAP = {}
channel_mapping_str = os.getenv("CHANNEL_ID_NAME_MAP", "")
if channel_mapping_str:
    for item in channel_mapping_str.split(","):
        if ":" in item:
            channel_id, channel_name = item.split(":", 1)
            try:
                CHANNEL_ID_NAME_MAP[int(channel_id.strip())] = channel_name.strip()
            except ValueError:
                pass

# Fail fast on missing essentials
_missing = []
for k in ("BYBIT_API_KEY","BYBIT_API_SECRET","TELEGRAM_API_ID","TELEGRAM_API_HASH"):
    if not os.getenv(k):
        _missing.append(k)
if _missing:
    raise RuntimeError(f"Missing required secrets: {', '.join(_missing)}. Set them in your .env")

# Signal Gating (using Decimal for all math)
DEDUP_SECONDS = int(os.getenv("DEDUP_SECONDS", str(3*60*60)))  # 3 hours
DUP_TOLERANCE_PCT = Decimal(os.getenv("DUP_TOLERANCE_PCT", "5"))  # ±5% tolerance for same signal
BLOCK_SAME_DIR_SECONDS = int(os.getenv("BLOCK_SAME_DIR_SECONDS", str(3*60*60)))  # 3 hours

# Leverage Configuration (isolated margin, Decimal math)
ISOLATED_MARGIN = True
LEV_MIN = Decimal(os.getenv("LEV_MIN", "5"))
LEV_MAX = Decimal(os.getenv("LEV_MAX", "15"))  # Max 15x for dynamic leverage (was 50x)

# Position Entry (Decimal for all price/qty calculations)
IM_PER_ENTRY_USDT = Decimal(os.getenv("IM_PER_ENTRY_USDT", "20"))  # Total IM per trade (split across dual entries)

# Pyramid Strategy (7 levels with Decimal precision)
PYR_LEVELS = [
    {"trigger": Decimal("1.5"), "action": "check_im",   "target_im": Decimal("20")},
    {"trigger": Decimal("2.3"), "action": "sl_to_be"},
    {"trigger": Decimal("2.4"), "action": "max_leverage","target_lev": Decimal("50")},
    {"trigger": Decimal("2.5"), "action": "add_im",     "target_im": Decimal("40")},
    {"trigger": Decimal("4.0"), "action": "add_im",     "target_im": Decimal("60")},
    {"trigger": Decimal("6.0"), "action": "add_im",     "target_im": Decimal("80")},
    {"trigger": Decimal("8.6"), "action": "add_im",     "target_im": Decimal("100")},
]
PYR_CHECK_INTERVAL = Decimal(os.getenv("PYR_CHECK_INTERVAL", "1.0"))
PYR_MAX_ADDS = int(os.getenv("PYR_MAX_ADDS", "100"))

# Trailing Strategy (Decimal precision)
TRAIL_TRIGGER_PCT = Decimal("6.1")   # activate trailing at +6.1%
TRAIL_DISTANCE_PCT = Decimal("2.5")  # keep SL 2.5% behind HWM/LWM
TRAIL_POLL_SECONDS = Decimal(os.getenv("TRAIL_POLL_SECONDS", "2"))

# Hedge / Re-entry Strategy (Decimal precision)
HEDGE_TRIGGER_PCT = Decimal("-2.0")   # open hedge at -2%
HEDGE_MAX_RENTRIES = 3
REENTRY_DELAY_SECONDS = int(os.getenv("REENTRY_DELAY_SECONDS", "60"))

# Output Channel - where all bot messages are sent
OUTPUT_CHANNEL_ID = os.getenv("OUTPUT_CHANNEL_ID")
if OUTPUT_CHANNEL_ID:
    OUTPUT_CHANNEL_ID = int(OUTPUT_CHANNEL_ID)

# Common
CATEGORY = os.getenv("CATEGORY", "linear")  # Bybit V5: "linear" for USDT perps