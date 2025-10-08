"""Trade limiter to enforce maximum concurrent trades."""

import threading
from typing import Dict, Set, Any
from decimal import Decimal
from app.core.logging import system_logger
from app.core.strict_config import STRICT_CONFIG

class TradeLimiter:
    """Limits concurrent trades to prevent overexposure."""
    
    def __init__(self, max_trades: int = None):
        """
        Initialize trade limiter.
        
        Args:
            max_trades: Maximum concurrent trades (defaults to STRICT_CONFIG.max_trades)
        """
        self.max_trades = max_trades or STRICT_CONFIG.max_trades
        self.active_trades: Set[str] = set()
        self.trade_symbols: Dict[str, str] = {}  # trade_id -> symbol mapping
        self._lock = threading.RLock()  # Thread-safe operations
        
    def can_start_trade(self, symbol: str) -> bool:
        """
        Check if a new trade can be started.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            True if trade can be started, False if at limit
        """
        with self._lock:
            current_count = len(self.active_trades)
            
            if current_count >= self.max_trades:
                system_logger.warning(f"Trade limit reached: {current_count}/{self.max_trades} trades active", {
                    'active_trades': list(self.active_trades),
                    'symbol': symbol,
                    'max_trades': self.max_trades
                })
                return False
                
            return True
    
    def start_trade(self, trade_id: str, symbol: str) -> bool:
        """
        Register a new trade.
        
        Args:
            trade_id: Unique trade identifier
            symbol: Trading symbol
            
        Returns:
            True if trade was registered, False if at limit
        """
        with self._lock:
            if not self.can_start_trade(symbol):
                return False
                
            self.active_trades.add(trade_id)
            self.trade_symbols[trade_id] = symbol
            
            system_logger.info(f"Trade started: {trade_id} ({symbol})", {
                'trade_id': trade_id,
                'symbol': symbol,
                'active_count': len(self.active_trades),
                'max_trades': self.max_trades
            })
            
            return True
    
    def end_trade(self, trade_id: str) -> bool:
        """
        Unregister a completed trade.
        
        Args:
            trade_id: Unique trade identifier
            
        Returns:
            True if trade was unregistered, False if not found
        """
        with self._lock:
            if trade_id not in self.active_trades:
                system_logger.warning(f"Trade not found for ending: {trade_id}")
                return False
                
            symbol = self.trade_symbols.pop(trade_id, "unknown")
            self.active_trades.remove(trade_id)
            
            system_logger.info(f"Trade ended: {trade_id} ({symbol})", {
                'trade_id': trade_id,
                'symbol': symbol,
                'active_count': len(self.active_trades),
                'max_trades': self.max_trades
            })
            
            return True
    
    def get_active_trades(self) -> Dict[str, Any]:
        """Get current active trades information."""
        with self._lock:
            return {
                'count': len(self.active_trades),
                'max_trades': self.max_trades,
                'trade_ids': list(self.active_trades),
                'symbols': list(self.trade_symbols.values()),
                'utilization_pct': (len(self.active_trades) / self.max_trades) * 100
            }
    
    def is_at_capacity(self) -> bool:
        """Check if at maximum capacity."""
        with self._lock:
            return len(self.active_trades) >= self.max_trades

# Global trade limiter instance
_global_trade_limiter = None

def get_trade_limiter() -> TradeLimiter:
    """Get the global trade limiter instance."""
    global _global_trade_limiter
    if _global_trade_limiter is None:
        _global_trade_limiter = TradeLimiter()
    return _global_trade_limiter
