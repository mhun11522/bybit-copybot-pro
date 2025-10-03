"""Signal blocking system with 3-hour window and 5% tolerance."""

import time
import hashlib
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from app.core.logging import system_logger
from app.core.strict_config import STRICT_CONFIG

class SignalBlockingManager:
    """Manages signal blocking with 3-hour window and 5% tolerance."""
    
    def __init__(self):
        self.block_duration_seconds = 10800  # 3 hours
        self.tolerance_percent = Decimal("5")  # 5% tolerance
        self._blocked_signals: Dict[str, Dict[str, Any]] = {}
        self._cleanup_interval = 300  # Cleanup every 5 minutes
        self._last_cleanup = time.time()
    
    def _cleanup_expired(self):
        """Remove expired blocked signals."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        expired_keys = [
            key for key, data in self._blocked_signals.items()
            if now - data['blocked_at'] > self.block_duration_seconds
        ]
        
        for key in expired_keys:
            del self._blocked_signals[key]
        
        self._last_cleanup = now
        
        if expired_keys:
            system_logger.debug(f"Cleaned up {len(expired_keys)} expired blocked signals")
    
    def _create_signal_key(self, signal: Dict[str, Any]) -> str:
        """Create blocking key from signal data (symbol + direction only)."""
        symbol = signal.get('symbol', '').upper()
        direction = signal.get('direction', '').upper()
        
        # Key is just symbol + direction (not channel-specific)
        return f"{symbol}:{direction}"
    
    def _calculate_value_difference(self, signal1: Dict[str, Any], signal2: Dict[str, Any]) -> Decimal:
        """Calculate percentage difference between signal values."""
        try:
            # Get entry prices
            entries1 = signal1.get('entries', [])
            entries2 = signal2.get('entries', [])
            
            if not entries1 or not entries2:
                return Decimal("100")  # If no entries, consider completely different
            
            # Use first entry for comparison
            entry1 = Decimal(str(entries1[0]))
            entry2 = Decimal(str(entries2[0]))
            
            if entry1 == 0 or entry2 == 0:
                return Decimal("100")
            
            # Calculate percentage difference
            diff = abs(entry1 - entry2) / max(entry1, entry2) * Decimal("100")
            return diff
            
        except Exception as e:
            system_logger.error(f"Error calculating value difference: {e}")
            return Decimal("100")  # If error, consider completely different
    
    def _is_similar_signal(self, signal1: Dict[str, Any], signal2: Dict[str, Any]) -> bool:
        """Check if two signals are similar (same symbol, direction, within 5% tolerance)."""
        # Must be same symbol and direction
        if (signal1.get('symbol', '').upper() != signal2.get('symbol', '').upper() or
            signal1.get('direction', '').upper() != signal2.get('direction', '').upper()):
            return False
        
        # Check if values are within 5% tolerance
        value_diff = self._calculate_value_difference(signal1, signal2)
        return value_diff <= self.tolerance_percent
    
    def is_signal_blocked(self, signal: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Check if signal should be blocked.
        
        Returns:
            (is_blocked, reason)
        """
        self._cleanup_expired()
        
        signal_key = self._create_signal_key(signal)
        now = time.time()
        
        # Check if there's a blocked signal for this symbol+direction
        if signal_key in self._blocked_signals:
            blocked_data = self._blocked_signals[signal_key]
            
            # Check if still within block duration
            if now - blocked_data['blocked_at'] < self.block_duration_seconds:
                # Check if this signal is similar to the blocked one
                if self._is_similar_signal(signal, blocked_data['original_signal']):
                    reason = f"Similar signal blocked for 3 hours (from {blocked_data['original_channel']})"
                    system_logger.info(f"Signal blocked: {reason}", {
                        'symbol': signal.get('symbol'),
                        'direction': signal.get('direction'),
                        'current_channel': signal.get('channel_name'),
                        'blocked_channel': blocked_data['original_channel'],
                        'blocked_at': blocked_data['blocked_at'],
                        'remaining_seconds': self.block_duration_seconds - (now - blocked_data['blocked_at'])
                    })
                    return True, reason
        
        # Signal is not blocked, but check if we should block future similar signals
        # This implements the "block for copy" logic
        self._block_signal(signal)
        
        return False, None
    
    def _block_signal(self, signal: Dict[str, Any]):
        """Block future similar signals for 3 hours."""
        signal_key = self._create_signal_key(signal)
        now = time.time()
        
        # Store the signal for blocking future similar ones
        self._blocked_signals[signal_key] = {
            'original_signal': signal.copy(),
            'original_channel': signal.get('channel_name', 'unknown'),
            'blocked_at': now
        }
        
        system_logger.info(f"Signal will block similar signals for 3 hours", {
            'symbol': signal.get('symbol'),
            'direction': signal.get('direction'),
            'channel': signal.get('channel_name'),
            'blocked_until': now + self.block_duration_seconds
        })
    
    def get_blocking_stats(self) -> Dict[str, Any]:
        """Get blocking statistics for monitoring."""
        now = time.time()
        active_blocks = sum(
            1 for data in self._blocked_signals.values()
            if now - data['blocked_at'] < self.block_duration_seconds
        )
        
        return {
            'total_blocked_signals': len(self._blocked_signals),
            'active_blocks': active_blocks,
            'block_duration_hours': self.block_duration_seconds / 3600,
            'tolerance_percent': float(self.tolerance_percent),
            'last_cleanup': self._last_cleanup
        }

# Global signal blocking manager
_signal_blocking_manager = None

def get_signal_blocking_manager() -> SignalBlockingManager:
    """Get global signal blocking manager instance."""
    global _signal_blocking_manager
    if _signal_blocking_manager is None:
        _signal_blocking_manager = SignalBlockingManager()
    return _signal_blocking_manager

def is_signal_blocked(signal: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Check if signal is blocked (convenience function)."""
    return get_signal_blocking_manager().is_signal_blocked(signal)