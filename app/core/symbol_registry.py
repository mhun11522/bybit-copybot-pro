"""Symbol metadata registry with quantization support."""

import asyncio
from decimal import Decimal
from typing import Dict, Any, Optional, List
from app.core.decimal_config import to_decimal, quantize_price, quantize_qty
from app.core.strict_config import STRICT_CONFIG
from app.core.logging import system_logger
from app.bybit.client import BybitClient

class SymbolInfo:
    """Symbol metadata container."""
    
    def __init__(self, symbol: str, data: Dict[str, Any]):
        self.symbol = symbol
        
        # Extract lot size filter (quantity constraints)
        lot_size_filter = data.get('lotSizeFilter', {})
        self.min_qty = to_decimal(lot_size_filter.get('minOrderQty', '0.001'))
        self.max_qty = to_decimal(lot_size_filter.get('maxOrderQty', '1000000'))
        self.step_size = to_decimal(lot_size_filter.get('qtyStep', '0.001'))
        self.min_notional = to_decimal(lot_size_filter.get('minNotionalValue', '5'))
        
        # Extract price filter (price constraints)
        price_filter = data.get('priceFilter', {})
        self.tick_size = to_decimal(price_filter.get('tickSize', '0.01'))
        
        # Extract leverage filter
        leverage_filter = data.get('leverageFilter', {})
        self.max_leverage = to_decimal(leverage_filter.get('maxLeverage', '50'))
        
        # Symbol status
        self.status = data.get('status', 'Trading')
        self.is_trading = self.status == 'Trading'
        
        # Calculate quantity precision from step size
        step_str = str(self.step_size)
        if '.' in step_str:
            self.qty_precision = len(step_str.split('.')[1])
        else:
            self.qty_precision = 0
    
    def quantize_price(self, price: Decimal) -> Decimal:
        """Quantize price to tick size."""
        return quantize_price(price, self.tick_size)
    
    def quantize_qty(self, qty: Decimal) -> Decimal:
        """Quantize quantity to step size."""
        return quantize_qty(qty, self.step_size)
    
    def format_qty(self, qty: Decimal) -> str:
        """Format quantity as string with correct precision for Bybit API."""
        # First quantize to step size
        quantized_qty = self.quantize_qty(qty)
        # Then format with correct decimal places
        return format(quantized_qty, f".{self.qty_precision}f")
    
    def validate_qty(self, qty: Decimal) -> bool:
        """Validate quantity is within limits."""
        return self.min_qty <= qty <= self.max_qty
    
    def validate_notional(self, notional: Decimal) -> bool:
        """Validate notional value meets minimum."""
        return notional >= self.min_notional
    
    def validate_price(self, price: Decimal) -> bool:
        """Validate price is within reasonable bounds."""
        # Basic price validation - should be positive and not too extreme
        return price > Decimal("0") and price < Decimal("1000000")
    
    def get_max_leverage(self) -> Decimal:
        """Get maximum allowed leverage."""
        return min(self.max_leverage, STRICT_CONFIG.pyramid_levels[-1]["target_lev"])

class SymbolRegistry:
    """Registry for symbol metadata and quantization."""
    
    def __init__(self):
        self._symbols: Dict[str, SymbolInfo] = {}
        self._last_update = 0
        self._update_interval = 300  # 5 minutes
        self._bybit_client = None
    
    def _get_bybit_client(self) -> BybitClient:
        """Get singleton Bybit client."""
        if self._bybit_client is None:
            # Use the global singleton instance
            from app.bybit.client import get_bybit_client
            self._bybit_client = get_bybit_client()
            system_logger.info(f"Symbol registry using singleton client with endpoint: {self._bybit_client.http.base_url}")
        return self._bybit_client
    
    async def _fetch_symbols(self) -> Dict[str, SymbolInfo]:
        """Fetch symbol metadata from Bybit."""
        try:
            client = self._get_bybit_client()
            
            # Fetch all linear (perpetual) symbols
            result = await client.instruments("linear", "")
            
            if result.get("retCode") != 0:
                raise Exception(f"Failed to fetch symbols: {result.get('retMsg')}")
            
            symbols = {}
            instruments = result.get("result", {}).get("list", [])
            
            for instrument in instruments:
                symbol = instrument.get("symbol", "")
                status = instrument.get("status", "")
                # Only USDT linear perpetuals (e.g., BTCUSDT, ETHUSDT)
                if status == "Trading" and symbol.endswith("USDT"):
                    symbols[symbol] = SymbolInfo(symbol, instrument)
            
            system_logger.info(f"Fetched {len(symbols)} trading symbols")
            return symbols
            
        except Exception as e:
            system_logger.error(f"Failed to fetch symbols: {e}", exc_info=True)
            return {}
    
    async def update_symbols(self, force: bool = False):
        """Update symbol registry."""
        import time
        now = time.time()
        
        if not force and now - self._last_update < self._update_interval:
            return
        
        try:
            symbols = await self._fetch_symbols()
            self._symbols.update(symbols)
            self._last_update = now
            
            system_logger.info(f"Symbol registry updated with {len(self._symbols)} symbols")
            
        except Exception as e:
            system_logger.error(f"Symbol registry update failed: {e}", exc_info=True)
    
    async def get_symbol_info(self, symbol: str) -> Optional[SymbolInfo]:
        """Get symbol information."""
        await self.update_symbols()
        return self._symbols.get(symbol)
    
    async def is_symbol_valid(self, symbol: str) -> bool:
        """Check if symbol is valid and trading."""
        info = await self.get_symbol_info(symbol)
        return info is not None and info.is_trading
    
    async def get_all_symbols(self) -> List[str]:
        """Get list of all available trading symbols."""
        await self.update_symbols()
        return [symbol for symbol, info in self._symbols.items() if info.is_trading]
    
    async def refresh_symbols(self):
        """Force refresh symbol cache."""
        self._last_update = None
        await self.update_symbols()
    
    async def quantize_price(self, symbol: str, price: Decimal) -> Optional[Decimal]:
        """Quantize price for symbol."""
        info = await self.get_symbol_info(symbol)
        if info is None:
            return None
        return info.quantize_price(price)
    
    async def quantize_qty(self, symbol: str, qty: Decimal) -> Optional[Decimal]:
        """Quantize quantity for symbol."""
        info = await self.get_symbol_info(symbol)
        if info is None:
            return None
        return info.quantize_qty(qty)
    
    async def validate_order(self, symbol: str, qty: Decimal, price: Decimal) -> Dict[str, Any]:
        """Validate order parameters."""
        info = await self.get_symbol_info(symbol)
        if info is None:
            return {
                'valid': False,
                'error': 'Symbol not found or not trading'
            }
        
        # Quantize values
        quantized_price = info.quantize_price(price)
        quantized_qty = info.quantize_qty(qty)
        
        # Validate quantity
        if not info.validate_qty(quantized_qty):
            return {
                'valid': False,
                'error': f'Quantity {quantized_qty} outside limits [{info.min_qty}, {info.max_qty}]'
            }
        
        # Validate notional
        notional = quantized_qty * quantized_price
        if not info.validate_notional(notional):
            return {
                'valid': False,
                'error': f'Notional {notional} below minimum {info.min_notional} USDT'
            }
        
        return {
            'valid': True,
            'quantized_price': quantized_price,
            'quantized_qty': quantized_qty,
            'notional': notional,
            'symbol_info': info
        }
    
    async def get_all_symbols(self) -> List[str]:
        """Get all valid symbols."""
        await self.update_symbols()
        return [symbol for symbol, info in self._symbols.items() if info.is_trading]
    
    async def get_symbol_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        await self.update_symbols()
        return {
            'total_symbols': len(self._symbols),
            'trading_symbols': sum(1 for info in self._symbols.values() if info.is_trading),
            'last_update': self._last_update,
            'update_interval': self._update_interval
        }

# Global registry instance
_registry_instance = None

def get_symbol_registry() -> SymbolRegistry:
    """Get global symbol registry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = SymbolRegistry()
    return _registry_instance

async def validate_symbol(symbol: str) -> bool:
    """Validate symbol (convenience function)."""
    registry = get_symbol_registry()
    return await registry.is_symbol_valid(symbol)

async def quantize_order_params(symbol: str, qty: Decimal, price: Decimal) -> Optional[Dict[str, Any]]:
    """Quantize and validate order parameters (convenience function)."""
    registry = get_symbol_registry()
    return await registry.validate_order(symbol, qty, price)