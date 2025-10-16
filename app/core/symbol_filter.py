"""
Symbol Filter for Demo Environment

Automatically filters out symbols that are not available on Bybit demo.
This prevents signals from failing at the FSM stage due to unavailable symbols.

CLIENT REQUIREMENT: Auto-filtering of unavailable symbols in demo mode.
"""

import asyncio
from typing import Optional, Dict, Set
from datetime import datetime, timedelta
from app.core.logging import system_logger


class SymbolFilter:
    """
    Filters symbols that are not available on Bybit.
    
    Features:
    - Caches symbol availability (reduces API calls)
    - Auto-refreshes cache every 24 hours
    - Logs filtered symbols for transparency
    - Gracefully handles API errors
    """
    
    def __init__(self):
        self._available_symbols: Set[str] = set()
        self._unavailable_symbols: Set[str] = set()
        self._last_refresh: Optional[datetime] = None
        self._cache_duration = timedelta(hours=24)
        self._initialized = False
        self._refresh_lock = asyncio.Lock()
    
    async def is_symbol_available(self, symbol: str) -> bool:
        """
        Check if symbol is available on Bybit.
        
        Args:
            symbol: Trading symbol (e.g., BTCUSDT)
        
        Returns:
            True if symbol is available, False otherwise
        """
        # Initialize if not done
        if not self._initialized:
            await self._initialize_cache()
        
        # Refresh cache if expired
        if self._is_cache_expired():
            await self._refresh_cache()
        
        # Check cache
        if symbol in self._available_symbols:
            return True
        
        if symbol in self._unavailable_symbols:
            system_logger.debug(f"Symbol {symbol} filtered (not available on Bybit)", {
                'symbol': symbol,
                'reason': 'unavailable_on_bybit'
            })
            return False
        
        # Symbol not in cache - check live
        is_available = await self._check_symbol_live(symbol)
        
        # Update cache
        if is_available:
            self._available_symbols.add(symbol)
        else:
            self._unavailable_symbols.add(symbol)
        
        return is_available
    
    async def _initialize_cache(self):
        """Initialize symbol cache from Bybit."""
        async with self._refresh_lock:
            if self._initialized:
                return
            
            system_logger.info("Initializing symbol filter cache...")
            
            try:
                from app.core.symbol_registry import get_symbol_registry
                registry = get_symbol_registry()
                
                # Get all available symbols
                all_symbols = await registry.get_all_symbols()
                
                if all_symbols:
                    self._available_symbols = set(all_symbols)
                    system_logger.info(f"Symbol filter initialized with {len(self._available_symbols)} symbols")
                else:
                    system_logger.warning("Symbol filter initialized with empty cache")
                
                self._last_refresh = datetime.now()
                self._initialized = True
                
            except Exception as e:
                system_logger.error(f"Failed to initialize symbol filter: {e}", exc_info=True)
                # Continue with empty cache - will check live
                self._initialized = True
    
    def _is_cache_expired(self) -> bool:
        """Check if cache needs refresh."""
        if self._last_refresh is None:
            return True
        
        return datetime.now() - self._last_refresh > self._cache_duration
    
    async def _refresh_cache(self):
        """Refresh symbol cache in background."""
        async with self._refresh_lock:
            # Double-check still expired
            if not self._is_cache_expired():
                return
            
            system_logger.info("Refreshing symbol filter cache...")
            
            try:
                from app.core.symbol_registry import get_symbol_registry
                registry = get_symbol_registry()
                
                # Force refresh registry
                await registry.refresh_symbols()
                
                # Get updated symbols
                all_symbols = await registry.get_all_symbols()
                
                if all_symbols:
                    old_count = len(self._available_symbols)
                    self._available_symbols = set(all_symbols)
                    new_count = len(self._available_symbols)
                    
                    system_logger.info(f"Symbol filter cache refreshed: {old_count} → {new_count} symbols")
                    
                    # Clear unavailable cache (symbols may become available)
                    self._unavailable_symbols.clear()
                
                self._last_refresh = datetime.now()
                
            except Exception as e:
                system_logger.error(f"Failed to refresh symbol filter cache: {e}", exc_info=True)
    
    async def _check_symbol_live(self, symbol: str) -> bool:
        """
        Check symbol availability with live API call.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            True if symbol is available and trading
        """
        try:
            from app.core.symbol_registry import get_symbol_registry
            registry = get_symbol_registry()
            
            symbol_info = await registry.get_symbol_info(symbol)
            
            if symbol_info:
                is_trading = symbol_info.status == "Trading"
                
                if is_trading:
                    system_logger.info(f"Symbol {symbol} is available and trading")
                else:
                    system_logger.warning(f"Symbol {symbol} found but status is {symbol_info.status}")
                
                return is_trading
            else:
                system_logger.warning(f"Symbol {symbol} not found on Bybit", {
                    'symbol': symbol,
                    'reason': 'symbol_not_found'
                })
                return False
        
        except Exception as e:
            system_logger.error(f"Error checking symbol {symbol}: {e}", exc_info=True)
            # On error, default to unavailable (safe choice)
            return False
    
    def get_stats(self) -> Dict[str, any]:
        """Get filter statistics."""
        return {
            'available_symbols': len(self._available_symbols),
            'unavailable_symbols': len(self._unavailable_symbols),
            'last_refresh': self._last_refresh.isoformat() if self._last_refresh else None,
            'cache_age_hours': (datetime.now() - self._last_refresh).total_seconds() / 3600 if self._last_refresh else None,
            'initialized': self._initialized
        }
    
    def get_available_symbols(self) -> Set[str]:
        """Get set of available symbols."""
        return self._available_symbols.copy()
    
    def get_unavailable_symbols(self) -> Set[str]:
        """Get set of unavailable symbols."""
        return self._unavailable_symbols.copy()


# Global symbol filter instance
_symbol_filter: Optional[SymbolFilter] = None


def get_symbol_filter() -> SymbolFilter:
    """Get or create global symbol filter instance."""
    global _symbol_filter
    
    if _symbol_filter is None:
        _symbol_filter = SymbolFilter()
    
    return _symbol_filter


async def is_symbol_available(symbol: str) -> bool:
    """
    Check if symbol is available on Bybit.
    
    Convenience function for quick checks.
    
    Args:
        symbol: Trading symbol (e.g., BTCUSDT)
    
    Returns:
        True if symbol is available, False otherwise
    """
    filter_instance = get_symbol_filter()
    return await filter_instance.is_symbol_available(symbol)

