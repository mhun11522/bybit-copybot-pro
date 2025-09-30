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

BYBIT_ENDPOINT   = os.getenv("BYBIT_ENDPOINT", "https://api-testnet.bybit.com")
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
DEDUP_SECONDS = int(os.getenv("DEDUP_SECONDS", "120"))
CATEGORY = "linear"  # USDT perps