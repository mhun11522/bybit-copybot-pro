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


if __name__ == "__main__":
    print("BYBIT_ENDPOINT:", BYBIT_ENDPOINT)
    print("TELEGRAM_SESSION:", TELEGRAM_SESSION)

