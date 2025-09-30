"""Configuration settings for Bybit Copybot Pro."""

import os
from dotenv import load_dotenv

load_dotenv()

# Bybit settings
BYBIT_ENDPOINT = os.getenv("BYBIT_ENDPOINT", "https://api-testnet.bybit.com")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET", "")
BYBIT_RECV_WINDOW = os.getenv("BYBIT_RECV_WINDOW", "5000")

# Telegram settings
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_SESSION = os.getenv("TELEGRAM_SESSION", "bybit_copybot_session")

# Channel whitelist (by name, not ID)
SRC_CHANNEL_NAMES = [x.strip() for x in os.getenv("SRC_CHANNEL_NAMES", "").split(",") if x.strip()]

# Risk management
RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.02"))  # 2%
MAX_CONCURRENT_TRADES = int(os.getenv("MAX_CONCURRENT_TRADES", "100"))
DEDUP_SECONDS = int(os.getenv("DEDUP_SECONDS", "120"))

# Timezone
TIMEZONE = os.getenv("TIMEZONE", "Europe/Stockholm")

# Trading category
CATEGORY = "linear"  # USDT perps