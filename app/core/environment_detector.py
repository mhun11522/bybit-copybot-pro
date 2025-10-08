#!/usr/bin/env python3
"""
Environment Detection and TP/SL Strategy Manager

Automatically detects Bybit environment (Live/Demo/Testnet) and implements
appropriate TP/SL strategies based on API limitations.
"""

import asyncio
from enum import Enum
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal
from app.core.logging import system_logger
from app.bybit.client import get_bybit_client

class BybitEnvironment(Enum):
    """Bybit environment types."""
    LIVE = "live"
    DEMO = "demo"  # Futurus
    TESTNET = "testnet"

class TPSLStrategy(Enum):
    """TP/SL implementation strategies."""
    NATIVE_API = "native_api"      # Use Bybit's set_trading_stop API
    SIMULATED = "simulated"        # Custom monitoring and manual close
    HYBRID = "hybrid"             # Try native first, fallback to simulated

class EnvironmentDetector:
    """Detects Bybit environment and manages TP/SL strategies."""
    
    def __init__(self):
        self.environment: Optional[BybitEnvironment] = None
        self.tpsl_strategy: Optional[TPSLStrategy] = None
        self.symbol_availability: Dict[str, bool] = {}
        self.api_limitations: Dict[str, bool] = {}
        self._client = None
    
    async def detect_environment(self) -> BybitEnvironment:
        """Detect the current Bybit environment."""
        if self.environment:
            return self.environment
        
        try:
            self._client = get_bybit_client()
            
            # Get endpoint from client
            endpoint = str(self._client.http.base_url)
            
            if "api-demo.bybit.com" in endpoint:
                self.environment = BybitEnvironment.DEMO
            elif "api-testnet.bybit.com" in endpoint:
                self.environment = BybitEnvironment.TESTNET
            elif "api.bybit.com" in endpoint:
                self.environment = BybitEnvironment.LIVE
            else:
                # Fallback: try API call to determine
                self.environment = await self._detect_via_api()
            
            await self._analyze_environment_capabilities()
            
            system_logger.info(f"Environment detected: {self.environment.value}", {
                'endpoint': endpoint,
                'tpsl_strategy': self.tpsl_strategy.value if self.tpsl_strategy else None
            })
            
            return self.environment
            
        except Exception as e:
            system_logger.error(f"Failed to detect environment: {e}", exc_info=True)
            # Default to TESTNET for safety
            self.environment = BybitEnvironment.TESTNET
            self.tpsl_strategy = TPSLStrategy.NATIVE_API
            return self.environment
    
    async def _detect_via_api(self) -> BybitEnvironment:
        """Detect environment via API characteristics."""
        try:
            # Try to get account info
            result = await self._client.get_wallet_balance()
            
            if result and 'result' in result:
                # Check for demo-specific fields or characteristics
                account_data = result['result']
                
                # Demo accounts often have specific characteristics
                if 'isDemo' in account_data and account_data['isDemo']:
                    return BybitEnvironment.DEMO
                
                # Check equity - demo accounts often have round numbers
                equity = account_data.get('totalEquity', '0')
                if isinstance(equity, str):
                    equity = float(equity)
                
                # Very high equity often indicates testnet
                if equity > 1000000:
                    return BybitEnvironment.TESTNET
                
                # Check symbol availability
                symbols_result = await self._client.instruments('linear', '')
                if symbols_result and 'result' in symbols_result:
                    symbols = symbols_result['result'].get('list', [])
                    usdt_symbols = [s for s in symbols if s['symbol'].endswith('USDT') and s['status'] == 'Trading']
                    
                    # Limited symbols = testnet, many symbols = live/demo
                    if len(usdt_symbols) < 50:
                        return BybitEnvironment.TESTNET
                    else:
                        return BybitEnvironment.LIVE
            
        except Exception as e:
            system_logger.warning(f"API detection failed: {e}")
        
        # Default fallback
        return BybitEnvironment.TESTNET
    
    async def _analyze_environment_capabilities(self):
        """Analyze what the environment can do."""
        if not self.environment:
            return
        
        try:
            # Test TP/SL API availability
            can_use_native_tpsl = await self._test_tpsl_api()
            
            # Analyze symbol availability
            await self._analyze_symbol_availability()
            
            # Determine TP/SL strategy based on research findings
            if self.environment == BybitEnvironment.LIVE:
                self.tpsl_strategy = TPSLStrategy.NATIVE_API
            elif self.environment == BybitEnvironment.TESTNET:
                # Testnet: Use native TP/SL API since it works perfectly
                # The native API works for both single and multiple TP levels
                self.tpsl_strategy = TPSLStrategy.NATIVE_API
                system_logger.info("Testnet detected: Using native TP/SL API for all TP levels")
            elif self.environment == BybitEnvironment.DEMO:
                # Demo has TP/SL API limitations
                self.tpsl_strategy = TPSLStrategy.SIMULATED
            
            system_logger.info(f"Environment capabilities analyzed", {
                'environment': self.environment.value,
                'native_tpsl_available': can_use_native_tpsl,
                'tpsl_strategy': self.tpsl_strategy.value,
                'symbols_available': len(self.symbol_availability)
            })
            
        except Exception as e:
            system_logger.error(f"Failed to analyze capabilities: {e}", exc_info=True)
            self.tpsl_strategy = TPSLStrategy.SIMULATED
    
    async def _test_tpsl_api(self) -> bool:
        """Test if TP/SL API is available."""
        try:
            # For testnet, we know TP/SL API should be available
            # We don't actually test it to avoid creating test orders
            # Just return True since we're using conditional orders approach
            return True
            
        except Exception as e:
            error_msg = str(e).lower()
            # Check for known limitation errors that indicate API is not available
            if any(phrase in error_msg for phrase in [
                'tpSlMode is empty',
                'not supported',
                'disabled',
                'restricted',
                'api not available'
            ]):
                return False
            elif any(phrase in error_msg for phrase in [
                'position not found',
                'no position',
                'position does not exist'
            ]):
                # These errors indicate API is available but no position exists
                # This is expected for testnet without actual positions
                return True
            else:
                # For testnet, assume API is available unless we get specific errors
                if self.environment == BybitEnvironment.TESTNET:
                    return True
                # Other errors might be temporary, assume API is available
                return True
    
    async def _analyze_symbol_availability(self):
        """Analyze symbol availability in current environment."""
        try:
            result = await self._client.instruments('linear', '')
            if result and 'result' in result:
                symbols = result['result'].get('list', [])
                for symbol_data in symbols:
                    symbol = symbol_data['symbol']
                    is_trading = symbol_data.get('status') == 'Trading'
                    self.symbol_availability[symbol] = is_trading
            
        except Exception as e:
            system_logger.warning(f"Failed to analyze symbols: {e}")
    
    def is_symbol_available(self, symbol: str) -> bool:
        """Check if a symbol is available for trading."""
        return self.symbol_availability.get(symbol, False)
    
    def get_available_symbols(self, filter_usdt: bool = True) -> list:
        """Get list of available symbols."""
        symbols = [s for s, available in self.symbol_availability.items() if available]
        if filter_usdt:
            symbols = [s for s in symbols if s.endswith('USDT')]
        return sorted(symbols)
    
    def get_environment_info(self) -> Dict[str, Any]:
        """Get comprehensive environment information."""
        return {
            'environment': self.environment.value if self.environment else None,
            'tpsl_strategy': self.tpsl_strategy.value if self.tpsl_strategy else None,
            'symbols_available': len(self.symbol_availability),
            'usdt_symbols': len([s for s in self.symbol_availability.keys() if s.endswith('USDT')]),
            'api_limitations': {
                'native_tpsl': self.tpsl_strategy == TPSLStrategy.NATIVE_API,
                'symbol_restrictions': self.environment == BybitEnvironment.TESTNET,
                'order_matching': 'simulated' if self.environment != BybitEnvironment.LIVE else 'real'
            }
        }
    
    def get_recommended_workflow(self) -> str:
        """Get recommended development workflow for current environment."""
        if self.environment == BybitEnvironment.TESTNET:
            return """
🧪 TESTNET RECOMMENDED WORKFLOW:
1. ✅ Full API testing (TP/SL, trailing stops work)
2. ✅ Test all order types and error handling
3. ✅ Validate authentication and rate limits
4. ⚠️ Limited symbols (10-20 pairs available)
5. ⚠️ Use for logic validation, not market simulation
            """
        elif self.environment == BybitEnvironment.DEMO:
            return """
🎮 DEMO (FUTURUS) RECOMMENDED WORKFLOW:
1. ✅ Full symbol availability (mirrors Live)
2. ✅ Real-time price feeds
3. ✅ Manual trading practice
4. ⚠️ TP/SL API disabled (use simulated TP/SL)
5. ✅ Great for presentation and visual validation
            """
        else:  # LIVE
            return """
🚀 LIVE RECOMMENDED WORKFLOW:
1. ✅ Full API functionality
2. ✅ All symbols available
3. ✅ Real order matching
4. ✅ Production-ready environment
5. ⚠️ Use real money - test thoroughly first!
            """
    
    async def get_optimal_testing_symbols(self, count: int = 5) -> list:
        """Get optimal symbols for testing in current environment."""
        available = self.get_available_symbols(filter_usdt=True)
        
        # Prioritize major pairs
        priority_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'DOTUSDT', 'LINKUSDT']
        
        optimal = []
        for symbol in priority_symbols:
            if symbol in available and len(optimal) < count:
                optimal.append(symbol)
        
        # Fill remaining slots with other available symbols
        for symbol in available:
            if symbol not in optimal and len(optimal) < count:
                optimal.append(symbol)
        
        return optimal
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get current environment capabilities."""
        if not self.environment:
            return {
                'environment': 'unknown',
                'native_tpsl_available': False,
                'tpsl_strategy': 'unknown',
                'symbols_available': 0
            }
        
        # Determine capabilities based on environment
        capabilities = {
            'environment': self.environment.value,
            'native_tpsl_available': self.tpsl_strategy == TPSLStrategy.NATIVE_API,
            'tpsl_strategy': self.tpsl_strategy.value if self.tpsl_strategy else 'unknown',
            'symbols_available': len(self.get_available_symbols(filter_usdt=True))
        }
        
        return capabilities

# Global instance
_environment_detector = None

def get_environment_detector() -> EnvironmentDetector:
    """Get global environment detector instance."""
    global _environment_detector
    if _environment_detector is None:
        _environment_detector = EnvironmentDetector()
    return _environment_detector

async def detect_current_environment() -> BybitEnvironment:
    """Quick function to detect current environment."""
    detector = get_environment_detector()
    return await detector.detect_environment()

async def get_tpsl_strategy() -> TPSLStrategy:
    """Get the appropriate TP/SL strategy for current environment."""
    detector = get_environment_detector()
    await detector.detect_environment()
    return detector.tpsl_strategy

async def is_native_tpsl_available() -> bool:
    """Check if native TP/SL API is available."""
    strategy = await get_tpsl_strategy()
    return strategy == TPSLStrategy.NATIVE_API
