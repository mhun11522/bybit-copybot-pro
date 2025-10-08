#!/usr/bin/env python3
"""
Fixed Intelligent TP/SL Handler with correct V5 API implementation.
"""

import asyncio
from decimal import Decimal
from typing import Dict, Any, List, Optional, Callable
from app.core.logging import system_logger
from app.core.environment_detector import get_environment_detector
from app.bybit.client import get_bybit_client
from app.core.simulated_tpsl import get_simulated_tpsl_manager

class IntelligentTPSLHandlerFixed:
    """Fixed intelligent TP/SL handler with correct V5 API implementation."""
    
    def __init__(self):
        self.environment_detector = get_environment_detector()
        self.simulated_manager = get_simulated_tpsl_manager()
        self._client = None
    
    async def initialize(self):
        """Initialize the intelligent TP/SL handler."""
        self._client = get_bybit_client()
        
        # Detect environment
        environment = await self.environment_detector.detect_environment()
        capabilities = self.environment_detector.get_capabilities()
        
        system_logger.info("Intelligent TP/SL handler initialized", {
            'environment': environment.value,
            'native_tpsl_available': capabilities.get('native_tpsl_available', False)
        })
    
    async def set_tpsl(
        self,
        symbol: str,
        side: str,
        position_size: Decimal,
        entry_price: Decimal,
        tp_levels: List[Decimal],
        sl_percentage: Decimal,
        trade_id: str,
        callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Set TP/SL using the appropriate method based on environment."""
        try:
            # Detect environment capabilities
            environment = await self.environment_detector.detect_environment()
            capabilities = self.environment_detector.get_capabilities()
            
            if capabilities.get('native_tpsl_available', False):
                # Use native API
                return await self._set_native_tpsl_v5(
                    symbol, side, tp_levels, sl_percentage, trade_id
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
    
    async def _set_native_tpsl_v5(
        self,
        symbol: str,
        side: str,
        tp_levels: List[Decimal],
        sl_percentage: Decimal,
        trade_id: str
    ) -> Dict[str, Any]:
        """Set TP/SL using native Bybit V5 API with correct parameters."""
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
            
            # Get position info and wait for position to exist
            position_response = await self._client.get_positions("linear", symbol)
            if not position_response or 'result' not in position_response or 'list' not in position_response['result']:
                raise Exception(f"Failed to get position for {symbol}")
            
            positions = position_response['result']['list']
            if not positions or float(positions[0].get('size', 0)) == 0:
                raise Exception(f"No active position found for {symbol}")
            
            position_size = Decimal(str(positions[0]['size']))
            position_side = positions[0]['side']  # "Buy" for long, "Sell" for short
            
            # Get correct positionIdx based on position mode
            position_idx = await self._client.get_correct_position_idx("linear", symbol, side)
            
            results = []
            successful_orders = 0
            
            # Use Conditional Orders for TP/SL (as per client specification)
            # TP/SL must be Conditional Orders placed after entry fills
            
            # Get symbol info for proper quantity formatting
            from app.core.symbol_registry import get_symbol_registry
            registry = await get_symbol_registry()
            symbol_info = await registry.get_symbol_info(symbol)
            
            # Set multiple TP levels as separate Conditional Orders
            if tp_levels:
                # Calculate position portion for each TP (equal distribution)
                tp_portion = position_size / len(tp_levels)
                
                # Format quantity using symbol info (proper precision, not integer rounding)
                if symbol_info:
                    tp_portion_formatted = symbol_info.format_qty(tp_portion)
                else:
                    # Fallback: use position size precision (NOT integer rounding)
                    # Determine precision from position size
                    position_str = str(position_size)
                    if '.' in position_str:
                        precision = len(position_str.split('.')[1])
                        tp_portion_formatted = str(tp_portion.quantize(Decimal(10) ** -precision))
                    else:
                        tp_portion_formatted = str(tp_portion)
                
                for i, tp_percentage in enumerate(tp_levels):
                    try:
                        # Convert TP percentage to actual price
                        if position_side == "Buy":  # Long position
                            actual_tp_price = current_price * (1 + tp_percentage / 100)
                            tp_order_side = "Sell"  # Close long position
                            trigger_direction = 1  # Rise (≥) for long TP
                        else:  # Short position
                            actual_tp_price = current_price * (1 - tp_percentage / 100)
                            tp_order_side = "Buy"  # Close short position
                            trigger_direction = 2  # Fall (≤) for short TP
                        
                        # Create Conditional TP order (StopOrder)
                        tp_order = {
                            "category": "linear",
                            "symbol": symbol,
                            "side": tp_order_side,
                            "orderType": "Market",  # Market order when triggered
                            "qty": tp_portion_formatted,
                            "triggerPrice": str(actual_tp_price),
                            "triggerBy": "MarkPrice",  # Recommended for stability
                            "triggerDirection": trigger_direction,  # 1 for rise (≥), 2 for fall (≤)
                            "positionIdx": position_idx,
                            "reduceOnly": True,  # Must be reduceOnly for TP/SL
                            "closeOnTrigger": True,
                            "orderLinkId": f"tp{i+1}_{symbol}_{trade_id}_{int(asyncio.get_event_loop().time())}"
                        }
                        
                        tp_result = await self._client.place_order(tp_order)
                        if tp_result and tp_result.get('retCode') == 0:
                            successful_orders += 1
                            results.append({
                                'type': 'tp',
                                'level': i+1,
                                'price': str(actual_tp_price),
                                'percentage': str(tp_percentage),
                                'result': tp_result
                            })
                            system_logger.info(f"TP{i+1} Conditional order placed successfully: {actual_tp_price} ({tp_percentage}%)")
                        else:
                            system_logger.error(f"TP{i+1} Conditional order failed: {tp_result}")
                            
                    except Exception as e:
                        system_logger.error(f"Failed to place TP{i+1} Conditional order: {e}")
            
            # Set Stop Loss as a single Conditional Order for the entire position
            if sl_percentage:
                try:
                    # Convert SL percentage to actual price
                    if position_side == "Buy":  # Long position
                        actual_sl_price = current_price * (1 - sl_percentage / 100)
                        sl_order_side = "Sell"  # Close long position
                        sl_trigger_direction = 2  # Fall (≤) for long SL
                    else:  # Short position
                        actual_sl_price = current_price * (1 + sl_percentage / 100)
                        sl_order_side = "Buy"  # Close short position
                        sl_trigger_direction = 1  # Rise (≥) for short SL
                    
                    # Format SL quantity using symbol info (proper precision)
                    if symbol_info:
                        sl_qty_formatted = symbol_info.format_qty(position_size)
                    else:
                        # Fallback: use position size precision (NOT integer rounding)
                        position_str = str(position_size)
                        if '.' in position_str:
                            precision = len(position_str.split('.')[1])
                            sl_qty_formatted = str(position_size.quantize(Decimal(10) ** -precision))
                        else:
                            sl_qty_formatted = str(position_size)
                    
                    # Create Conditional SL order (StopOrder)
                    sl_order = {
                        "category": "linear",
                        "symbol": symbol,
                        "side": sl_order_side,
                        "orderType": "Market",  # Market order when triggered
                        "qty": sl_qty_formatted,  # Close entire position (properly formatted)
                        "triggerPrice": str(actual_sl_price),
                        "triggerBy": "MarkPrice",  # Recommended for stability
                        "triggerDirection": sl_trigger_direction,  # 2 for fall (≤), 1 for rise (≥)
                        "positionIdx": position_idx,
                        "reduceOnly": True,  # Must be reduceOnly for TP/SL
                        "closeOnTrigger": True,
                        "orderLinkId": f"sl_{symbol}_{trade_id}_{int(asyncio.get_event_loop().time())}"
                    }
                    
                    sl_result = await self._client.place_order(sl_order)
                    if sl_result and sl_result.get('retCode') == 0:
                        successful_orders += 1
                        results.append({
                            'type': 'sl',
                            'price': str(actual_sl_price),
                            'percentage': str(sl_percentage),
                            'result': sl_result
                        })
                        system_logger.info(f"SL Conditional order placed successfully: {actual_sl_price} ({sl_percentage}%)")
                    else:
                        system_logger.error(f"SL Conditional order failed: {sl_result}")
                        
                except Exception as e:
                    system_logger.error(f"Failed to place SL Conditional order: {e}")
            
            # Calculate expected orders
            expected_orders = len(tp_levels) if tp_levels else 0
            if sl_percentage:
                expected_orders += 1
            
            # Only report success if ALL expected orders were placed successfully
            all_orders_successful = (successful_orders == expected_orders and expected_orders > 0)
            
            # Log the result
            if all_orders_successful:
                system_logger.info(f"✅ ALL TP/SL orders placed successfully: {successful_orders}/{expected_orders}")
            else:
                system_logger.error(f"❌ TP/SL orders failed: {successful_orders}/{expected_orders} successful")
                for result in results:
                    if result.get('result', {}).get('retCode') != 0:
                        system_logger.error(f"❌ Failed order: {result.get('type')} - {result.get('result', {}).get('retMsg')}")
            
            return {
                'success': all_orders_successful,
                'method': 'native_api',
                'trade_id': trade_id,
                'tp_levels': [str(tp) for tp in tp_levels] if tp_levels else [],
                'sl_percentage': str(sl_percentage) if sl_percentage else None,
                'position_size': str(position_size),
                'entry_price': str(current_price),
                'results': results,
                'successful_orders': successful_orders,
                'expected_orders': expected_orders,
                'all_orders_successful': all_orders_successful
            }
            
        except Exception as e:
            system_logger.error(f"Native TP/SL failed: {e}")
            raise

# Global instance
_intelligent_tpsl_handler_fixed = None

def get_intelligent_tpsl_handler_fixed() -> IntelligentTPSLHandlerFixed:
    """Get global intelligent TP/SL handler instance."""
    global _intelligent_tpsl_handler_fixed
    if _intelligent_tpsl_handler_fixed is None:
        _intelligent_tpsl_handler_fixed = IntelligentTPSLHandlerFixed()
    return _intelligent_tpsl_handler_fixed

async def initialize_intelligent_tpsl_fixed():
    """Initialize the intelligent TP/SL system."""
    handler = get_intelligent_tpsl_handler_fixed()
    await handler.initialize()

async def set_intelligent_tpsl_fixed(
    symbol: str,
    side: str,
    position_size: Decimal,
    entry_price: Decimal,
    tp_levels: List[Decimal],
    sl_percentage: Decimal,
    trade_id: str
) -> Dict[str, Any]:
    """Set intelligent TP/SL with fixed V5 API implementation."""
    handler = get_intelligent_tpsl_handler_fixed()
    return await handler.set_tpsl(
        symbol, side, position_size, entry_price, tp_levels, sl_percentage, trade_id
    )
