from dotenv import load_dotenv
import os
from decimal import Decimal

load_dotenv()


def get_env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def get_int_env(name: str, default: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return int(default)
    try:
        return int(raw)
    except ValueError:
        return int(default)


def get_decimal_env(name: str, default: str = "0") -> Decimal:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return Decimal(default)
    try:
        return Decimal(raw)
    except Exception:
        return Decimal(default)


# === BYBIT API CONFIGURATION ===
BYBIT_API_KEY = get_env("BYBIT_API_KEY", "")
BYBIT_API_SECRET = get_env("BYBIT_API_SECRET", "")
BYBIT_ENDPOINT = get_env("BYBIT_ENDPOINT", "https://api-testnet.bybit.com")

# === TELEGRAM CONFIGURATION ===
TELEGRAM_API_ID = get_int_env("TELEGRAM_API_ID", 0)
TELEGRAM_API_HASH = get_env("TELEGRAM_API_HASH", "")
TELEGRAM_SESSION = get_env("TELEGRAM_SESSION", "bybit_copybot_session")
TELEGRAM_OUTPUT_CHANNEL = get_int_env("TELEGRAM_OUTPUT_CHANNEL", 0)

# Allow-list (supports both TELEGRAM_ALLOWED_CHANNELS and legacy TELEGRAM_SOURCE_WHITELIST)
_allowed = get_env("TELEGRAM_ALLOWED_CHANNELS", "")
_legacy = get_env("TELEGRAM_SOURCE_WHITELIST", "")
_src = _allowed if _allowed else _legacy
TELEGRAM_SOURCE_WHITELIST = []
ALLOWED_CHANNEL_IDS = []
if _src:
    try:
        parsed = [int(x.strip()) for x in _src.split(",") if x.strip()]
        TELEGRAM_SOURCE_WHITELIST = parsed
        ALLOWED_CHANNEL_IDS = parsed
    except Exception:
        TELEGRAM_SOURCE_WHITELIST = []
        ALLOWED_CHANNEL_IDS = []

# Optional: human-readable names for allowed channels
# Note: Duplicate ID -1003035035852 kept as SRC_SMART_CRYPTO per user instruction
CHANNEL_ID_TO_NAME = {
    -1002464706951: "SRC_LUX_LEAK",
    -1002290339976: "SRC_CRYPTORAKETEN",
    -1003035035852: "SRC_SMART_CRYPTO",
    -1002296565814: "SRC_WOLF_TRADING",
    -1001535877716: "SRC_ALGOBOT",
    -1002646388542: "SRC_BITOP_CRYPTO",
    -1002007321736: "SRC_CRYPTO_BOE",
    -1001741713321: "SRC_CRYPTO_JOBS",
    -1002096444523: "SRC_BYBIT_FUTURE",
    -1002467159534: "SRC_CRYPTO_PUMP_CLUB",
    -1001778431342: "SRC_TRADEBOLT",
    -1002308774475: "SRC_SCALPING_100",
    -1002655381894: "SRC_CRYPTO_SCALPING",
    -1001858531978: "SRC_HEMI_SIGNALS",
}

# Debug flag: when set to "1", intake prints and bypasses allow-list filter
TELEGRAM_DEBUG = get_env("TELEGRAM_DEBUG", "0") == "1"

# === RISK MANAGEMENT CONFIGURATION ===
# Initial risk per trade (2% of equity)
INITIAL_RISK_PCT = get_decimal_env("INITIAL_RISK_PCT", "0.02")

# Initial margin per trade (20 USDT)
INITIAL_MARGIN_USDT = get_decimal_env("INITIAL_MARGIN_USDT", "20")

# Pyramid step margin (20 USDT per add)
PYRAMID_STEP_MARGIN_USDT = get_decimal_env("PYRAMID_STEP_MARGIN_USDT", "20")

# Maximum pyramid adds per trade
MAX_PYRAMID_ADDS = get_int_env("MAX_PYRAMID_ADDS", 100)

# === LEVERAGE CONFIGURATION ===
# Default leverage modes
DEFAULT_LEVERAGE_SWING = get_int_env("DEFAULT_LEVERAGE_SWING", 6)
DEFAULT_LEVERAGE_DYNAMIC = get_int_env("DEFAULT_LEVERAGE_DYNAMIC", 10)
DEFAULT_LEVERAGE_FIXED = get_int_env("DEFAULT_LEVERAGE_FIXED", 10)

# Maximum leverage in pyramid ladder
MAX_LEVERAGE_PYRAMID = get_int_env("MAX_LEVERAGE_PYRAMID", 50)

# === HEDGE/RE-ENTRY CONFIGURATION ===
# Hedge trigger percentage (-2%)
HEDGE_TRIGGER_PCT = get_decimal_env("HEDGE_TRIGGER_PCT", "-0.02")

# Maximum re-entries per trade
MAX_REENTRIES = get_int_env("MAX_REENTRIES", 3)

# === TRAILING STOP CONFIGURATION ===
# Trailing activation percentage (+6.1%)
TRAILING_ACTIVATION_PCT = get_decimal_env("TRAILING_ACTIVATION_PCT", "0.061")

# Trailing distance behind highest price (2.5%)
TRAILING_DISTANCE_PCT = get_decimal_env("TRAILING_DISTANCE_PCT", "0.025")

# === PYRAMID LADDER CONFIGURATION ===
# Step percentages and corresponding IM totals
PYRAMID_LADDER = {
    Decimal("0.015"): 20,   # +1.5%: IM = 20 USDT
    Decimal("0.023"): 20,   # +2.3%: SL to BE
    Decimal("0.024"): 20,   # +2.4%: Raise leverage
    Decimal("0.025"): 40,   # +2.5%: IM = 40 USDT
    Decimal("0.040"): 60,   # +4.0%: IM = 60 USDT
    Decimal("0.060"): 80,   # +6.0%: IM = 80 USDT
    Decimal("0.086"): 100,  # +8.6%: IM = 100 USDT
}

# === SIGNAL DEDUPLICATION ===
# Cross-group signal blocking duration (3 hours)
SIGNAL_BLOCK_DURATION_HOURS = get_int_env("SIGNAL_BLOCK_DURATION_HOURS", 3)

# Signal similarity threshold (5% difference allowed)
SIGNAL_SIMILARITY_THRESHOLD_PCT = get_decimal_env("SIGNAL_SIMILARITY_THRESHOLD_PCT", "0.05")

# === ORDER CLEANUP ===
# Delete orders not opened within N days
ORDER_CLEANUP_DAYS = get_int_env("ORDER_CLEANUP_DAYS", 6)

# === MARGIN MODE ===
# Set to "isolated" or "cross"
MARGIN_MODE = get_env("MARGIN_MODE", "isolated")

# === REPORTING ===
# Report timezone (Europe/Stockholm)
REPORT_TIMEZONE = get_env("REPORT_TIMEZONE", "Europe/Stockholm")

# Daily report times (24h format)
DAILY_REPORT_TIMES = ["08:00", "22:00"]

# Weekly report (Saturday 22:00)
WEEKLY_REPORT_DAY = 5  # Saturday
WEEKLY_REPORT_TIME = "22:00"

# === LOGGING ===
# Log level
LOG_LEVEL = get_env("LOG_LEVEL", "INFO")

# Log file path
LOG_FILE = get_env("LOG_FILE", "bot.log")

if __name__ == "__main__":
    print("BYBIT_ENDPOINT:", BYBIT_ENDPOINT)
    print("TELEGRAM_SESSION:", TELEGRAM_SESSION)
    print("INITIAL_RISK_PCT:", INITIAL_RISK_PCT)
    print("INITIAL_MARGIN_USDT:", INITIAL_MARGIN_USDT)
    print("PYRAMID_LADDER:", PYRAMID_LADDER)

