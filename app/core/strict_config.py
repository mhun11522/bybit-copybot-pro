"""Strict configuration with client requirements."""

from decimal import Decimal
from typing import List, Dict, Any
import os
from zoneinfo import ZoneInfo
from app.core.logging import system_logger

# CRITICAL FIX: Load .env BEFORE reading environment variables
from dotenv import load_dotenv
load_dotenv()  # Ensure .env is loaded before os.getenv() calls

class StrictSettings:
    """Strict configuration matching client requirements exactly."""
    
    # Core trading parameters (client requirements)
    risk_pct: Decimal = Decimal("0.02")  # 2% risk per trade
    im_target: Decimal = Decimal("20")   # 20 USDT initial margin target
    max_trades: int = 100               # Maximum concurrent trades
    timezone: str = "Europe/Stockholm"  # Client specified timezone
    
    # Leverage policy (CLIENT SPEC - doc/10_15.md)
    swing_leverage: Decimal = Decimal("6.00")  # SWING must be x6.00
    min_dynamic_leverage: Decimal = Decimal("7.5")  # DYNAMIC minimum x7.50
    auto_sl_leverage: Decimal = Decimal("10.00")  # Safety lock when SL missing
    forbidden_leverage_gap_min: Decimal = Decimal("6")
    forbidden_leverage_gap_max: Decimal = Decimal("7.5")
    
    # Strategy parameters
    breakeven_offset: Decimal = Decimal("0.0015")  # 0.0015% offset for BE
    trailing_trigger: Decimal = Decimal("6.1")     # 6.1% trigger for trailing (CLIENT SPEC)
    trailing_distance: Decimal = Decimal("2.5")    # 2.5% trailing distance (CLIENT SPEC)
    hedge_trigger: Decimal = Decimal("-2.0")       # -2% trigger for hedge
    max_reentries: int = 3                         # Maximum re-entry attempts
    
    # Pyramid levels (EXACT CLIENT SPECIFICATION - DO NOT MODIFY)
    # All percentages calculated from ORIGINAL ENTRY, not current average
    # CRITICAL CLARIFICATION (doc/requirement.txt Line 10 vs doc/10_15.md Line 136):
    # - Template calls this "Pyramid Step 4" = +2.4% leverage-only
    # - Next step is +2.5% = IM to 40 USDT
    pyramid_levels: List[Dict[str, Any]] = [
        {"trigger": Decimal("1.5"), "action": "im_check", "target_im": 20},      # Step 1: +1.5% → Check IM = 20 USDT if any TP hit
        {"trigger": Decimal("2.3"), "action": "sl_breakeven"},                   # Step 2: +2.3% → SL to BE + 0.0015%
        {"trigger": Decimal("2.4"), "action": "set_full_leverage", "leverage_cap": Decimal("50")},  # Step 3 (Template "Step 4"): +2.4% → Leverage-only (max 50x)
        {"trigger": Decimal("2.5"), "action": "im_total", "target_im": 40},     # Step 4: +2.5% → IM total 40 USDT
        {"trigger": Decimal("4.0"), "action": "im_total", "target_im": 60},     # Step 5: +4.0% → IM total 60 USDT
        {"trigger": Decimal("6.0"), "action": "im_total", "target_im": 80},     # Step 6: +6.0% → IM total 80 USDT
        {"trigger": Decimal("8.6"), "action": "im_total", "target_im": 100},    # Step 7: +8.6% → IM total 100 USDT (CLIENT SPEC)
    ]
    
    # Leverage constraints (CLIENT SPEC)
    dynamic_leverage_min: Decimal = Decimal("7.5")   # DYNAMIC must be >=7.5x
    dynamic_leverage_max: Decimal = Decimal("25")    # DYNAMIC clamped to max 25x
    eth_pyramid_step3_leverage: Decimal = Decimal("50")  # ETH pyramid step 3 target
    
    # Report timing (exact client specification)
    daily_report_hour: int = 8          # 08:00 Stockholm time
    weekly_report_hour: int = 22        # 22:00 Saturday Stockholm time
    weekly_report_day: int = 5          # Saturday (0=Monday, 5=Saturday)
    
    # Bybit configuration
    bybit_endpoint: str = "https://api-demo.bybit.com"
    bybit_recv_window: str = "30000"
    bybit_api_key: str = ""
    
    # Position limits
    max_position_size_usdt: Decimal = Decimal("1000")  # Maximum position size in USDT
    bybit_api_secret: str = ""
    
    # Telegram configuration
    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    telegram_session: str = "bybit_copybot_session"
    
    # Channel ID to name mapping (from environment variable)
    channel_id_name_map: Dict[str, str] = {
        "-1002464706951": "Smart Crypto Signals Private",
        "-1002290339976": "Crypto Pump Club Free ( Crypto Future|Spot Signals)", 
        "-1003035035852": "Wolf Of Trading",
        "-1002296565814": "Wolf Of Trading",
        "-1001535877716": "AlgoBot Signals",
        "-1002646388542": "Bitop Crypto Signals",
        "-1002007321736": "Crypto BOE Signals",
        "-1001741713321": "Crypto Jobs",
        "-1002096444523": "Bybit Future Signals",
        "-1002467159534": "Crypto Pump Club",
        "-1001778431342": "TradeBolt Signals",
        "-1002308774475": "Scalping 100 Signals",
        "-1002655381894": "Crypto Scalping Signals",
        "-1001858531978": "Hemi Signals",
        "-1003027029201": "MY_TEST_CHANNEL",
        "-1002582453224": "Active Trading Channel",
        "-1002317185064": "Trading Signals Channel",
        "-1001674963962": "Crypto Signals Hub",
        "-1002606212243": "Premium Trading Signals",
        "-1002339729195": "VIP Trading Channel",
        "-1001594157621": "Elite Trading Signals",
        "-1002633265221": "Pro Trading Channel",
        "-1001173711569": "Advanced Trading Signals",
        # Additional channels found in logs - UPDATED with better names
        "-1002460891279": "The Lux Leak Free",  # Based on signal patterns
        "-1001604036547": "Crypto Signals Channel 2",  # Based on signal patterns
        "-1002259852182": "Premium Free Signals",  # Based on signal patterns
        "-1001744615878": "Trading Alerts Channel", 
        "-1001648417896": "Crypto Trading Signals",
        "-1001536269316": "Advanced Crypto Signals",  # Found in recent logs
        "-1002500502443": "Active Trading Channel 2",  # From current logs
        "-1001394941879": "Premium Signals Channel",  # From current logs
        # NEW: Channels detected in current session logs (2025-10-11)
        "-1002442181206": "Trading Channel A",  # Actively sending signals
        "-1002559357361": "Trading Channel B",  # Actively sending signals
        "-1001582079881": "Trading Channel C",  # Actively sending signals
        "8007997005": "Personal Test Chat"  # For testing
    }
    
    # Whitelisted channel IDs (derived from mapping)
    source_whitelist: List[str] = list(channel_id_name_map.keys())
    
    # Order type enforcement - CLIENT SPECIFICATION
    # CLIENT SPEC REQUIREMENT: Must use LIMIT orders at EXACT signal entry price!
    # Signal says "Entry: 63000", bot MUST place limit order at 63000 and WAIT
    # PostOnly ensures order waits in book at signal price (no immediate market fill)
    # THIS IS CRITICAL - entry price must match signal, NOT current market price!
    entry_order_type: str = "Limit"  # LIMIT orders at signal price (CLIENT REQUIREMENT!)
    entry_time_in_force: str = "PostOnly"  # PostOnly to wait at exact signal price
    exit_order_type: str = "Market"  # Market orders for TP/SL (Conditional)
    exit_reduce_only: bool = True
    exit_trigger_by: str = "LastPrice"  # CLIENT SPEC: Consistent trigger source for all SL/TP (LastPrice|MarkPrice|IndexPrice)
    
    # Symbol validation
    min_notional_usdt: Decimal = Decimal("5")  # Minimum 5 USDT notional
    supported_categories: List[str] = ["linear"]  # USDT perps only
    category: str = "linear"  # Default category for Bybit API calls
    
    # Idempotency settings
    idempotency_ttl_seconds: int = 10800  # 3-hour sliding window as per client requirements
    
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
    
    def get_channel_name(self, channel_id: str) -> str:
        """Get channel name from channel ID."""
        return self.channel_id_name_map.get(channel_id, f"Unknown_{channel_id}")
    
    def is_channel_whitelisted(self, channel_id: str) -> bool:
        """Check if channel ID is whitelisted."""
        return channel_id in self.source_whitelist

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
        config.bybit_endpoint = os.getenv("BYBIT_ENDPOINT", "https://api-demo.bybit.com")
        config.bybit_recv_window = os.getenv("BYBIT_RECV_WINDOW", "30000")
        
        # Load channel ID to name mapping from environment
        channel_mapping_str = os.getenv("CHANNEL_ID_NAME_MAP", "")
        if channel_mapping_str:
            config.channel_id_name_map = {}
            config.source_whitelist = []
            
            # Parse format: -1002464706951:SRC_LUX_LEAK,-1002290339976:SRC_CRYPTORAKETEN,...
            for mapping in channel_mapping_str.split(','):
                if ':' in mapping:
                    channel_id, channel_name = mapping.strip().split(':', 1)
                    config.channel_id_name_map[channel_id] = channel_name
                    config.source_whitelist.append(channel_id)
            
            system_logger.info(
                f"Loaded {len(config.source_whitelist)} whitelisted channels from environment",
                {"channel_count": len(config.source_whitelist)}
            )
        else:
            system_logger.info("CHANNEL_ID_NAME_MAP environment variable not set, using default channels")
            # Use all available channels from the mapping as whitelisted
            config.source_whitelist = list(config.channel_id_name_map.keys())
            system_logger.info(
                f"Whitelisted {len(config.source_whitelist)} default channels",
                {"channel_count": len(config.source_whitelist)}
            )
        
        # Merge with ALLOWED_CHANNEL_IDS from environment if provided
        from app.config.settings import ALLOWED_CHANNEL_IDS
        if ALLOWED_CHANNEL_IDS:
            additional_channels = [str(ch_id) for ch_id in ALLOWED_CHANNEL_IDS if str(ch_id) not in config.source_whitelist]
            config.source_whitelist.extend(additional_channels)
            system_logger.info(
                f"Added {len(additional_channels)} additional channels from ALLOWED_CHANNEL_IDS",
                {"additional_count": len(additional_channels)}
            )
        
        # DEMO FIX (2025-10-13): Always ensure test channel is whitelisted
        test_channel = "-1003027029201"
        if test_channel not in config.source_whitelist:
            config.source_whitelist.append(test_channel)
        # Always ensure the test channel has the correct name in the map
        if test_channel not in config.channel_id_name_map or config.channel_id_name_map[test_channel] != "MY_TEST_CHANNEL":
            config.channel_id_name_map[test_channel] = "MY_TEST_CHANNEL"
            system_logger.info(
                f"Added test channel {test_channel} (MY_TEST_CHANNEL) to whitelist",
                {"channel_id": test_channel, "channel_name": "MY_TEST_CHANNEL"}
            )
        
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
        except ImportError as e:
            system_logger.warning(f"Optional module not available: {e}")
        
        # Validate configuration
        if not config.bybit_api_key:
            raise ValueError("BYBIT_API_KEY not provided")
        if not config.bybit_api_secret:
            raise ValueError("BYBIT_API_SECRET not provided")
        if config.telegram_api_id <= 0:
            raise ValueError("TELEGRAM_API_ID must be positive")
        if not config.telegram_api_hash:
            raise ValueError("TELEGRAM_API_HASH not provided")
        
        # CLIENT SPEC: Enforce permanent sources governance
        # The three required sources MUST be whitelisted for compliance
        required_sources = {"CRYPTORAKETEN", "LUX_LEAK", "SMART_CRYPTO"}
        present_sources = {name.upper() for name in config.channel_id_name_map.values()}
        
        # Check for required patterns in channel names (case-insensitive)
        found_sources = set()
        for required in required_sources:
            # Normalize required by removing underscores/spaces for matching
            required_normalized = required.replace("_", "").replace(" ", "")
            for present in present_sources:
                present_normalized = present.replace("_", "").replace(" ", "")
                if required_normalized in present_normalized:
                    found_sources.add(required)
                    system_logger.debug(f"Matched required source '{required}' with channel '{present}'")
                    break
        
        missing = sorted(required_sources - found_sources)
        if missing:
            system_logger.warning(
                f"Source governance check: Missing required sources: {', '.join(missing)}. "
                f"Bot will start but governance is incomplete.",
                {
                    "required": list(required_sources),
                    "present": list(present_sources),
                    "missing": missing,
                    "found": list(found_sources),
                    "governance_status": "incomplete"
                }
            )
            # CLIENT SPEC: Warn but allow startup if required sources are missing
            # TODO: Add CRYPTORAKETEN channel ID when available
        
        if not missing:
            system_logger.info("Source governance check: ALL required sources found", {
                "required_sources": list(required_sources),
                "found_sources": list(found_sources),
                "governance_status": "complete"
            })
        else:
            system_logger.info("Source governance check: Partial compliance", {
                "required_sources": list(required_sources),
                "found_sources": list(found_sources),
                "missing_sources": missing
            })
        
        return config
        
    except Exception as e:
        raise ValueError(f"Configuration validation failed: {e}")

# Global settings instance
STRICT_CONFIG = load_strict_config()

def reload_strict_config():
    """Reload strict configuration (useful for development)."""
    global STRICT_CONFIG
    STRICT_CONFIG = load_strict_config()
    system_logger.info("Strict configuration reloaded")
    return STRICT_CONFIG