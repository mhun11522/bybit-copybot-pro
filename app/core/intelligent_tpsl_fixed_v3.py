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
            
            # Force environment detection based on endpoint BEFORE analysis
            endpoint_str = str(self._client.http.base_url)
            if "api-demo.bybit.com" in endpoint_str:
                self.environment_detector.environment = BybitEnvironment.DEMO
                self.environment_detector.tpsl_strategy = TPSLStrategy.SIMULATED
                system_logger.info(f"Forced demo environment and simulated TP/SL")
            elif "api-testnet.bybit.com" in endpoint_str:
                self.environment_detector.environment = BybitEnvironment.TESTNET
                self.environment_detector.tpsl_strategy = TPSLStrategy.NATIVE_API
                system_logger.info(f"Forced testnet environment and native TP/SL API")
            elif "api.bybit.com" in endpoint_str:
                self.environment_detector.environment = BybitEnvironment.LIVE
                self.environment_detector.tpsl_strategy = TPSLStrategy.NATIVE_API
                system_logger.info(f"Forced live environment and native TP/SL API")
            else:
                # Unknown endpoint - run analysis
                await self.environment_detector.detect_environment()
            
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

    def _calculate_tp_portions(self, num_tp_levels: int) -> List[Decimal]:
        """
        Calculate what portion of position to close at each TP level.
        
        CRITICAL FIX: Ensures TPs close portions, not entire position!
        
        Strategy: Equal distribution
        - 1 TP: [1.0] = 100%
        - 2 TPs: [0.5, 0.5] = 50% each
        - 3 TPs: [0.33, 0.33, 0.34] = ~33% each
        - 4 TPs: [0.25, 0.25, 0.25, 0.25] = 25% each
        
        Args:
            num_tp_levels: Number of TP levels
            
        Returns:
            List of Decimal portions that sum to 1.0
        """
        if num_tp_levels == 1:
            return [Decimal("1.0")]
        
        if num_tp_levels == 2:
            return [Decimal("0.5"), Decimal("0.5")]
        
        if num_tp_levels == 3:
            return [Decimal("0.33"), Decimal("0.33"), Decimal("0.34")]
        
        if num_tp_levels == 4:
            return [Decimal("0.25"), Decimal("0.25"), Decimal("0.25"), Decimal("0.25")]
        
        if num_tp_levels == 5:
            return [Decimal("0.20"), Decimal("0.20"), Decimal("0.20"), Decimal("0.20"), Decimal("0.20")]
        
        if num_tp_levels == 6:
            return [Decimal("0.167"), Decimal("0.167"), Decimal("0.166"), 
                    Decimal("0.167"), Decimal("0.167"), Decimal("0.166")]
        
        # Fallback: equal distribution
        base_portion = Decimal("1.0") / Decimal(str(num_tp_levels))
        portions = [base_portion] * num_tp_levels
        
        # Ensure they sum to exactly 1.0
        total = sum(portions)
        if total != Decimal("1.0"):
            portions[-1] += Decimal("1.0") - total
        
        return portions
    
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
            
            # CRITICAL FIX: Calculate TP portions for partial position closes
            # This ensures each TP closes only a portion, not the entire position
            tp_portions = self._calculate_tp_portions(len(tp_levels)) if tp_levels else []
            
            system_logger.info(f"TP portions calculated for {len(tp_levels)} levels: {[str(p) for p in tp_portions]}")
            
            # APPROACH: Place ALL TPs as conditional orders (not using set_trading_stop for TP)
            # Bybit's set_trading_stop doesn't support partial TP closes
            # We'll use set_trading_stop ONLY for SL
            all_tp_results = []
            overall_success = True
            
            # Set ONLY SL using set_trading_stop (no TP here since it doesn't support partial closes)
            if sl_price:
                system_logger.info(f"Setting SL only: SL={sl_price}")
                
                # CRITICAL FIX: Use set_trading_stop for SL ONLY (not TP)
                # Bybit's set_trading_stop doesn't support partial TP closes
                result = await self._client.set_trading_stop(
                    category="linear",
                    symbol=symbol,
                    stop_loss=sl_price,  # Only SL, no TP!
                    sl_order_type="Market",
                    sl_trigger_by="MarkPrice",
                    position_idx=position_idx
                )
                
                system_logger.info(f"SL set_trading_stop response: {json.dumps(result, indent=2)}")
                
                if result and result.get('retCode') != 0:
                    error_msg = result.get('retMsg', 'Unknown error')
                    system_logger.error(f"❌ SL setting failed: {error_msg}")
                    overall_success = False
                else:
                    system_logger.info(f"✅ SL attached to position: SL={sl_price}")
            
            # Place ALL TP orders as conditional orders with PARTIAL quantities
            if tp_levels and position_size:
                for i, tp_percentage in enumerate(tp_levels, start=1):
                    try:
                        # Calculate TP price for this level
                        if side == "Buy":  # Long position
                            tp_price = current_price * (1 + tp_percentage / 100)
                            tp_side = "Sell"  # Close long position
                        else:  # Short position
                            tp_price = current_price * (1 - tp_percentage / 100)
                            tp_side = "Buy"   # Close short position
                        
                        system_logger.info(f"Setting additional TP level {i}: {tp_price} ({tp_percentage}%)")
                        
                        # CRITICAL FIX: Calculate PARTIAL quantity for this TP level
                        tp_portion = tp_portions[i-1]  # Get portion for this level
                        tp_qty = position_size * tp_portion
                        
                        system_logger.info(f"TP{i} will close {float(tp_portion)*100:.1f}% of position ({tp_qty} contracts)")
                        
                        # Create conditional order for this TP level
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
                            "qty": str(tp_qty),  # ✅ PARTIAL quantity, not full position!
                            "triggerPrice": str(tp_price),
                            "triggerBy": "MarkPrice",
                            "triggerDirection": trigger_direction,
                            "reduceOnly": True,
                            "closeOnTrigger": False,  # ✅ CRITICAL: False for partial close!
                            "positionIdx": position_idx,
                            "orderLinkId": f"tp_{trade_id}_{i}"
                        }
                        
                        tp_result = await self._client.place_order(tp_order)
                        system_logger.info(f"TP{i} place_order response: {json.dumps(tp_result, indent=2)}")
                        
                        if tp_result and tp_result.get('retCode') == 0:
                            system_logger.info(f"✅ TP{i} placed successfully: {tp_price} ({float(tp_portion)*100:.1f}% of position = {tp_qty} contracts)")
                            all_tp_results.append({
                                'tp_level': i,
                                'tp_percentage': str(tp_percentage),
                                'tp_price': str(tp_price),
                                'tp_qty': str(tp_qty),
                                'tp_portion': str(tp_portion),
                                'success': True,
                                'result': tp_result,
                                'method': 'conditional_order_partial'
                            })
                        else:
                            error_msg = tp_result.get('retMsg', 'Unknown error') if tp_result else 'No response'
                            system_logger.error(f"❌ TP{i} failed: {error_msg}")
                            all_tp_results.append({
                                'tp_level': i,
                                'tp_percentage': str(tp_percentage),
                                'tp_price': str(tp_price),
                                'tp_qty': str(tp_qty),
                                'tp_portion': str(tp_portion),
                                'success': False,
                                'error': error_msg,
                                'method': 'conditional_order_partial'
                            })
                            overall_success = False
                            
                    except Exception as e:
                        system_logger.error(f"❌ TP{i} placement error: {e}")
                        all_tp_results.append({
                            'tp_level': i,
                            'tp_percentage': str(tp_percentage),
                            'tp_price': str(tp_price) if 'tp_price' in locals() else 'Unknown',
                            'tp_qty': str(tp_qty) if 'tp_qty' in locals() else 'Unknown',
                            'tp_portion': str(tp_portion) if 'tp_portion' in locals() else 'Unknown',
                            'success': False,
                            'error': str(e),
                            'method': 'conditional_order_partial'
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
