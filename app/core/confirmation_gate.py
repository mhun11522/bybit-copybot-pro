"""Bybit confirmation gate - no Telegram until Bybit OK."""

import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable, List
from decimal import Decimal
from app.core.logging import system_logger, trade_logger
from app.core.strict_config import STRICT_CONFIG
from app.core.intelligent_tpsl_fixed import set_intelligent_tpsl_fixed

async def retry_until_ok(op, *, attempts=5, delay=1.0, op_name=""):
    """Retry operation until it succeeds or max attempts reached."""
    last = None
    for i in range(1, attempts + 1):
        try:
            res = await op()
            # Accept either internal shape {success: True} or Bybit {retCode: 0}
            if isinstance(res, dict) and (res.get("success") is True or res.get("retCode") == 0):
                return res
            last = res
        except Exception as e:
            last = {"success": False, "error": str(e)}
        if i < attempts:
            await asyncio.sleep(delay)
    raise RuntimeError(f"{op_name or 'operation'} failed after {attempts} attempts: {last}")

class ConfirmationGate:
    """Gate that ensures no Telegram messages until Bybit confirms operations."""
    
    def __init__(self):
        self._pending_confirmations: Dict[str, Dict[str, Any]] = {}
        self._confirmation_callbacks: Dict[str, Callable] = {}
    
    async def wait_for_confirmation(
        self, 
        operation_id: str, 
        bybit_operation: Callable[[], Awaitable[Dict[str, Any]]],
        telegram_callback: Callable[[Dict[str, Any]], Awaitable[None]],
        timeout: float = 15.0  # Reduced timeout for Market orders
    ) -> bool:
        """
        Execute Bybit operation and wait for confirmation before sending Telegram.
        
        Args:
            operation_id: Unique identifier for this operation
            bybit_operation: Async function that performs Bybit operation
            telegram_callback: Async function to call after Bybit confirms
            timeout: Maximum time to wait for confirmation
        
        Returns:
            True if confirmed and Telegram sent, False otherwise
        """
        try:
            system_logger.info(f"Starting confirmation gate for operation: {operation_id}")
            
            # Execute Bybit operation
            bybit_result = await bybit_operation()
            
            # Check if Bybit operation was successful
            if not self._is_bybit_success(bybit_result):
                system_logger.error(f"Bybit operation failed for {operation_id}", {
                    'operation_id': operation_id,
                    'bybit_result': bybit_result
                })
                return False
            
            # Store confirmation data
            self._pending_confirmations[operation_id] = {
                'bybit_result': bybit_result,
                'telegram_callback': telegram_callback,
                'timestamp': asyncio.get_event_loop().time()
            }
            
            # Send Telegram message after Bybit confirmation
            await telegram_callback(bybit_result)
            
            # Clean up
            if operation_id in self._pending_confirmations:
                del self._pending_confirmations[operation_id]
            
            system_logger.info(f"Confirmation gate completed for operation: {operation_id}")
            return True
            
        except asyncio.TimeoutError:
            system_logger.error(f"Confirmation gate timeout for operation: {operation_id}")
            return False
        except Exception as e:
            system_logger.error(f"Confirmation gate error for operation {operation_id}: {e}", exc_info=True)
            return False
    
    def _is_bybit_success(self, bybit_result: Dict[str, Any]) -> bool:
        """Check if Bybit result indicates success."""
        if not isinstance(bybit_result, dict):
            return False
        
        ret_code = bybit_result.get('retCode', -1)
        return ret_code == 0
    
    async def place_entry_orders(
        self,
        symbol: str,
        direction: str,
        entries: List,
        qty: Decimal,
        leverage: Decimal,
        channel_name: str
    ) -> bool:
        """Place entry orders with confirmation gate."""
        from app.bybit.client import BybitClient
        from app.telegram.output import send_message
        
        operation_id = f"entry_{symbol}_{direction}_{int(asyncio.get_event_loop().time())}"
        
        async def bybit_operation():
            from app.bybit.client import get_bybit_client
            client = get_bybit_client()
            try:
                # Set leverage
                await client.set_leverage(
                    STRICT_CONFIG.supported_categories[0], 
                    symbol, 
                    int(leverage), 
                    int(leverage)
                )
                
                # Handle MARKET entries by fetching current price
                processed_entries = []
                for entry_price in entries:
                    if entry_price == "MARKET":
                        # Fetch current market price
                        ticker_response = await client.get_ticker(symbol)
                        if ticker_response and 'result' in ticker_response and 'list' in ticker_response['result'] and ticker_response['result']['list']:
                            # Extract lastPrice from the first ticker in the list
                            ticker_data = ticker_response['result']['list'][0]
                            if 'lastPrice' in ticker_data:
                                market_price = Decimal(str(ticker_data['lastPrice']))
                                processed_entries.append(market_price)
                            else:
                                system_logger.error(f"No lastPrice in ticker data for {symbol}")
                                return False
                        else:
                            system_logger.error(f"Failed to get market price for {symbol}: {ticker_response}")
                            return False
                    else:
                        # Convert to Decimal if it's not already
                        if isinstance(entry_price, Decimal):
                            processed_entries.append(entry_price)
                        else:
                            processed_entries.append(Decimal(str(entry_price)))
                
                # Place dual entry orders
                order_results = []
                
                # Get symbol metadata for minimum quantity validation
                from app.core.symbol_registry import get_symbol_registry
                from app.core.position_calculator import PositionCalculator
                registry = await get_symbol_registry()
                symbol_info = await registry.get_symbol_info(symbol)
                
                if symbol_info:
                    # Use the new position calculator for dual entry calculation
                    order_qty = PositionCalculator.calculate_dual_entry_qty(
                        total_contracts=qty,
                        symbol_info=symbol_info,
                        entries_count=len(processed_entries)
                    )
                    
                    # Final validation
                    if not symbol_info.validate_qty(order_qty):
                        system_logger.error(f"Final order_qty {order_qty} failed validation for {symbol}")
                        return {'retCode': -1, 'retMsg': f'Order quantity validation failed: {order_qty}'}
                    
                    # Log the quantity calculation details
                    system_logger.info(f"Order quantity calculation for {symbol}", {
                        'original_qty': float(qty),
                        'entries_count': len(processed_entries),
                        'order_qty': float(order_qty),
                        'min_qty': float(symbol_info.min_qty),
                        'step_size': float(symbol_info.step_size)
                    })
                else:
                    # Fallback to original logic if symbol info not available
                    order_qty = qty / len(processed_entries)
                
                for i, entry_price in enumerate(processed_entries):
                    # Convert direction to Bybit format
                    bybit_side = "Buy" if direction == "LONG" else "Sell"
                    
                    # Place order based on configuration (Market or Limit)
                    result = await self._place_order_with_retry(
                        client, symbol, bybit_side, order_qty, entry_price, f"{operation_id}_{i}"
                    )
                    order_results.append(result)
                
                # Subscribe to WebSocket updates for this symbol
                try:
                    from app.trade.websocket_handlers import get_websocket_handlers
                    handlers = await get_websocket_handlers()
                    await handlers.subscribe_to_symbol(symbol)
                except Exception as e:
                    system_logger.warning(f"Failed to subscribe to WebSocket for {symbol}: {e}")
                
                return {
                    'retCode': 0,
                    'operation': 'entry_orders',
                    'symbol': symbol,
                    'direction': direction,
                    'entries': [str(e) for e in entries],
                    'qty': str(qty),
                    'leverage': str(leverage),
                    'order_results': order_results
                }
            finally:
                await client.aclose()
        
        async def telegram_callback(bybit_result):
            # Send confirmation message only after Bybit confirms
            message = f"""
🎯 **Signal mottagen & kopierad**

📊 **Symbol:** {symbol}
📈 **Riktning:** {direction}
💰 **Storlek:** {qty}
⚡ **Hävstång:** {leverage}x
📺 **Källa:** {channel_name}
⏰ **Tid:** {asyncio.get_event_loop().time()}

✅ **Order placerad** - Väntar på fyllning
            """.strip()
            
            await send_message(message)
        
        return await self.wait_for_confirmation(
            operation_id, bybit_operation, telegram_callback
        )
    
    async def place_exit_orders(
        self,
        symbol: str,
        side: str,
        qty: Decimal,
        tps: List,
        sl,
        channel_name: str
    ) -> bool:
        """Place exit orders (TP/SL) with confirmation gate."""
        from app.bybit.client import BybitClient
        from app.telegram.output import send_message
        
        operation_id = f"exit_{symbol}_{side}_{int(asyncio.get_event_loop().time())}"
        
        async def bybit_operation():
            from app.bybit.client import get_bybit_client
            client = get_bybit_client()
            try:
                order_results = []
                tp_success = True
                sl_success = True
                
                # Handle default TP/SL by calculating based on entry price
                processed_tps = []
                processed_sl = None
                
                if tps == ["DEFAULT_TP"]:
                    # Get current market price for default TP calculation
                    ticker_response = await client.get_ticker(symbol)
                    if ticker_response and 'result' in ticker_response and 'list' in ticker_response['result'] and ticker_response['result']['list']:
                        # Extract lastPrice from the first ticker in the list
                        ticker_data = ticker_response['result']['list'][0]
                        if 'lastPrice' in ticker_data:
                            current_price = Decimal(str(ticker_data['lastPrice']))
                        # Set TP at +2% for LONG, -2% for SHORT
                        if side == "LONG":
                            default_tp = current_price * Decimal("1.02")
                        else:
                            default_tp = current_price * Decimal("0.98")
                        processed_tps = [default_tp]
                    else:
                        system_logger.error(f"Failed to get market price for default TP calculation")
                        return False
                else:
                    processed_tps = []
                    for tp in tps:
                        if isinstance(tp, Decimal):
                            processed_tps.append(tp)
                        else:
                            processed_tps.append(Decimal(str(tp)))
                
                if sl == "DEFAULT_SL":
                    # Get current market price for default SL calculation
                    ticker_response = await client.get_ticker(symbol)
                    if ticker_response and 'result' in ticker_response and 'list' in ticker_response['result'] and ticker_response['result']['list']:
                        # Extract lastPrice from the first ticker in the list
                        ticker_data = ticker_response['result']['list'][0]
                        if 'lastPrice' in ticker_data:
                            current_price = Decimal(str(ticker_data['lastPrice']))
                        # Set SL at -2% for LONG, +2% for SHORT
                        if side == "LONG":
                            processed_sl = current_price * Decimal("0.98")
                        else:
                            processed_sl = current_price * Decimal("1.02")
                    else:
                        system_logger.error(f"Failed to get market price for default SL calculation")
                        return False
                else:
                    if isinstance(sl, Decimal):
                        processed_sl = sl
                    else:
                        processed_sl = Decimal(str(sl))
                
                # Use intelligent TP/SL handler that adapts to environment
                try:
                    # Convert TP prices to percentages for intelligent handler
                    tp_percentages = []
                    if processed_tps:
                        # Get current price to calculate percentages
                        ticker_response = await client.get_ticker(symbol)
                        if ticker_response and 'result' in ticker_response and 'list' in ticker_response['result']:
                            current_price = Decimal(str(ticker_response['result']['list'][0]['lastPrice']))
                            
                            for tp_price in processed_tps:
                                # Check if TP is already a percentage (small values < 1 are likely percentages)
                                if tp_price < Decimal("1"):
                                    # Treat as percentage directly (e.g., 0.02 = 2%)
                                    tp_pct = tp_price * 100  # Convert to percentage
                                else:
                                    # Treat as absolute price and convert to percentage
                                    if side == "LONG":
                                        tp_pct = ((tp_price - current_price) / current_price) * 100
                                    else:  # SHORT
                                        tp_pct = ((current_price - tp_price) / current_price) * 100
                                tp_percentages.append(tp_pct)
                    
                    # Convert SL price to percentage
                    sl_percentage = None
                    if processed_sl:
                        # Check if SL is already a percentage (small values < 1 are likely percentages)
                        if processed_sl < Decimal("1"):
                            # Treat as percentage directly (e.g., 0.02 = 2%)
                            sl_percentage = processed_sl * 100  # Convert to percentage
                        else:
                            # Treat as absolute price and convert to percentage
                            if side == "LONG":
                                sl_percentage = ((current_price - processed_sl) / current_price) * 100
                            else:  # SHORT
                                sl_percentage = ((processed_sl - current_price) / current_price) * 100
                    
                    # Use intelligent TP/SL handler with retry
                    tpsl_result = await retry_until_ok(
                        lambda: set_intelligent_tpsl_fixed(
                            symbol=symbol,
                            side=side,
                            position_size=qty,
                            entry_price=current_price,
                            tp_levels=tp_percentages,
                            sl_percentage=sl_percentage,
                            trade_id=operation_id
                        ),
                        attempts=5, delay=1.0, op_name="set_intelligent_tpsl_fixed"
                    )
                    
                    if tpsl_result['success']:
                        system_logger.info(f"✅ Intelligent TP/SL placed successfully: {symbol}", {
                            'method': tpsl_result['method'],
                            'tp_levels': tpsl_result.get('tp_levels', []),
                            'sl_percentage': tpsl_result.get('sl_percentage')
                        })
                        tp_success = True
                        sl_success = True
                        order_results.append({"intelligent_tpsl": tpsl_result})
                    else:
                        system_logger.error(f"❌ Intelligent TP/SL failed: {tpsl_result.get('error', 'Unknown error')}")
                        tp_success = False
                        sl_success = False
                        
                except Exception as e:
                    system_logger.error(f"❌ Failed to set intelligent TP/SL: {e}")
                    if processed_tps:
                        tp_success = False
                    if processed_sl:
                        sl_success = False
                
                # Return success only if both TP and SL orders succeeded (or if only one was needed)
                overall_success = True
                if processed_tps and not tp_success:
                    overall_success = False
                    system_logger.error(f"❌ TP order failed for {symbol}")
                if processed_sl and not sl_success:
                    overall_success = False
                    system_logger.error(f"❌ SL order failed for {symbol}")
                
                return {
                    'retCode': 0 if overall_success else 1,
                    'operation': 'exit_orders',
                    'symbol': symbol,
                    'side': side,
                    'qty': str(qty),
                    'tps': [str(tp) for tp in tps],
                    'sl': str(sl),
                    'order_results': order_results,
                    'tp_success': tp_success,
                    'sl_success': sl_success,
                    'overall_success': overall_success
                }
            finally:
                await client.aclose()
        
        async def telegram_callback(bybit_result):
            # Send confirmation message only after Bybit confirms
            message = f"""
🎯 **TP/SL placerad**

📊 **Symbol:** {symbol}
📈 **Riktning:** {side}
💰 **Storlek:** {qty}
🎯 **TP:** {', '.join([str(tp) for tp in tps])}
🛑 **SL:** {sl}
📺 **Källa:** {channel_name}

✅ **TP/SL bekräftad** av Bybit
            """.strip()
            
            await send_message(message)
        
        return await self.wait_for_confirmation(
            operation_id, bybit_operation, telegram_callback
        )
    
    async def close_position(
        self,
        symbol: str,
        side: str,
        qty: Decimal,
        reason: str,
        channel_name: str
    ) -> bool:
        """Close position with confirmation gate."""
        from app.bybit.client import BybitClient
        from app.telegram.output import send_message
        
        operation_id = f"close_{symbol}_{side}_{int(asyncio.get_event_loop().time())}"
        
        async def bybit_operation():
            from app.bybit.client import get_bybit_client
            client = get_bybit_client()
            try:
                close_side = "Sell" if side == "Buy" else "Buy"
                order_body = {
                    "category": STRICT_CONFIG.supported_categories[0],
                    "symbol": symbol,
                    "side": close_side,
                    "orderType": "Market",
                    "qty": str(qty),
                    "reduceOnly": True,
                    "positionIdx": 0
                }
                
                result = await client.place_order(order_body)
                return {
                    'retCode': result.get('retCode', -1),
                    'operation': 'close_position',
                    'symbol': symbol,
                    'side': side,
                    'qty': str(qty),
                    'reason': reason,
                    'order_result': result
                }
            finally:
                await client.aclose()
        
        async def telegram_callback(bybit_result):
            # Send confirmation message only after Bybit confirms
            message = f"""
🎯 **Position stängd**

📊 **Symbol:** {symbol}
📈 **Riktning:** {side}
💰 **Storlek:** {qty}
📝 **Anledning:** {reason}
📺 **Källa:** {channel_name}

✅ **Position stängd** bekräftad av Bybit
            """.strip()
            
            await send_message(message)
        
        return await self.wait_for_confirmation(
            operation_id, bybit_operation, telegram_callback
        )
    
    async def _validate_order_parameters(self, order_body: Dict[str, Any], symbol_info) -> Dict[str, Any]:
        """Validate order parameters to prevent auto-cancellation (client recommendation)."""
        try:
            # Check if order would be auto-cancelled
            if order_body.get('timeInForce') == 'IOC':
                return {'valid': False, 'reason': 'IOC orders are auto-cancelled if not filled immediately'}
            
            if order_body.get('timeInForce') == 'FOK':
                return {'valid': False, 'reason': 'FOK orders are auto-cancelled if not filled completely'}
            
            # Check postOnly parameter
            if order_body.get('postOnly') and order_body.get('orderType') == 'Limit':
                # PostOnly orders are cancelled if they would cross the book
                # This is acceptable for limit orders, but log it
                system_logger.info("PostOnly order - will be cancelled if price crosses book")
            
            # Check reduceOnly parameter
            if order_body.get('reduceOnly') and order_body.get('orderType') == 'Market':
                return {'valid': False, 'reason': 'Market orders with reduceOnly may be cancelled'}
            
            # Validate quantity
            if symbol_info:
                qty = Decimal(str(order_body.get('qty', '0')))
                if not symbol_info.validate_qty(qty):
                    return {'valid': False, 'reason': f'Invalid quantity {qty} for symbol constraints'}
            
            # Validate price for limit orders
            if order_body.get('orderType') == 'Limit' and 'price' in order_body:
                price = Decimal(str(order_body['price']))
                if symbol_info and not symbol_info.validate_price(price):
                    return {'valid': False, 'reason': f'Invalid price {price} for symbol constraints'}
            
            return {'valid': True, 'reason': 'Order parameters are valid'}
            
        except Exception as e:
            return {'valid': False, 'reason': f'Validation error: {e}'}

    async def _place_order_with_retry(self, client, symbol: str, side: str, qty: Decimal, price: Decimal, order_link_id: str, max_retries: int = 10) -> Dict[str, Any]:
        """Place order (Market or Limit) with retry logic."""
        from decimal import Decimal, ROUND_DOWN, ROUND_UP
        from app.core.symbol_registry import get_symbol_registry
        
        for attempt in range(max_retries):
            try:
                # Get symbol info for quantity formatting
                registry = await get_symbol_registry()
                symbol_info = await registry.get_symbol_info(symbol)
                
                # Format quantity using symbol info
                if symbol_info:
                    formatted_qty = symbol_info.format_qty(qty)
                else:
                    formatted_qty = str(qty)
                
                # Build order body based on order type
                if STRICT_CONFIG.entry_order_type == "Market":
                    # Market orders don't need price
                    order_body = {
                        "category": STRICT_CONFIG.supported_categories[0],
                        "symbol": symbol,
                        "side": side,
                        "orderType": STRICT_CONFIG.entry_order_type,
                        "qty": formatted_qty,
                        "timeInForce": STRICT_CONFIG.entry_time_in_force,
                        "reduceOnly": False,
                        "positionIdx": 0,
                        "orderLinkId": order_link_id
                    }
                else:
                    # Limit orders need price - use PostOnly for maker orders
                    adjusted_price = price  # Use exact price for PostOnly
                    
                    order_body = {
                        "category": STRICT_CONFIG.supported_categories[0],
                        "symbol": symbol,
                        "side": side,
                        "orderType": STRICT_CONFIG.entry_order_type,
                        "qty": formatted_qty,
                        "price": str(adjusted_price),
                        "timeInForce": STRICT_CONFIG.entry_time_in_force,
                        "reduceOnly": False,
                        "positionIdx": 0,
                        "orderLinkId": order_link_id
                    }
                
                # Log the exact order body being sent to Bybit
                system_logger.info(f"Sending order to Bybit: {order_body}")
                
                # Apply demo environment rate limiting
                from app.core.demo_config import DemoConfig
                if DemoConfig.is_demo_environment():
                    import asyncio
                    limits = DemoConfig.get_demo_limits()
                    await asyncio.sleep(limits['min_request_interval'])
                
                result = await client.place_order(order_body)
                
                # Log the response from Bybit
                system_logger.info(f"Bybit response: {result}")
                
                # Check if order was accepted
                if result.get('retCode') == 0:
                    if STRICT_CONFIG.entry_order_type == "Market":
                        system_logger.info(f"Market order accepted: {symbol} {side} {qty}")
                    else:
                        system_logger.info(f"Limit order accepted: {symbol} {side} {qty} @ {adjusted_price}")
                    return result
                elif "PostOnly" in str(result.get('retMsg', '')) and STRICT_CONFIG.entry_time_in_force == "PostOnly":
                    # PostOnly rejected - adjust price and retry
                    system_logger.warning(f"PostOnly rejected (attempt {attempt + 1}/{max_retries}): {result.get('retMsg')}")
                    if attempt < max_retries - 1:
                        # Adjust price for better PostOnly acceptance
                        if side == "Buy":
                            price = price * Decimal("1.001")  # Move slightly above for maker order
                        else:
                            price = price * Decimal("0.999")  # Move slightly below for maker order
                        continue
                elif "Qty invalid" in str(result.get('retMsg', '')):
                    # Handle qty invalid error with demo-specific logic
                    from app.core.demo_config import DemoConfig
                    if DemoConfig.is_demo_environment():
                        error_config = DemoConfig.get_demo_error_handling()
                        if error_config['retry_on_qty_invalid'] and attempt < max_retries - 1:
                            # Reduce quantity by 50% and retry
                            qty = qty * Decimal("0.5")
                            system_logger.warning(f"Qty invalid, reducing to {qty} and retrying (attempt {attempt + 1}/{max_retries})")
                            continue
                        else:
                            # Demo environment: return immediately for qty errors
                            system_logger.error(f"Demo environment: Qty invalid error: {result.get('retMsg')}", {
                                'symbol': symbol,
                                'side': side,
                                'qty': str(qty),
                                'price': str(price),
                                'full_result': result
                            })
                            return result
                    else:
                        # Live environment: return immediately for qty errors
                        system_logger.error(f"Live environment: Qty invalid error: {result.get('retMsg')}", {
                            'symbol': symbol,
                            'side': side,
                            'qty': str(qty),
                            'price': str(price),
                            'full_result': result
                        })
                        return result
                else:
                    # Other error, return immediately
                    system_logger.error(f"Order placement failed: {result}")
                    return result
                    
            except Exception as e:
                system_logger.error(f"Order placement attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    return {'retCode': -1, 'retMsg': f'Order placement failed after {max_retries} attempts: {str(e)}'}
                continue
        
        # If we get here, all retries failed
        return {'retCode': -1, 'retMsg': f'Order rejected after {max_retries} attempts'}

    async def _place_postonly_order_with_retry(self, client, symbol: str, side: str, qty: Decimal, price: Decimal, order_link_id: str, max_retries: int = 10) -> Dict[str, Any]:
        """Place PostOnly order with retry logic until accepted."""
        from decimal import Decimal, ROUND_DOWN, ROUND_UP
        from app.core.symbol_registry import get_symbol_registry
        
        for attempt in range(max_retries):
            try:
                # Get symbol info for price adjustment
                registry = await get_symbol_registry()
                symbol_info = await registry.get_symbol_info(symbol)
                
                # Adjust price to ensure PostOnly acceptance
                # Apply demo environment specific price adjustment
                from app.core.demo_config import DemoConfig
                if DemoConfig.is_demo_environment():
                    limits = DemoConfig.get_demo_limits()
                    if side == "Buy":
                        adjusted_price = price * limits['buy_price_factor']
                    else:
                        adjusted_price = price * limits['sell_price_factor']
                else:
                    # Live environment price adjustment
                    if side == "Buy":
                        adjusted_price = price * Decimal("0.999")  # 0.1% below
                    else:
                        adjusted_price = price * Decimal("1.001")  # 0.1% above
                
                # Quantize to tick size
                if symbol_info:
                    adjusted_price = symbol_info.quantize_price(adjusted_price)
                
                # Format quantity with correct precision
                if symbol_info:
                    formatted_qty = symbol_info.format_qty(qty)
                else:
                    formatted_qty = str(qty)
                
                # Build order body based on order type
                if STRICT_CONFIG.entry_order_type == "Market":
                    # Market orders don't need price
                    order_body = {
                        "category": STRICT_CONFIG.supported_categories[0],
                        "symbol": symbol,
                        "side": side,
                        "orderType": STRICT_CONFIG.entry_order_type,
                        "qty": formatted_qty,
                        "timeInForce": STRICT_CONFIG.entry_time_in_force,
                        "reduceOnly": False,
                        "positionIdx": 0,
                        "orderLinkId": order_link_id
                    }
                else:
                    # Limit orders need price
                    order_body = {
                        "category": STRICT_CONFIG.supported_categories[0],
                        "symbol": symbol,
                        "side": side,
                        "orderType": STRICT_CONFIG.entry_order_type,
                        "qty": formatted_qty,
                        "price": str(adjusted_price),
                        "timeInForce": STRICT_CONFIG.entry_time_in_force,
                        "reduceOnly": False,
                        "positionIdx": 0,
                        "orderLinkId": order_link_id
                    }
                
                # Log the exact order body being sent to Bybit
                system_logger.info(f"Sending order to Bybit: {order_body}")
                
                # Apply demo environment rate limiting
                from app.core.demo_config import DemoConfig
                if DemoConfig.is_demo_environment():
                    import asyncio
                    limits = DemoConfig.get_demo_limits()
                    await asyncio.sleep(limits['min_request_interval'])
                
                result = await client.place_order(order_body)
                
                # Log the response from Bybit
                system_logger.info(f"Bybit response: {result}")
                
                # Check if order was accepted
                if result.get('retCode') == 0:
                    if STRICT_CONFIG.entry_order_type == "Market":
                        system_logger.info(f"Market order accepted: {symbol} {side} {qty}")
                    else:
                        system_logger.info(f"Limit order accepted: {symbol} {side} {qty} @ {adjusted_price}")
                    return result
                elif "PostOnly" in str(result.get('retMsg', '')) and STRICT_CONFIG.entry_time_in_force == "PostOnly":
                    # PostOnly rejected - adjust price and retry
                    system_logger.warning(f"PostOnly rejected (attempt {attempt + 1}/{max_retries}): {result.get('retMsg')}")
                    if attempt < max_retries - 1:
                        # Adjust price for better PostOnly acceptance
                        if side == "Buy":
                            price = price * Decimal("1.001")  # Move slightly above for maker order
                        else:
                            price = price * Decimal("0.999")  # Move slightly below for maker order
                        continue
                elif "Qty invalid" in str(result.get('retMsg', '')):
                    # Handle qty invalid error with demo-specific logic
                    from app.core.demo_config import DemoConfig
                    if DemoConfig.is_demo_environment():
                        error_config = DemoConfig.get_demo_error_handling()
                        if error_config['qty_invalid_retry'] and attempt < max_retries - 1:
                            system_logger.warning(f"Demo environment: Qty invalid error (attempt {attempt + 1}/{max_retries}): {result.get('retMsg')}")
                            # Reduce quantity using demo configuration
                            qty = qty * error_config['qty_reduction_factor']
                            # Re-format quantity with correct precision
                            if symbol_info:
                                formatted_qty = symbol_info.format_qty(qty)
                            else:
                                formatted_qty = str(qty)
                            system_logger.info(f"Demo environment: Reducing quantity to {formatted_qty} for retry")
                            continue
                        else:
                            # Final attempt failed, return error
                            system_logger.error(f"Demo environment: Final qty invalid error: {result.get('retMsg')}", {
                                'symbol': symbol,
                                'side': side,
                                'qty': str(qty),
                                'price': str(adjusted_price),
                                'full_result': result
                            })
                            return result
                    else:
                        # Live environment: return immediately for qty errors
                        system_logger.error(f"Live environment: Qty invalid error: {result.get('retMsg')}", {
                            'symbol': symbol,
                            'side': side,
                            'qty': str(qty),
                            'price': str(adjusted_price),
                            'full_result': result
                        })
                        return result
                else:
                    # Other error, return immediately
                    system_logger.error(f"Order placement failed: {result}")
                    return result
                    
            except Exception as e:
                system_logger.error(f"Order placement attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    return {'retCode': -1, 'retMsg': f'Order placement failed after {max_retries} attempts: {str(e)}'}
                continue
        
        # If we get here, all retries failed
        return {'retCode': -1, 'retMsg': f'PostOnly order rejected after {max_retries} attempts'}
    
    def get_pending_confirmations(self) -> Dict[str, Any]:
        """Get pending confirmations for monitoring."""
        return {
            'pending_count': len(self._pending_confirmations),
            'operations': list(self._pending_confirmations.keys())
        }

# Global confirmation gate instance
_gate_instance = None

def get_confirmation_gate() -> ConfirmationGate:
    """Get global confirmation gate instance."""
    global _gate_instance
    if _gate_instance is None:
        _gate_instance = ConfirmationGate()
    return _gate_instance