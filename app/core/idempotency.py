"""
Idempotency management with 90-second sliding window.

CLIENT SPEC Line 295: Implement deterministic clientOrderId/orderLinkId:
    trade_id|step|hash(signal_id|OEP|qty|price)

This ensures:
1. Same signal → same orderLinkId (idempotency)
2. Different signals → different orderLinkId (uniqueness)
3. Deterministic replay (can reconstruct orderLinkId from data)
"""

import time
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal
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
        """Mark signal as processed (adds to cache without checking)."""
        key = self._create_idempotency_key(signal)
        self._cache[key] = time.time()
        # NOTE: Don't call is_duplicate() here - that would check the cache
        # and find the signal that was just added, causing false duplicate detection
    
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


# ============================================================================
# Deterministic orderLinkId Generation (CLIENT SPEC Line 295)
# ============================================================================

def generate_deterministic_order_link_id(
    trade_id: str,
    step: str,
    signal_id: str,
    oep: Decimal,  # Original Entry Price
    qty: Decimal,
    price: Decimal
) -> str:
    """
    Generate deterministic orderLinkId per CLIENT SPEC.
    
    CLIENT SPEC Line 295: "trade_id|step|hash(signal_id|OEP|qty|price)"
    
    Format: {trade_id}|{step}|{hash}
    
    Where:
    - trade_id: Unique identifier for this trade
    - step: Order step (E1, E2, TP1, TP2, SL, etc.)
    - hash: First 8 chars of SHA256(signal_id|OEP|qty|price)
    
    Args:
        trade_id: Trade identifier (e.g., "TRADE123ABC")
        step: Order step (e.g., "E1", "E2", "TP1", "SL")
        signal_id: Original signal identifier
        oep: Original Entry Price (Decimal)
        qty: Quantity (Decimal)
        price: Order price (Decimal)
    
    Returns:
        Deterministic orderLinkId (e.g., "TRADE123|E1|a1b2c3d4")
    
    Examples:
        >>> generate_deterministic_order_link_id(
        ...     "TRADE123", "E1", "signal_456", 
        ...     Decimal("50000"), Decimal("0.001"), Decimal("49950")
        ... )
        "TRADE123|E1|a1b2c3d4"
    """
    # Create hash payload
    payload = f"{signal_id}|{oep}|{qty}|{price}"
    
    # Compute SHA256 hash
    hash_full = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    
    # Take first 8 characters of hash
    hash_short = hash_full[:8]
    
    # Format: trade_id|step|hash
    order_link_id = f"{trade_id}|{step}|{hash_short}"
    
    # Bybit orderLinkId has max length limit (check docs), typically 36 chars
    # Truncate if needed
    max_length = 36
    if len(order_link_id) > max_length:
        # Truncate trade_id if needed
        available_for_trade_id = max_length - len(step) - len(hash_short) - 2  # 2 for pipes
        trade_id_truncated = trade_id[:available_for_trade_id]
        order_link_id = f"{trade_id_truncated}|{step}|{hash_short}"
    
    system_logger.debug("Generated deterministic orderLinkId", {
        "trade_id": trade_id,
        "step": step,
        "signal_id": signal_id,
        "oep": str(oep),
        "qty": str(qty),
        "price": str(price),
        "order_link_id": order_link_id
    })
    
    return order_link_id


def parse_order_link_id(order_link_id: str) -> Optional[Dict[str, str]]:
    """
    Parse orderLinkId to extract components.
    
    Args:
        order_link_id: OrderLinkId in format "trade_id|step|hash"
    
    Returns:
        {"trade_id": str, "step": str, "hash": str} or None if invalid format
    """
    parts = order_link_id.split("|")
    
    if len(parts) == 3:
        return {
            "trade_id": parts[0],
            "step": parts[1],
            "hash": parts[2]
        }
    else:
        # Legacy format or different format
        system_logger.warning(f"OrderLinkId not in expected format: {order_link_id}")
        return None