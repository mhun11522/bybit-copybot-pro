"""Trading configuration and safety settings."""

import os
from typing import Dict, Any

# Trading modes
TRADING_MODE = os.getenv("TRADING_MODE", "MONITOR")  # MONITOR, DRY_RUN, LIVE

# Safety settings
MAX_DAILY_TRADES = int(os.getenv("MAX_DAILY_TRADES", "10"))
MAX_POSITION_SIZE_USDT = float(os.getenv("MAX_POSITION_SIZE_USDT", "100"))
MIN_SIGNAL_CONFIDENCE = float(os.getenv("MIN_SIGNAL_CONFIDENCE", "0.7"))

# Risk management
MAX_LEVERAGE = int(os.getenv("MAX_LEVERAGE", "20"))
STOP_LOSS_PERCENTAGE = float(os.getenv("STOP_LOSS_PERCENTAGE", "5.0"))
TAKE_PROFIT_PERCENTAGE = float(os.getenv("TAKE_PROFIT_PERCENTAGE", "10.0"))

# Channel-specific settings
CHANNEL_RISK_MULTIPLIERS = {
    "SRC_LUX_LEAK": 1.0,
    "SRC_CRYPTORAKETEN": 0.8,
    "SRC_SMART_CRYPTO": 1.2,
    "SRC_WOLF_TRADING": 0.9,
    "SRC_ALGOBOT": 1.1,
    "SRC_BITOP_CRYPTO": 0.7,
    "SRC_CRYPTO_BOE": 1.0,
    "SRC_CRYPTO_JOBS": 0.8,
    "SRC_BYBIT_FUTURE": 1.3,
    "SRC_CRYPTO_PUMP_CLUB": 0.6,
    "SRC_TRADEBOLT": 1.0,
    "SRC_SCALPING_100": 0.5,
    "SRC_CRYPTO_SCALPING": 0.5,
    "SRC_HEMI_SIGNALS": 0.9,
    "MY_TEST_CHANNEL": 0.1,  # Very low risk for testing
}

# Symbol blacklist (symbols to never trade)
BLACKLISTED_SYMBOLS = {
    "LUNAUSDT", "USTUSDT", "FTTUSDT",  # Known problematic tokens
}

# Trading hours (UTC)
TRADING_HOURS = {
    "start": int(os.getenv("TRADING_START_HOUR", "0")),  # 0 = 00:00 UTC
    "end": int(os.getenv("TRADING_END_HOUR", "23")),    # 23 = 23:00 UTC
}

def is_trading_enabled() -> bool:
    """Check if trading is enabled."""
    return TRADING_MODE in ["DRY_RUN", "LIVE"]

def is_live_trading() -> bool:
    """Check if live trading is enabled."""
    return TRADING_MODE == "LIVE"

def is_dry_run() -> bool:
    """Check if dry run mode is enabled."""
    return TRADING_MODE == "LIVE"

def get_channel_risk_multiplier(channel_name: str) -> float:
    """Get risk multiplier for a channel."""
    return CHANNEL_RISK_MULTIPLIERS.get(channel_name, 1.0)

def is_symbol_blacklisted(symbol: str) -> bool:
    """Check if symbol is blacklisted."""
    return symbol.upper() in BLACKLISTED_SYMBOLS

def is_trading_hours() -> bool:
    """Check if current time is within trading hours."""
    from datetime import datetime
    current_hour = datetime.utcnow().hour
    return TRADING_HOURS["start"] <= current_hour <= TRADING_HOURS["end"]

def get_trading_config() -> Dict[str, Any]:
    """Get complete trading configuration."""
    return {
        "mode": TRADING_MODE,
        "max_daily_trades": MAX_DAILY_TRADES,
        "max_position_size_usdt": MAX_POSITION_SIZE_USDT,
        "min_signal_confidence": MIN_SIGNAL_CONFIDENCE,
        "max_leverage": MAX_LEVERAGE,
        "stop_loss_percentage": STOP_LOSS_PERCENTAGE,
        "take_profit_percentage": TAKE_PROFIT_PERCENTAGE,
        "trading_hours": TRADING_HOURS,
        "blacklisted_symbols": list(BLACKLISTED_SYMBOLS),
    }