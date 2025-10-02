"""Strict configuration with client requirements."""

from decimal import Decimal
from typing import List, Dict, Any
import os
from zoneinfo import ZoneInfo

class StrictSettings:
    """Strict configuration matching client requirements exactly."""
    
    # Core trading parameters (client requirements)
    risk_pct: Decimal = Decimal("0.02")  # 2% risk per trade
    im_target: Decimal = Decimal("20")   # 20 USDT initial margin target
    max_trades: int = 100               # Maximum concurrent trades
    timezone: str = "Europe/Stockholm"  # Client specified timezone
    
    # Leverage policy (exact client rules)
    swing_leverage: Decimal = Decimal("6")
    fast_leverage: Decimal = Decimal("10") 
    min_dynamic_leverage: Decimal = Decimal("7.5")
    forbidden_leverage_gap_min: Decimal = Decimal("6")
    forbidden_leverage_gap_max: Decimal = Decimal("7.5")
    
    # Strategy parameters
    breakeven_offset: Decimal = Decimal("0.0015")  # 0.0015% offset for BE
    trailing_trigger: Decimal = Decimal("6.1")     # 6.1% trigger for trailing
    trailing_distance: Decimal = Decimal("2.5")    # 2.5% trailing distance
    hedge_trigger: Decimal = Decimal("-2.0")       # -2% trigger for hedge
    max_reentries: int = 3                         # Maximum re-entry attempts
    
    # Pyramid levels (exact client specification)
    pyramid_levels: List[Dict[str, Any]] = [
        {"trigger": Decimal("1.5"), "action": "check_im", "target_im": 20},
        {"trigger": Decimal("2.3"), "action": "sl_to_be"},
        {"trigger": Decimal("2.4"), "action": "max_leverage", "target_lev": 50},
        {"trigger": Decimal("2.5"), "action": "add_im", "target_im": 40},
        {"trigger": Decimal("4.0"), "action": "add_im", "target_im": 60},
        {"trigger": Decimal("6.0"), "action": "add_im", "target_im": 80},
        {"trigger": Decimal("8.6"), "action": "add_im", "target_im": 100},
    ]
    
    # Report timing (exact client specification)
    daily_report_hour: int = 8          # 08:00 Stockholm time
    weekly_report_hour: int = 22        # 22:00 Saturday Stockholm time
    weekly_report_day: int = 5          # Saturday (0=Monday, 5=Saturday)
    
    # Bybit configuration
    bybit_endpoint: str = "https://api.bybit.com"
    bybit_recv_window: str = "30000"
    bybit_api_key: str = ""
    bybit_api_secret: str = ""
    
    # Telegram configuration
    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    telegram_session: str = "bybit_copybot_session"
    
    # Channel whitelist (exact client channels)
    source_whitelist: List[str] = [
        "SRC_LUX_LEAK",
        "SRC_CRYPTORAKETEN", 
        "SRC_SMART_CRYPTO",
        "SRC_WOLF_TRADING",
        "SRC_ALGOBOT",
        "SRC_BITOP_CRYPTO",
        "SRC_CRYPTO_BOE",
        "SRC_CRYPTO_JOBS",
        "SRC_BYBIT_FUTURE",
        "SRC_CRYPTO_PUMP_CLUB",
        "SRC_TRADEBOLT",
        "SRC_SCALPING_100",
        "SRC_CRYPTO_SCALPING",
        "SRC_HEMI_SIGNALS",
        "MY_TEST_CHANNEL"
    ]
    
    # Order type enforcement
    entry_order_type: str = "Limit"
    entry_time_in_force: str = "PostOnly"
    exit_order_type: str = "Market"  # For TP/SL triggers
    exit_reduce_only: bool = True
    exit_trigger_by: str = "MarkPrice"
    
    # Symbol validation
    min_notional_usdt: Decimal = Decimal("5")  # Minimum 5 USDT notional
    supported_categories: List[str] = ["linear"]  # USDT perps only
    
    # Idempotency settings
    idempotency_ttl_seconds: int = 90  # 90-second sliding window
    
    def get_timezone(self) -> ZoneInfo:
        """Get timezone object."""
        return ZoneInfo(self.timezone)
    
    def is_leverage_in_forbidden_gap(self, leverage: Decimal) -> bool:
        """Check if leverage is in forbidden 6-7.5 gap."""
        return self.forbidden_leverage_gap_min < leverage < self.forbidden_leverage_gap_max
    
    def get_pyramid_level(self, price_pct: Decimal) -> Dict[str, Any]:
        """Get pyramid level for given price percentage."""
        for level in reversed(self.pyramid_levels):  # Check highest first
            if price_pct >= level["trigger"]:
                return level
        return {}

def load_strict_config() -> StrictSettings:
    """Load configuration with validation."""
    try:
        # Create settings instance
        config = StrictSettings()
        
        # Load from environment variables
        config.bybit_api_key = os.getenv("BYBIT_API_KEY", "")
        config.bybit_api_secret = os.getenv("BYBIT_API_SECRET", "")
        config.telegram_api_id = int(os.getenv("TELEGRAM_API_ID", "0"))
        config.telegram_api_hash = os.getenv("TELEGRAM_API_HASH", "")
        config.telegram_session = os.getenv("TELEGRAM_SESSION", "bybit_copybot_session")
        config.bybit_endpoint = os.getenv("BYBIT_ENDPOINT", "https://api.bybit.com")
        config.bybit_recv_window = os.getenv("BYBIT_RECV_WINDOW", "30000")
        
        # Override with existing settings if available
        try:
            from app.config.settings import (
                BYBIT_API_KEY, BYBIT_API_SECRET, TELEGRAM_API_ID, 
                TELEGRAM_API_HASH, TELEGRAM_SESSION, BYBIT_ENDPOINT, BYBIT_RECV_WINDOW
            )
            config.bybit_api_key = BYBIT_API_KEY
            config.bybit_api_secret = BYBIT_API_SECRET
            config.telegram_api_id = TELEGRAM_API_ID
            config.telegram_api_hash = TELEGRAM_API_HASH
            config.telegram_session = TELEGRAM_SESSION
            config.bybit_endpoint = BYBIT_ENDPOINT
            config.bybit_recv_window = BYBIT_RECV_WINDOW
        except ImportError:
            pass
        
        # Validate configuration
        if not config.bybit_api_key:
            raise ValueError("BYBIT_API_KEY not provided")
        if not config.bybit_api_secret:
            raise ValueError("BYBIT_API_SECRET not provided")
        if config.telegram_api_id <= 0:
            raise ValueError("TELEGRAM_API_ID must be positive")
        if not config.telegram_api_hash:
            raise ValueError("TELEGRAM_API_HASH not provided")
        
        return config
        
    except Exception as e:
        raise ValueError(f"Configuration validation failed: {e}")

# Global settings instance
STRICT_CONFIG = load_strict_config()