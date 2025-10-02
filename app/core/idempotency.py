"""Idempotency management with 90-second sliding window."""

import time
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from app.core.logging import system_logger
from app.core.strict_config import STRICT_CONFIG

class IdempotencyManager:
    """Manages signal idempotency with sliding window cache."""
    
    def __init__(self, ttl_seconds: int = None):
        self.ttl_seconds = ttl_seconds or STRICT_CONFIG.idempotency_ttl_seconds
        self._cache: Dict[str, float] = {}
        self._cleanup_interval = 30  # Cleanup every 30 seconds
        self._last_cleanup = time.time()
    
    def _cleanup_expired(self):
        """Remove expired entries from cache."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        expired_keys = [
            key for key, timestamp in self._cache.items()
            if now - timestamp > self.ttl_seconds
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        self._last_cleanup = now
        
        if expired_keys:
            system_logger.debug(f"Cleaned up {len(expired_keys)} expired idempotency entries")
    
    def _create_idempotency_key(self, signal: Dict[str, Any]) -> str:
        """Create idempotency key from signal data."""
        # Extract key components for idempotency
        source_name = signal.get('channel_name', 'unknown')
        timestamp_bucket = str(int(time.time() // 60))  # 1-minute buckets
        symbol = signal.get('symbol', '')
        side = signal.get('direction', '')
        entries = str(sorted(signal.get('entries', [])))
        tps = str(sorted(signal.get('tps', [])))
        sl = str(signal.get('sl', ''))
        
        # Create payload string
        payload = "|".join([
            source_name,
            timestamp_bucket,
            symbol,
            side,
            entries,
            tps,
            sl
        ])
        
        # Create SHA256 hash and take first 32 characters
        return hashlib.sha256(payload.encode()).hexdigest()[:32]
    
    def is_duplicate(self, signal: Dict[str, Any]) -> bool:
        """Check if signal is duplicate within TTL window."""
        self._cleanup_expired()
        
        key = self._create_idempotency_key(signal)
        now = time.time()
        
        if key in self._cache:
            # Check if within TTL
            if now - self._cache[key] < self.ttl_seconds:
                system_logger.info(f"Duplicate signal detected and suppressed", {
                    'symbol': signal.get('symbol'),
                    'channel': signal.get('channel_name'),
                    'key': key,
                    'age_seconds': now - self._cache[key]
                })
                return True
        
        # Add to cache
        self._cache[key] = now
        return False
    
    def mark_processed(self, signal: Dict[str, Any]):
        """Mark signal as processed (same as is_duplicate but explicit)."""
        self.is_duplicate(signal)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring."""
        now = time.time()
        active_entries = sum(
            1 for timestamp in self._cache.values()
            if now - timestamp < self.ttl_seconds
        )
        
        return {
            'total_entries': len(self._cache),
            'active_entries': active_entries,
            'ttl_seconds': self.ttl_seconds,
            'last_cleanup': self._last_cleanup
        }

# Global idempotency manager
_idempotency_manager = None

def get_idempotency_manager() -> IdempotencyManager:
    """Get global idempotency manager instance."""
    global _idempotency_manager
    if _idempotency_manager is None:
        _idempotency_manager = IdempotencyManager()
    return _idempotency_manager

def is_duplicate_signal(signal: Dict[str, Any]) -> bool:
    """Check if signal is duplicate (convenience function)."""
    return get_idempotency_manager().is_duplicate(signal)

def mark_signal_processed(signal: Dict[str, Any]):
    """Mark signal as processed (convenience function)."""
    get_idempotency_manager().mark_processed(signal)