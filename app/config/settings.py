import os
from dotenv import load_dotenv
load_dotenv()

TIMEZONE = os.getenv("TIMEZONE", "Europe/Stockholm")

BYBIT_ENDPOINT   = os.getenv("BYBIT_ENDPOINT", "https://api-testnet.bybit.com")
BYBIT_API_KEY    = os.getenv("BYBIT_API_KEY", "")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET", "")
BYBIT_RECV_WINDOW= os.getenv("BYBIT_RECV_WINDOW", "5000")

TELEGRAM_SESSION = os.getenv("TELEGRAM_SESSION", "bybit_copybot_session")
TELEGRAM_API_ID  = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH= os.getenv("TELEGRAM_API_HASH", "")

# client requirement: exactly three whitelisted source *names* (not IDs!)
SRC_CHANNEL_NAMES = [x.strip() for x in os.getenv("SRC_CHANNEL_NAMES", "").split(",") if x.strip()]
ALLOWED_CHANNEL_IDS = [int(x) for x in os.getenv("TELEGRAM_ALLOWED_CHANNELS","").split(",") if x.strip()]

RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.02"))
MAX_CONCURRENT_TRADES = int(os.getenv("MAX_CONCURRENT_TRADES", "100"))
DEDUP_SECONDS = int(os.getenv("DEDUP_SECONDS", "120"))
CATEGORY = "linear"  # USDT perps