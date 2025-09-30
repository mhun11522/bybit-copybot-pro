from dotenv import load_dotenv
import os

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


BYBIT_API_KEY = get_env("BYBIT_API_KEY", "")
BYBIT_API_SECRET = get_env("BYBIT_API_SECRET", "")
BYBIT_ENDPOINT = get_env("BYBIT_ENDPOINT", "https://api-testnet.bybit.com")

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


if __name__ == "__main__":
    print("BYBIT_ENDPOINT:", BYBIT_ENDPOINT)
    print("TELEGRAM_SESSION:", TELEGRAM_SESSION)

