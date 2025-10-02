# app/config/settings.py
# Re-export existing settings and add missing constants

import os
from dotenv import load_dotenv
load_dotenv()

# Set environment variables directly if not found
if not os.getenv("TELEGRAM_API_ID"):
    os.environ["TELEGRAM_API_ID"] = "27590479"
if not os.getenv("TELEGRAM_API_HASH"):
    os.environ["TELEGRAM_API_HASH"] = "6e60321cbb996b499b6a370af62342de"
if not os.getenv("BYBIT_API_KEY"):
    os.environ["BYBIT_API_KEY"] = "ZLk18Hv2uM6EkJGce7"
if not os.getenv("BYBIT_API_SECRET"):
    os.environ["BYBIT_API_SECRET"] = "XbMCBIlE6DosgDMLRvod014y4inqtXBtVzmr"

# Re-export from app.settings
TIMEZONE = os.getenv("TIMEZONE", "Europe/Stockholm")

TELEGRAM_SESSION = os.getenv("TELEGRAM_SESSION", "bybit_copybot_session")
TELEGRAM_API_ID  = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH= os.getenv("TELEGRAM_API_HASH", "")

BYBIT_ENDPOINT   = os.getenv("BYBIT_ENDPOINT", "https://api.bybit.com")
BYBIT_API_KEY    = os.getenv("BYBIT_API_KEY", "")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET", "")
BYBIT_RECV_WINDOW= os.getenv("BYBIT_RECV_WINDOW", "30000")

TELEGRAM_SESSION = os.getenv("TELEGRAM_SESSION", "bybit_copybot_session")
TELEGRAM_API_ID  = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH= os.getenv("TELEGRAM_API_HASH", "")

# Multi-channel support: whitelisted source names and IDs
SRC_CHANNEL_NAMES = [x.strip() for x in os.getenv("SRC_CHANNEL_NAMES", "").split(",") if x.strip()]
ALLOWED_CHANNEL_IDS = [int(x) for x in os.getenv("TELEGRAM_ALLOWED_CHANNELS","").split(",") if x.strip()]

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

RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.02"))
MAX_CONCURRENT_TRADES = int(os.getenv("MAX_CONCURRENT_TRADES", "100"))

# —— Signal gating ——
DEDUP_SECONDS = int(os.getenv("DEDUP_SECONDS", str(3*60*60)))  # 3 hours
DUP_TOLERANCE_PCT = float(os.getenv("DUP_TOLERANCE_PCT", "5"))  # ±5% tolerance for same signal
BLOCK_SAME_DIR_SECONDS = int(os.getenv("BLOCK_SAME_DIR_SECONDS", str(3*60*60)))  # 3 hours

# —— Leverage (isolated) ——
ISOLATED_MARGIN = True
LEV_MIN = float(os.getenv("LEV_MIN", "5"))
LEV_MAX = float(os.getenv("LEV_MAX", "15"))  # Max 15x for dynamic leverage (was 50x)

# —— Position entry ——
IM_PER_ENTRY_USDT = float(os.getenv("IM_PER_ENTRY_USDT", "20"))  # Total IM per trade (split across dual entries)

# —— Pyramid (7 levels) ——
PYR_LEVELS = [
    {"trigger": 1.5, "action": "check_im",   "target_im": 20},
    {"trigger": 2.3, "action": "sl_to_be"},
    {"trigger": 2.4, "action": "max_leverage","target_lev": 50},
    {"trigger": 2.5, "action": "add_im",     "target_im": 40},
    {"trigger": 4.0, "action": "add_im",     "target_im": 60},
    {"trigger": 6.0, "action": "add_im",     "target_im": 80},
    {"trigger": 8.6, "action": "add_im",     "target_im": 100},
]
PYR_CHECK_INTERVAL = float(os.getenv("PYR_CHECK_INTERVAL", "1.0"))
PYR_MAX_ADDS = int(os.getenv("PYR_MAX_ADDS", "100"))

# —— Trailing ——
TRAIL_TRIGGER_PCT = 6.1   # activate trailing at +6.1%
TRAIL_DISTANCE_PCT = 2.5  # keep SL 2.5% behind HWM/LWM
TRAIL_POLL_SECONDS = float(os.getenv("TRAIL_POLL_SECONDS", "2"))

# —— Hedge / Re-entry ——
HEDGE_TRIGGER_PCT = -2.0   # open hedge at -2%
HEDGE_MAX_RENTRIES = 3
REENTRY_DELAY_SECONDS = int(os.getenv("REENTRY_DELAY_SECONDS", "60"))

# Output Channel - where all bot messages are sent
OUTPUT_CHANNEL_ID = os.getenv("OUTPUT_CHANNEL_ID")
if OUTPUT_CHANNEL_ID:
    OUTPUT_CHANNEL_ID = int(OUTPUT_CHANNEL_ID)

# Common
CATEGORY = os.getenv("CATEGORY", "linear")  # Bybit V5: "linear" for USDT perps