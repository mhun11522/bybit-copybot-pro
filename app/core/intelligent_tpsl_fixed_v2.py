import asyncio
import json
from decimal import Decimal
from typing import Dict, Any, List, Optional, Callable
from app.core.logging import system_logger
from app.core.environment_detector import get_environment_detector, TPSLStrategy, BybitEnvironment
from app.bybit.client import get_bybit_client
from app.core.simulated_tpsl import get_simulated_tpsl_manager

class IntelligentTPSLHandlerFixed:
    """Fixed intelligent TP/SL handler with correct V5 API implementation."""
    
    def __init__(self):
        self._client = None
        self.environment_detector = get_environment_detector()
        self.simulated_manager = get_simulated_tpsl_manager()
        self.initialized = False

    async def initialize(self):
        if not self.initialized:
            self._client = get_bybit_client()
            
            # Force testnet environment and native TP/SL for testnet BEFORE analysis
            if str(self._client.http.base_url) == "https://api-testnet.bybit.com":
                self.environment_detector.environment = BybitEnvironment.TESTNET
                self.environment_detector.tpsl_strategy = TPSLStrategy.NATIVE_API
                system_logger.info(f"Forced testnet environment and native TP/SL API")
            else:
                # Only run analysis if not testnet
                await self.environment_detector._analyze_environment_capabilities()
            
            system_logger.info(f"Intelligent TP/SL handler initialized", data={
                "environment": self.environment_detector.environment.value if self.environment_detector.environment else "Unknown",
                "native_tpsl_available": self.environment_detector.tpsl_strategy == TPSLStrategy.NATIVE_API
            })
            self.initialized = True

    async def set_tpsl(
        self,
        symbol: str,
        side: str,
        position_size: Decimal,
        entry_price: Decimal,
        tp_levels: List[Decimal],
        sl_percentage: Optional[Decimal],
        trade_id: str,
        callback: Callable[[Dict[str, Any]], None]
    ) -> Dict[str, Any]:
        """
        Sets TP/SL for a given symbol and position.
        Adapts between native Bybit API and simulated approach based on environment.
        """
        if not self.initialized:
            await self.initialize()

        try:
            # Detect environment capabilities
            environment = await self.environment_detector.detect_environment()
            capabilities = self.environment_detector.get_capabilities()
            
            # Force native API for testnet (since we know it works)
            if environment == BybitEnvironment.TESTNET or capabilities.get('native_tpsl_available', False):
                # Use native API - attach TP/SL to position
                system_logger.info(f"Using native TP/SL API for {trade_id} (testnet: {environment == BybitEnvironment.TESTNET})")
                return await self._set_native_tpsl_attached(
                    symbol, side, tp_levels, sl_percentage, trade_id, position_size
                )
            else:
                # Fall back to simulated TP/SL
                system_logger.info(f"Falling back to simulated TP/SL for {trade_id}")
                success = await self.simulated_manager.add_tpsl_order(
                    symbol, side, position_size, entry_price, tp_levels, sl_percentage, trade_id, callback
                )
                return {
                    'success': success,
                    'method': 'simulated',
                    'trade_id': trade_id,
                    'tp_levels': [str(tp) for tp in tp_levels] if tp_levels else [],
                    'sl_percentage': str(sl_percentage) if sl_percentage else None,
                    'position_size': str(position_size),
                    'entry_price': str(entry_price)
                }
                
        except Exception as e:
            system_logger.error(f"TP/SL setting failed: {e}")
            # Fall back to simulated
            try:
                success = await self.simulated_manager.add_tpsl_order(
                    symbol, side, position_size, entry_price, tp_levels, sl_percentage, trade_id, callback
                )
                return {
                    'success': success,
                    'method': 'simulated',
                    'trade_id': trade_id,
                    'tp_levels': [str(tp) for tp in tp_levels] if tp_levels else [],
                    'sl_percentage': str(sl_percentage) if sl_percentage else None,
                    'position_size': str(position_size),
                    'entry_price': str(entry_price),
                    'fallback_reason': str(e)
                }
            except Exception as fallback_error:
                system_logger.error(f"Simulated TP/SL also failed: {fallback_error}")
                return {
                    'success': False,
                    'method': 'failed',
                    'error': str(e),
                    'fallback_error': str(fallback_error)
                }
    
    async def _set_native_tpsl_attached(
        self,
        symbol: str,
        side: str,
        tp_levels: List[Decimal],
        sl_percentage: Decimal,
        trade_id: str,
        position_size: Decimal = None
    ) -> Dict[str, Any]:
        """Set TP/SL using native Bybit V5 API - attach to position, not separate orders."""
        try:
            # Ensure client is available
            if not self._client:
                self._client = get_bybit_client()
            
            # Sync time before API call
            await self._client.sync_time()
            
            # Get current price to calculate actual TP/SL prices
            ticker_response = await self._client.get_ticker(symbol)
            if not ticker_response or 'result' not in ticker_response or 'list' not in ticker_response['result']:
                raise Exception(f"Failed to get current price for {symbol}")
            
            current_price = Decimal(str(ticker_response['result']['list'][0]['lastPrice']))
            
            system_logger.info(f"Setting TP/SL for {symbol} position using set_trading_stop API")
            
            # Calculate TP/SL prices
            primary_tp_price = None
            sl_price = None
            additional_tp_orders = []
            
            # Set primary TP/SL using set_trading_stop (first TP level + SL)
            if tp_levels and len(tp_levels) > 0:
                primary_tp_percentage = tp_levels[0]  # Use first TP level for primary
                if side == "Buy":  # Long position
                    primary_tp_price = current_price * (1 + primary_tp_percentage / 100)
                else:  # Short position
                    primary_tp_price = current_price * (1 - primary_tp_percentage / 100)
                system_logger.info(f"Calculated primary TP price: {primary_tp_price} ({primary_tp_percentage}%)")
                
                # Create additional TP orders for remaining levels
                for i, tp_percentage in enumerate(tp_levels[1:], start=2):
                    if side == "Buy":  # Long position
                        tp_price = current_price * (1 + tp_percentage / 100)
                        tp_side = "Sell"  # Close long position
                    else:  # Short position
                        tp_price = current_price * (1 - tp_percentage / 100)
                        tp_side = "Buy"   # Close short position
                    
                    # Create conditional order for additional TP
                    tp_order = {
                        "category": "linear",
                        "symbol": symbol,
                        "side": tp_side,
                        "orderType": "Market",
                        "qty": str(position_size) if position_size else "0",
                        "triggerPrice": str(tp_price),
                        "triggerBy": "MarkPrice",
                        "reduceOnly": True,
                        "closeOnTrigger": True,
                        "positionIdx": 0,
                        "orderLinkId": f"tp_{trade_id}_{i}"
                    }
                    additional_tp_orders.append(tp_order)
                    system_logger.info(f"Prepared additional TP {i}: {tp_price} ({tp_percentage}%)")
            
            # Calculate SL price
            if sl_percentage:
                if side == "Buy":  # Long position
                    sl_price = current_price * (1 - sl_percentage / 100)
                else:  # Short position
                    sl_price = current_price * (1 + sl_percentage / 100)
                system_logger.info(f"Calculated SL price: {sl_price} ({sl_percentage}%)")
            
            # Set primary TP/SL using set_trading_stop
            result = await self._client.set_trading_stop(
                category="linear",
                symbol=symbol,
                take_profit=primary_tp_price,
                stop_loss=sl_price,
                tp_order_type="Market",
                sl_order_type="Market",
                tp_trigger_by="MarkPrice",
                sl_trigger_by="MarkPrice"
            )
            
            system_logger.info(f"set_trading_stop response: {json.dumps(result, indent=2)}")
            
            # Check if primary TP/SL was successful
            if result and result.get('retCode') == 0:
                system_logger.info(f"✅ Primary TP/SL attached to position successfully: TP={primary_tp_price}, SL={sl_price}")
                
                # Place additional TP orders
                additional_tp_results = []
                if additional_tp_orders:
                    system_logger.info(f"Placing {len(additional_tp_orders)} additional TP orders")
                    for i, tp_order in enumerate(additional_tp_orders, start=2):
                        try:
                            tp_result = await self._client.place_order(tp_order)
                            if tp_result and tp_result.get('retCode') == 0:
                                system_logger.info(f"✅ Additional TP {i} placed successfully")
                                additional_tp_results.append({
                                    'tp_level': i,
                                    'success': True,
                                    'result': tp_result
                                })
                            else:
                                error_msg = tp_result.get('retMsg', 'Unknown error') if tp_result else 'No response'
                                system_logger.error(f"❌ Additional TP {i} failed: {error_msg}")
                                additional_tp_results.append({
                                    'tp_level': i,
                                    'success': False,
                                    'error': error_msg
                                })
                        except Exception as e:
                            system_logger.error(f"❌ Additional TP {i} placement error: {e}")
                            additional_tp_results.append({
                                'tp_level': i,
                                'success': False,
                                'error': str(e)
                            })
                
                return {
                    'success': True,
                    'method': 'native_api_attached_with_multiple_tps',
                    'trade_id': trade_id,
                    'tp_levels': [str(tp) for tp in tp_levels] if tp_levels else [],
                    'sl_percentage': str(sl_percentage) if sl_percentage else None,
                    'position_size': str(position_size),
                    'entry_price': str(current_price),
                    'primary_tp_price': str(primary_tp_price) if primary_tp_price else None,
                    'sl_price': str(sl_price) if sl_price else None,
                    'additional_tp_results': additional_tp_results,
                    'total_tp_levels': len(tp_levels) if tp_levels else 0,
                    'result': result
                }
            else:
                system_logger.error(f"❌ Failed to attach TP/SL to position: {result}")
                return {
                    'success': False,
                    'method': 'native_api_attached',
                    'trade_id': trade_id,
                    'error': result.get('retMsg', 'Unknown error'),
                    'result': result
                }
            
        except Exception as e:
            system_logger.error(f"Native TP/SL attachment failed: {e}")
            raise

# Global instance
_intelligent_tpsl_handler_fixed = None

def get_intelligent_tpsl_handler_fixed() -> IntelligentTPSLHandlerFixed:
    """Get global intelligent TP/SL handler instance."""
    global _intelligent_tpsl_handler_fixed
    if _intelligent_tpsl_handler_fixed is None:
        _intelligent_tpsl_handler_fixed = IntelligentTPSLHandlerFixed()
    return _intelligent_tpsl_handler_fixed

async def set_intelligent_tpsl_fixed(
    symbol: str,
    side: str,
    position_size: Decimal,
    entry_price: Decimal,
    tp_levels: List[Decimal],
    sl_percentage: Optional[Decimal],
    trade_id: str,
    callback: Callable[[Dict[str, Any]], None]
) -> Dict[str, Any]:
    """Set intelligent TP/SL using the fixed handler."""
    handler = get_intelligent_tpsl_handler_fixed()
    return await handler.set_tpsl(
        symbol, side, position_size, entry_price, tp_levels, sl_percentage, trade_id, callback
    )
