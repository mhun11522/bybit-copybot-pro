"""
NTP synchronization and clock discipline.

CLIENT SPEC Lines 300-302:
- Add NTP sync and skew guard
- Operate within ±100 ms (normal operation)
- If drift > ±250 ms: automatically block trading and raise alarm
- Auto-sync and log all drift events

This prevents timestamp-related errors with Bybit API and ensures
accurate order timing.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import pytz

try:
    import ntplib
    NTP_AVAILABLE = True
except ImportError:
    NTP_AVAILABLE = False
    print("⚠️ ntplib not installed. Run: pip install ntplib")

from app.core.logging import system_logger


class NTPClockMonitor:
    """
    NTP-based clock drift monitor.
    
    CLIENT SPEC:
    - Normal operation: ±100 ms
    - Warning threshold: ±100 ms
    - Block threshold: ±250 ms (auto-block trading)
    """
    
    def __init__(self, ntp_servers: List[str] = None):
        self.ntp_servers = ntp_servers or [
            'pool.ntp.org',
            'time.google.com',
            'time.windows.com',
            'time.cloudflare.com'
        ]
        
        # CLIENT SPEC thresholds (in seconds)
        self.drift_normal = 0.100      # 100 ms - normal operation
        self.drift_warning = 0.100     # 100 ms - log warning
        self.drift_block = 0.250       # 250 ms - block trading
        
        self.trading_blocked = False
        self.last_drift: Optional[float] = None
        self.last_check: Optional[datetime] = None
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        
        # Statistics
        self.total_checks = 0
        self.drift_warnings = 0
        self.drift_blocks = 0
    
    async def check_drift(self) -> Optional[float]:
        """
        Check current clock drift against NTP server.
        
        Returns:
            Drift in seconds (positive = local clock ahead, negative = local clock behind)
            None if check failed
        """
        if not NTP_AVAILABLE:
            system_logger.warning("NTP library not available, skipping drift check")
            return None
        
        self.total_checks += 1
        
        # Try each NTP server until one succeeds
        for ntp_server in self.ntp_servers:
            try:
                client = ntplib.NTPClient()
                response = client.request(ntp_server, version=3, timeout=5)
                
                # Get offset (drift) in seconds
                drift = response.offset
                self.last_drift = drift
                self.last_check = datetime.now(pytz.UTC)
                self.consecutive_failures = 0
                
                # Log drift
                system_logger.debug(f"NTP drift check", {
                    "server": ntp_server,
                    "drift_ms": drift * 1000,
                    "drift_seconds": drift
                })
                
                return drift
                
            except Exception as e:
                system_logger.debug(f"NTP server {ntp_server} failed: {e}")
                continue
        
        # All servers failed
        self.consecutive_failures += 1
        system_logger.warning(f"NTP check failed for all servers (attempt {self.consecutive_failures}/{self.max_consecutive_failures})")
        return None
    
    async def monitor_loop(self):
        """
        Continuous NTP monitoring loop.
        
        CLIENT SPEC: Monitor clock drift and auto-block trading if threshold exceeded.
        
        Runs every 60 seconds to check drift.
        """
        system_logger.info("NTP monitor loop started", {
            "drift_normal_ms": self.drift_normal * 1000,
            "drift_warning_ms": self.drift_warning * 1000,
            "drift_block_ms": self.drift_block * 1000,
            "ntp_servers": self.ntp_servers
        })
        
        while True:
            try:
                drift = await self.check_drift()
                
                if drift is None:
                    # NTP check failed
                    if self.consecutive_failures >= self.max_consecutive_failures:
                        # Too many failures - block trading for safety
                        if not self.trading_blocked:
                            self.trading_blocked = True
                            self.drift_blocks += 1
                            system_logger.critical("⚠️ NTP check failed repeatedly - BLOCKING TRADING", {
                                "consecutive_failures": self.consecutive_failures,
                                "max_failures": self.max_consecutive_failures,
                                "action": "TRADING_BLOCKED"
                            })
                    
                    await asyncio.sleep(60)
                    continue
                
                abs_drift = abs(drift)
                drift_ms = drift * 1000
                
                # Check against thresholds
                if abs_drift > self.drift_block:
                    # CRITICAL: Block trading
                    if not self.trading_blocked:
                        self.trading_blocked = True
                        self.drift_blocks += 1
                        
                        system_logger.critical("🚨 CLOCK DRIFT EXCEEDED BLOCK THRESHOLD - TRADING BLOCKED", {
                            "drift_ms": drift_ms,
                            "drift_seconds": drift,
                            "threshold_ms": self.drift_block * 1000,
                            "action": "TRADING_BLOCKED",
                            "local_time": datetime.now().isoformat(),
                            "ntp_time": (datetime.now() - timedelta(seconds=drift)).isoformat()
                        })
                        
                        # TODO: Send alert to admin (Telegram, email, etc.)
                    
                elif abs_drift > self.drift_warning:
                    # WARNING: Drift elevated but within limits
                    self.drift_warnings += 1
                    
                    system_logger.warning("⚠️ Clock drift elevated", {
                        "drift_ms": drift_ms,
                        "drift_seconds": drift,
                        "warning_threshold_ms": self.drift_warning * 1000,
                        "block_threshold_ms": self.drift_block * 1000,
                        "status": "WARNING"
                    })
                    
                else:
                    # Normal operation
                    if self.trading_blocked:
                        # Drift has normalized - unblock trading
                        system_logger.info("✅ Clock drift normalized - UNBLOCKING TRADING", {
                            "drift_ms": drift_ms,
                            "previous_state": "BLOCKED",
                            "new_state": "NORMAL"
                        })
                        self.trading_blocked = False
                    
                    system_logger.debug("Clock drift normal", {
                        "drift_ms": drift_ms,
                        "threshold_ms": self.drift_normal * 1000
                    })
                
                # Sleep for 60 seconds before next check
                await asyncio.sleep(60)
                
            except Exception as e:
                system_logger.error(f"NTP monitor loop error: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    def is_trading_allowed(self) -> bool:
        """
        Check if trading is allowed based on clock drift.
        
        CLIENT SPEC: Must return False if drift > 250 ms.
        
        This should be checked before every order placement.
        """
        return not self.trading_blocked
    
    def get_status(self) -> Dict[str, Any]:
        """Get NTP monitor status."""
        return {
            "trading_allowed": not self.trading_blocked,
            "last_drift_ms": self.last_drift * 1000 if self.last_drift else None,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "total_checks": self.total_checks,
            "drift_warnings": self.drift_warnings,
            "drift_blocks": self.drift_blocks,
            "consecutive_failures": self.consecutive_failures,
            "ntp_servers": self.ntp_servers
        }


# Global NTP monitor instance
_ntp_monitor: Optional[NTPClockMonitor] = None


def get_ntp_monitor() -> NTPClockMonitor:
    """Get global NTP monitor instance."""
    global _ntp_monitor
    if _ntp_monitor is None:
        _ntp_monitor = NTPClockMonitor()
    return _ntp_monitor


async def start_ntp_monitoring():
    """
    Start NTP monitoring loop.
    
    CLIENT SPEC: Must be started in main.py during initialization.
    
    This runs continuously in the background monitoring clock drift.
    """
    monitor = get_ntp_monitor()
    asyncio.create_task(monitor.monitor_loop())
    
    system_logger.info("NTP monitoring started", {
        "drift_warning_threshold_ms": monitor.drift_warning * 1000,
        "drift_block_threshold_ms": monitor.drift_block * 1000
    })
    
    # Do initial check
    initial_drift = await monitor.check_drift()
    if initial_drift is not None:
        system_logger.info("Initial NTP drift check", {
            "drift_ms": initial_drift * 1000,
            "status": "NORMAL" if abs(initial_drift) < monitor.drift_warning else "WARNING"
        })


def is_trading_allowed_by_clock() -> bool:
    """Check if trading is allowed based on clock discipline."""
    monitor = get_ntp_monitor()
    return monitor.is_trading_allowed()

