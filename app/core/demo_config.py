"""Demo environment specific configuration and workarounds."""

import os
from decimal import Decimal
from typing import Dict, Any
from app.config.settings import BYBIT_ENDPOINT

class DemoConfig:
    """Configuration for Bybit demo trading environment."""
    
    @staticmethod
    def is_demo_environment() -> bool:
        """Check if we're running in demo environment."""
        env = os.getenv("TRADING_ENV", "").lower()
        endpoint = BYBIT_ENDPOINT.lower()
        # Accept either an explicit env flag or known hostnames
        return env in {"demo", "testnet"} or ("demo" in endpoint or "testnet" in endpoint)
    
    @staticmethod
    def get_demo_limits() -> Dict[str, Any]:
        """Get demo-specific limits and constraints."""
        return {
            # Position size limits (conservative but still meet min notional)
            'max_contracts_per_order': Decimal("1000"),  # Allow larger positions for demo
            'max_notional_per_order': Decimal("1000"),  # 1000 USDT max per order
            
            # Leverage limits (demo may have different limits)
            'max_leverage': Decimal("10"),  # Conservative leverage for demo
            
            # Price adjustment factors (more conservative for demo)
            'buy_price_factor': Decimal("0.995"),  # 0.5% below market
            'sell_price_factor': Decimal("1.005"),  # 0.5% above market
            
            # Retry configuration
            'max_retries': 5,  # More retries for demo
            'quantity_reduction_factor': Decimal("0.5"),  # Reduce by 50% on retry
            
            # Order type preferences for demo
            'preferred_order_type': "Limit",
            'preferred_time_in_force': "GTC",
            
            # Rate limiting (demo may have stricter limits)
            'min_request_interval': 0.5,  # 500ms between requests
        }
    
    @staticmethod
    def get_demo_symbol_limits(symbol: str) -> Dict[str, Any]:
        """Get symbol-specific demo limits."""
        # Some symbols may have different limits in demo
        symbol_limits = {
            'BTCUSDT': {
                'max_contracts': Decimal("100"),
                'max_notional': Decimal("1000"),
            },
            'ETHUSDT': {
                'max_contracts': Decimal("200"),
                'max_notional': Decimal("1000"),
            },
            'POWRUSDT': {
                'max_contracts': Decimal("1000"),
                'max_notional': Decimal("200"),
            },
            'NEOUSDT': {
                'max_contracts': Decimal("500"),
                'max_notional': Decimal("500"),
            },
            'ATHUSDT': {
                'max_contracts': Decimal("2000"),
                'max_notional': Decimal("200"),
            },
            'CHZUSDT': {
                'max_contracts': Decimal("2000"),
                'max_notional': Decimal("200"),
            },
        }
        
        return symbol_limits.get(symbol, {
            'max_contracts': Decimal("1000"),
            'max_notional': Decimal("200"),
        })
    
    @staticmethod
    def apply_demo_quantity_limit(contracts: Decimal, symbol: str) -> Decimal:
        """Apply demo-specific quantity limits."""
        if not DemoConfig.is_demo_environment():
            return contracts
        
        limits = DemoConfig.get_demo_limits()
        symbol_limits = DemoConfig.get_demo_symbol_limits(symbol)
        
        # Apply both global and symbol-specific limits
        max_contracts = min(limits['max_contracts_per_order'], symbol_limits['max_contracts'])
        
        if contracts > max_contracts:
            return max_contracts
        
        return contracts
    
    @staticmethod
    def get_demo_error_handling() -> Dict[str, Any]:
        """Get demo-specific error handling configuration."""
        return {
            'qty_invalid_retry': True,
            'qty_reduction_factor': Decimal("0.5"),
            'price_adjustment_retry': True,
            'price_adjustment_factor': Decimal("0.01"),  # 1% adjustment
            'max_retries': 5,
        }
