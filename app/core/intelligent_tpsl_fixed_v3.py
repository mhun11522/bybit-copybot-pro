import asyncio
import json
from decimal import Decimal
from typing import Dict, Any, List, Optional, Callable
from app.core.logging import system_logger
from app.core.environment_detector import get_environment_detector, TPSLStrategy, BybitEnvironment
from app.bybit.client import get_bybit_client


class IntelligentTPSLHandlerFixed:
    """Fixed intelligent TP/SL handler with correct V5 API implementation for multiple TP levels."""
    
    def __init__(self):
        self._client = None
        self.environment_detector = get_environment_detector()
        from app.core.simulated_tpsl import get_simulated_tpsl_manager
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
            # CRITICAL FIX: Don't fall back to simulated - return failure
            # This prevents false positive success reporting
            return {
                'success': False,
                'method': 'native_api_failed',
                'error': str(e),
                'trade_id': trade_id,
                'tp_levels': [str(tp) for tp in tp_levels] if tp_levels else [],
                'sl_percentage': str(sl_percentage) if sl_percentage else None,
                'position_size': str(position_size),
                'entry_price': str(entry_price)
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
            
            # Calculate SL price
            sl_price = None
            if sl_percentage:
                if side == "Buy":  # Long position
                    sl_price = current_price * (1 - sl_percentage / 100)
                else:  # Short position
                    sl_price = current_price * (1 + sl_percentage / 100)
                system_logger.info(f"Calculated SL price: {sl_price} ({sl_percentage}%)")
            
            # Determine correct positionIdx based on position mode
            # CRITICAL FIX: In OneWay mode (mode 0), always use positionIdx 0
            # In Hedge mode (mode 1), use positionIdx 1 for LONG, 2 for SHORT
            position_idx = 0  # Default OneWay mode
            
            try:
                # Check if account is in Hedge mode
                account_info = await self._client.get_account_info()
                if account_info and 'result' in account_info and 'list' in account_info['result']:
                    account_list = account_info['result']['list']
                    if account_list and len(account_list) > 0:
                        account = account_list[0]
                        position_mode = account.get('positionMode', '0')  # Default to OneWay
                        
                        if position_mode == '1':  # Hedge mode
                            # In Hedge mode, determine positionIdx based on position side
                            positions = await self._client.get_positions("linear", symbol)
                            if positions and 'result' in positions and 'list' in positions['result']:
                                for pos in positions['result']['list']:
                                    if pos.get('symbol') == symbol and float(pos.get('size', 0)) != 0:
                                        position_size = float(pos.get('size', 0))
                                        if position_size > 0:  # LONG position
                                            position_idx = 1
                                        else:  # SHORT position (negative size)
                                            position_idx = 2
                                        system_logger.info(f"Hedge mode: Determined positionIdx {position_idx} for {symbol} {'LONG' if position_size > 0 else 'SHORT'} position (size: {position_size})")
                                        break
                        else:
                            # OneWay mode - always use positionIdx 0
                            system_logger.info(f"OneWay mode: Using positionIdx 0 for {symbol}")
                            position_idx = 0
                            
            except Exception as e:
                system_logger.warning(f"Could not determine position mode for {symbol}: {e}, defaulting to OneWay mode (positionIdx 0)")
                position_idx = 0
            
            # CORRECT APPROACH: Use set_trading_stop for primary TP/SL, then separate orders for additional TPs
            # Bybit's set_trading_stop only supports ONE TP and ONE SL per position
            all_tp_results = []
            overall_success = True
            
            # Set primary TP/SL using set_trading_stop (first TP level + SL)
            if tp_levels and len(tp_levels) > 0:
                primary_tp_percentage = tp_levels[0]
                if side == "Buy":  # Long position
                    primary_tp_price = current_price * (1 + primary_tp_percentage / 100)
                else:  # Short position
                    primary_tp_price = current_price * (1 - primary_tp_percentage / 100)
                
                system_logger.info(f"Setting primary TP/SL: TP={primary_tp_price} ({primary_tp_percentage}%), SL={sl_price}")
                
                # Check if TP/SL is already set to prevent "not modified" errors
                try:
                    positions = await self._client.get_positions("linear", symbol)
                    if positions and 'result' in positions and 'list' in positions['result']:
                        for pos in positions['result']['list']:
                            if pos.get('symbol') == symbol and float(pos.get('size', 0)) != 0:
                                existing_tp = pos.get('takeProfit')
                                existing_sl = pos.get('stopLoss')
                                
                                # Check if TP/SL is already set with same values
                                if existing_tp and existing_tp != '0' and existing_sl and existing_sl != '0':
                                    # Compare values to see if they're the same (within tolerance)
                                    existing_tp_decimal = Decimal(str(existing_tp))
                                    existing_sl_decimal = Decimal(str(existing_sl))
                                    
                                    # Check if values are close enough (within 0.1% tolerance)
                                    tp_diff = abs(existing_tp_decimal - primary_tp_price) / primary_tp_price * 100
                                    sl_diff = abs(existing_sl_decimal - sl_price) / sl_price * 100 if sl_price else 0
                                    
                                    if tp_diff < 0.1 and sl_diff < 0.1:
                                        system_logger.info(f"TP/SL already set with same values for {symbol}: TP={existing_tp}, SL={existing_sl}")
                                        # Skip setting if already configured with same values
                                        all_tp_results.append({
                                            'tp_level': 1,
                                            'tp_percentage': str(primary_tp_percentage),
                                            'tp_price': str(primary_tp_price),
                                            'success': True,
                                            'result': {'retCode': 0, 'retMsg': 'Already set with same values'},
                                            'method': 'set_trading_stop'
                                        })
                                        break
                                    else:
                                        system_logger.info(f"TP/SL values differ for {symbol}: existing TP={existing_tp} vs new TP={primary_tp_price}, existing SL={existing_sl} vs new SL={sl_price}")
                except Exception as e:
                    system_logger.warning(f"Could not check existing TP/SL: {e}")
                
                # Use set_trading_stop for primary TP/SL
                result = await self._client.set_trading_stop(
                    category="linear",
                    symbol=symbol,
                    take_profit=primary_tp_price,
                    stop_loss=sl_price,
                    tp_order_type="Market",
                    sl_order_type="Market",
                    tp_trigger_by="MarkPrice",
                    sl_trigger_by="MarkPrice",
                    position_idx=position_idx
                )
                
                system_logger.info(f"Primary TP/SL set_trading_stop response: {json.dumps(result, indent=2)}")
                
                if result and result.get('retCode') == 0:
                    system_logger.info(f"✅ Primary TP/SL attached to position successfully: TP={primary_tp_price}, SL={sl_price}")
                    all_tp_results.append({
                        'tp_level': 1,
                        'tp_percentage': str(primary_tp_percentage),
                        'tp_price': str(primary_tp_price),
                        'success': True,
                        'result': result,
                        'method': 'set_trading_stop'
                    })
                else:
                    error_msg = result.get('retMsg', 'Unknown error') if result else 'No response'
                    system_logger.error(f"❌ Primary TP/SL failed: {error_msg}")
                    all_tp_results.append({
                        'tp_level': 1,
                        'tp_percentage': str(primary_tp_percentage),
                        'tp_price': str(primary_tp_price),
                        'success': False,
                        'error': error_msg,
                        'method': 'set_trading_stop'
                    })
                    overall_success = False
                
                # Create additional TP orders for remaining levels (separate conditional orders)
                for i, tp_percentage in enumerate(tp_levels[1:], start=2):
                    try:
                        # Calculate TP price for this level
                        if side == "Buy":  # Long position
                            tp_price = current_price * (1 + tp_percentage / 100)
                            tp_side = "Sell"  # Close long position
                        else:  # Short position
                            tp_price = current_price * (1 - tp_percentage / 100)
                            tp_side = "Buy"   # Close short position
                        
                        system_logger.info(f"Setting additional TP level {i}: {tp_price} ({tp_percentage}%)")
                        
                        # Create conditional order for additional TP
                        # Determine trigger direction based on position side
                        if side == "Buy":  # Long position
                            trigger_direction = 1  # Rise (≥) for long TP
                        else:  # Short position
                            trigger_direction = 2  # Fall (≤) for short TP
                        
                        tp_order = {
                            "category": "linear",
                            "symbol": symbol,
                            "side": tp_side,
                            "orderType": "Market",
                            "qty": str(position_size) if position_size else "0",
                            "triggerPrice": str(tp_price),
                            "triggerBy": "MarkPrice",
                            "triggerDirection": trigger_direction,  # CRITICAL FIX: Add missing parameter
                            "reduceOnly": True,
                            "closeOnTrigger": True,
                            "positionIdx": position_idx,
                            "orderLinkId": f"tp_{trade_id}_{i}"
                        }
                        
                        tp_result = await self._client.place_order(tp_order)
                        system_logger.info(f"Additional TP {i} place_order response: {json.dumps(tp_result, indent=2)}")
                        
                        if tp_result and tp_result.get('retCode') == 0:
                            system_logger.info(f"✅ Additional TP {i} placed successfully: {tp_price}")
                            all_tp_results.append({
                                'tp_level': i,
                                'tp_percentage': str(tp_percentage),
                                'tp_price': str(tp_price),
                                'success': True,
                                'result': tp_result,
                                'method': 'place_order'
                            })
                        else:
                            error_msg = tp_result.get('retMsg', 'Unknown error') if tp_result else 'No response'
                            system_logger.error(f"❌ Additional TP {i} failed: {error_msg}")
                            all_tp_results.append({
                                'tp_level': i,
                                'tp_percentage': str(tp_percentage),
                                'tp_price': str(tp_price),
                                'success': False,
                                'error': error_msg,
                                'method': 'place_order'
                            })
                            overall_success = False
                            
                    except Exception as e:
                        system_logger.error(f"❌ Additional TP {i} placement error: {e}")
                        all_tp_results.append({
                            'tp_level': i,
                            'tp_percentage': str(tp_percentage),
                            'tp_price': str(tp_price) if 'tp_price' in locals() else 'Unknown',
                            'success': False,
                            'error': str(e),
                            'method': 'place_order'
                        })
                        overall_success = False
            
            # VERIFY: Check if position actually has TP/SL attached
            try:
                positions = await self._client.get_positions("linear", symbol)
                if positions and 'result' in positions and 'list' in positions['result']:
                    for pos in positions['result']['list']:
                        if pos.get('symbol') == symbol and float(pos.get('size', 0)) != 0:
                            # Check if TP/SL is actually set on the position
                            tp_set = pos.get('takeProfit') and pos.get('takeProfit') != '0'
                            sl_set = pos.get('stopLoss') and pos.get('stopLoss') != '0'
                            if tp_set or sl_set:
                                system_logger.info(f"✅ Verified TP/SL attached to position: TP={tp_set}, SL={sl_set}")
                            else:
                                system_logger.warning(f"⚠️ TP/SL API succeeded but position shows no TP/SL attached")
                            break
            except Exception as e:
                system_logger.warning(f"Could not verify TP/SL attachment: {e}")
            
            if overall_success:
                return {
                    'success': True,
                    'method': 'native_api_attached_multiple_tps',
                    'trade_id': trade_id,
                    'tp_levels': [str(tp) for tp in tp_levels] if tp_levels else [],
                    'sl_percentage': str(sl_percentage) if sl_percentage else None,
                    'position_size': str(position_size),
                    'entry_price': str(current_price),
                    'sl_price': str(sl_price) if sl_price else None,
                    'tp_results': all_tp_results,
                    'total_tp_levels': len(tp_levels) if tp_levels else 0,
                    'successful_tp_levels': len([r for r in all_tp_results if r['success']])
                }
            else:
                return {
                    'success': False,
                    'method': 'native_api_attached_multiple_tps',
                    'error': f"Some TP levels failed. {len([r for r in all_tp_results if not r['success']])} out of {len(tp_levels)} failed",
                    'trade_id': trade_id,
                    'tp_levels': [str(tp) for tp in tp_levels] if tp_levels else [],
                    'sl_percentage': str(sl_percentage) if sl_percentage else None,
                    'position_size': str(position_size),
                    'entry_price': str(current_price),
                    'sl_price': str(sl_price) if sl_price else None,
                    'tp_results': all_tp_results,
                    'total_tp_levels': len(tp_levels) if tp_levels else 0,
                    'successful_tp_levels': len([r for r in all_tp_results if r['success']])
                }
                        
        except Exception as e:
            system_logger.error(f"Error in _set_native_tpsl_attached for {symbol}: {e}")
            return {
                'success': False,
                'method': 'native_api_attached',
                'error': str(e),
                'trade_id': trade_id,
                'tp_levels': [str(tp) for tp in tp_levels] if tp_levels else [],
                'sl_percentage': str(sl_percentage) if sl_percentage else None,
                'position_size': str(position_size),
                'entry_price': str(current_price) if 'current_price' in locals() else 'Unknown'
            }


# Global instance
_intelligent_tpsl_handler = None

def get_intelligent_tpsl_handler_fixed() -> IntelligentTPSLHandlerFixed:
    """Get singleton instance of intelligent TP/SL handler."""
    global _intelligent_tpsl_handler
    if _intelligent_tpsl_handler is None:
        _intelligent_tpsl_handler = IntelligentTPSLHandlerFixed()
    return _intelligent_tpsl_handler

async def set_intelligent_tpsl_fixed(
    symbol: str,
    side: str,
    position_size: Decimal,
    entry_price: Decimal,
    tp_levels: List[Decimal],
    sl_percentage: Optional[Decimal],
    trade_id: str,
    callback: Callable[[Dict[str, Any]], None] = None
) -> Dict[str, Any]:
    """Set intelligent TP/SL using the fixed handler."""
    handler = get_intelligent_tpsl_handler_fixed()
    return await handler.set_tpsl(
        symbol, side, position_size, entry_price, tp_levels, sl_percentage, trade_id, callback
    )
