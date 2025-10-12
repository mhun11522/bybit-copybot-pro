"""Bybit confirmation gate - no Telegram until Bybit OK (CLIENT SPEC compliance)."""

import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable, List
from decimal import Decimal
from app.core.logging import system_logger, trade_logger
from app.core.strict_config import STRICT_CONFIG
from app.core.intelligent_tpsl_fixed_v3 import set_intelligent_tpsl_fixed

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
    """
    Gate that ensures no Telegram messages until Bybit confirms operations.
    
    CLIENT SPEC: All operational messages (except "Signal received & copied")
    must only be sent AFTER Bybit confirmation with real confirmed data.
    """
    
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
    
    async def _fetch_confirmed_im(self, symbol: str) -> Decimal:
        """
        Fetch confirmed IM (Initial Margin) from Bybit for a symbol.
        
        CLIENT SPEC: IM must be fetched from Bybit and confirmed, never assumed.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
        
        Returns:
            Decimal: Confirmed IM in USDT (defaults to 0 if fetch fails)
        """
        try:
            from app.bybit.client import get_bybit_client
            client = get_bybit_client()
            
            # Get position information from Bybit
            positions_response = await client.get_positions("linear", symbol)
            
            if positions_response and positions_response.get("retCode") == 0:
                positions_list = positions_response.get("result", {}).get("list", [])
                
                if positions_list:
                    # Extract IM (may appear as positionIM, positionMargin, or margin)
                    position = positions_list[0]
                    im_value = (
                        position.get("positionIM") or 
                        position.get("positionMargin") or 
                        position.get("margin") or 
                        position.get("positionValue")
                    )
                    
                    if im_value is not None:
                        im_decimal = Decimal(str(im_value))
                        system_logger.info(f"Confirmed IM for {symbol}: {im_decimal} USDT", {
                            "symbol": symbol,
                            "im": float(im_decimal)
                        })
                        return im_decimal
            
            system_logger.warning(f"Could not fetch confirmed IM for {symbol}, defaulting to 0", {
                "symbol": symbol,
                "response": positions_response
            })
            return Decimal("0")
            
        except Exception as e:
            system_logger.error(f"Error fetching confirmed IM for {symbol}: {e}", exc_info=True)
            return Decimal("0")
    
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
                # Don't close singleton client
                pass
        
        async def telegram_callback(bybit_result):
            """
            Send Telegram confirmation ONLY after Bybit confirms (CLIENT SPEC).
            
            Uses TemplateEngine with all required Bybit-confirmed fields.
            """
            from app.telegram.engine import render_template
            
            # Extract order ID from Bybit result
            order_results = bybit_result.get("order_results", [])
            order_id = "N/A"
            if order_results:
                # Get first order ID from results
                first_result = order_results[0]
                if isinstance(first_result, dict):
                    order_id = first_result.get("result", {}).get("orderId", "N/A")
            
            # Fetch confirmed IM from Bybit (CLIENT SPEC requirement)
            im_confirmed = await self._fetch_confirmed_im(symbol)
            
            # Prepare data for template with all CLIENT SPEC required fields
            template_data = {
                "symbol": symbol,
                "side": direction,
                "direction": direction,
                "qty": qty,
                "size": qty,
                "leverage": leverage,
                "source_name": channel_name,
                "channel_name": channel_name,
                "order_id": order_id,
                "post_only": (STRICT_CONFIG.entry_time_in_force == "PostOnly"),
                "reduce_only": False,  # Entry orders are never reduce-only
                "im_confirmed": im_confirmed,
            }
            
            # Render template using TemplateEngine
            rendered = render_template("ORDER_PLACED", template_data)
            
            # Send message with full metadata for logging
            await send_message(
                rendered["text"],
                template_name=rendered["template_name"],
                trade_id=rendered["trade_id"],
                symbol=rendered["symbol"],
                hashtags=rendered["hashtags"]
            )
        
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
                                # CRITICAL FIX: Smart detection of percentage vs absolute price
                                # For low-priced assets, small values are likely percentages
                                tp_pct = None
                                
                                # Smart detection logic:
                                if current_price < Decimal("1.0") and tp_price <= Decimal("10.0"):
                                    # Low-priced asset (< $1) with small TP value (≤ $10) = likely percentage
                                    tp_pct = tp_price  # Use as percentage directly
                                    system_logger.info(f"Smart detection: TP {tp_price} treated as {tp_pct}% for low-priced asset {symbol} (current: {current_price})")
                                elif tp_price > current_price * Decimal("2.0"):
                                    # TP value is more than 2x current price = likely absolute price
                                    if side == "LONG":
                                        tp_pct = ((tp_price - current_price) / current_price) * 100
                                    else:  # SHORT
                                        tp_pct = ((current_price - tp_price) / current_price) * 100
                                    system_logger.info(f"Smart detection: TP {tp_price} treated as absolute price = {tp_pct}% for {symbol}")
                                else:
                                    # Ambiguous case - try both interpretations and pick the reasonable one
                                    # Try as percentage first
                                    tp_pct_as_percentage = tp_price
                                    # Try as absolute price
                                    if side == "LONG":
                                        tp_pct_as_absolute = ((tp_price - current_price) / current_price) * 100
                                    else:  # SHORT
                                        tp_pct_as_absolute = ((current_price - tp_price) / current_price) * 100
                                    
                                    # Choose the more reasonable interpretation (between 0.1% and 50%)
                                    if 0.1 <= abs(tp_pct_as_percentage) <= 50:
                                        tp_pct = tp_pct_as_percentage
                                        system_logger.info(f"Smart detection: TP {tp_price} treated as percentage {tp_pct}% (more reasonable)")
                                    elif 0.1 <= abs(tp_pct_as_absolute) <= 50:
                                        tp_pct = tp_pct_as_absolute
                                        system_logger.info(f"Smart detection: TP {tp_price} treated as absolute price = {tp_pct}% (more reasonable)")
                                    else:
                                        # Both interpretations are unreasonable, skip
                                        system_logger.warning(f"⚠️ TP {tp_price} has unreasonable interpretations: {tp_pct_as_percentage}% or {tp_pct_as_absolute}% for {symbol}")
                                        continue
                                
                                # Final validation: Reject negative or unrealistic TP percentages
                                if tp_pct is None or tp_pct < 0:
                                    system_logger.error(f"❌ Rejecting negative TP percentage {tp_pct}% for {symbol} (TP: {tp_price}, Current: {current_price})")
                                    continue  # Skip this TP level
                                
                                # Validate percentage is reasonable (0.1% to 100%)
                                if abs(tp_pct) < 0.1 or abs(tp_pct) > 100:
                                    system_logger.warning(f"⚠️ TP percentage {tp_pct}% seems unrealistic for {symbol} (TP: {tp_price}, Current: {current_price})")
                                    continue  # Skip this TP level
                                
                                tp_percentages.append(tp_pct)
                    
                    # Convert SL price to percentage
                    sl_percentage = None
                    if processed_sl:
                        # CRITICAL FIX: Always treat as absolute price
                        # The signal parser extracts absolute prices, not percentages
                        if side == "LONG":
                            sl_percentage = ((current_price - processed_sl) / current_price) * 100
                        else:  # SHORT
                            sl_percentage = ((processed_sl - current_price) / current_price) * 100
                        
                        # Log SL calculation for debugging
                        system_logger.info(f"SL calculation for {symbol}: SL={processed_sl}, Current={current_price}, Side={side}, Percentage={sl_percentage}%")
                        
                        # Validate percentage is reasonable (1% to 50% for normal SL)
                        if abs(sl_percentage) > 50:
                            system_logger.warning(f"⚠️ SL percentage {sl_percentage}% seems high for {symbol} (SL: {processed_sl}, Current: {current_price})")
                            # Don't reject, just warn - might be intentional for high-risk trades
                    
                    # Use intelligent TP/SL handler with retry
                    tpsl_result = await retry_until_ok(
                        lambda: set_intelligent_tpsl_fixed(
                            symbol=symbol,
                            side=side,
                            position_size=qty,
                            entry_price=current_price,
                            tp_levels=tp_percentages,
                            sl_percentage=sl_percentage,
                            trade_id=operation_id,
                            callback=lambda x: None  # Dummy callback for compatibility
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
                # Don't close singleton client
                pass
        
        async def telegram_callback(bybit_result):
            """
            Send TP/SL confirmation ONLY after Bybit confirms (CLIENT SPEC).
            
            Note: TP/SL confirmations use simpler formatting since they're
            post-position placement updates.
            """
            # Extract actual TP/SL values from Bybit result
            actual_tps = []
            actual_sl = "N/A"
            
            if bybit_result and 'order_results' in bybit_result:
                for result in bybit_result['order_results']:
                    if 'intelligent_tpsl' in result:
                        tpsl_data = result['intelligent_tpsl']
                        if 'tp_levels' in tpsl_data:
                            actual_tps = [f"{tp}%" for tp in tpsl_data['tp_levels']]
                        if 'sl_percentage' in tpsl_data:
                            actual_sl = f"{tpsl_data['sl_percentage']}%"
            
            # Fallback to original values if no actual values found
            if not actual_tps:
                actual_tps = [str(tp) for tp in tps]
            if actual_sl == "N/A" and sl:
                actual_sl = str(sl)
            
            # CLIENT SPEC: Simple TP/SL confirmation with bold labels
            message = f"""**✅ TP/SL bekräftad av Bybit**

📊 **Symbol:** {symbol}
📈 **Riktning:** {side}
💰 **Storlek:** {qty}
🎯 **TP:** {', '.join(actual_tps)}
🛑 **SL:** {actual_sl}
📺 **Källa:** {channel_name}"""
            
            await send_message(message, template_name="tp_sl_confirmed", symbol=symbol)
        
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
                # Don't close singleton client
                pass
        
        async def telegram_callback(bybit_result):
            """
            Send position closed confirmation ONLY after Bybit confirms (CLIENT SPEC).
            """
            # CLIENT SPEC: Position closed with bold labels
            message = f"""**✅ Position stängd**

📊 **Symbol:** {symbol}
📈 **Riktning:** {side}
💰 **Storlek:** {qty}
📝 **Anledning:** {reason}
📺 **Källa:** {channel_name}

⚠️ **Bekräftat i Bybit**"""
            
            await send_message(message, template_name="position_closed", symbol=symbol)
        
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
        
        postonly_failures = 0  # Track PostOnly failures for fallback
        
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
                
                # Use PostOnly for precise waiting limit orders (CLIENT REQUIREMENT)
                time_in_force = STRICT_CONFIG.entry_time_in_force
                
                # Build order body based on order type
                if STRICT_CONFIG.entry_order_type == "Market":
                    # Market orders don't need price
                    order_body = {
                        "category": STRICT_CONFIG.supported_categories[0],
                        "symbol": symbol,
                        "side": side,
                        "orderType": STRICT_CONFIG.entry_order_type,
                        "qty": formatted_qty,
                        "timeInForce": time_in_force,
                        "reduceOnly": False,
                        "positionIdx": 0,
                        "orderLinkId": order_link_id
                    }
                else:
                    # Limit orders need price - use exact signal price for PostOnly orders
                    # PostOnly ensures order waits in book until exact price is reached
                    adjusted_price = price
                    
                    order_body = {
                        "category": STRICT_CONFIG.supported_categories[0],
                        "symbol": symbol,
                        "side": side,
                        "orderType": STRICT_CONFIG.entry_order_type,
                        "qty": formatted_qty,
                        "price": str(adjusted_price),
                        "timeInForce": time_in_force,
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
                    # PostOnly rejected - implement smart price adjustment
                    postonly_failures += 1
                    system_logger.warning(f"PostOnly rejected (attempt {attempt + 1}/{max_retries}, failures: {postonly_failures}): {result.get('retMsg')}")
                    if attempt < max_retries - 1:
                        try:
                            # Get current market price and instrument info for smart adjustment
                            ticker_response = await client.get_ticker(symbol)
                            instrument_response = await client.get_instrument_info(symbol)
                            
                            if ticker_response and ticker_response.get('retCode') == 0 and 'list' in ticker_response['result']:
                                current_price = Decimal(ticker_response['result']['list'][0]['lastPrice'])
                                
                                # Get tick size for proper price adjustment
                                tick_size = Decimal("0.0001")  # Default tick size
                                if instrument_response and instrument_response.get('retCode') == 0:
                                    instrument_list = instrument_response.get('result', {}).get('list', [])
                                    if instrument_list:
                                        filters = instrument_list[0].get('lotSizeFilter', {})
                                        tick_size = Decimal(str(filters.get('tickSize', '0.0001')))
                                
                                # Calculate smart price adjustment
                                if side == "Buy":
                                    # For Buy orders, move price very close to market to ensure fill
                                    # Use 0.01% above market + tick size buffer
                                    price = current_price * Decimal("1.0001")  # Move 0.01% above market
                                    # Round to tick size
                                    price = (price / tick_size).quantize(Decimal('1')) * tick_size
                                else:
                                    # For Sell orders, move price very close to market to ensure fill
                                    # Use 0.01% below market + tick size buffer
                                    price = current_price * Decimal("0.9999")  # Move 0.01% below market
                                    # Round to tick size
                                    price = (price / tick_size).quantize(Decimal('1')) * tick_size
                                
                                system_logger.info(f"Smart adjustment: {side} price from {current_price} to {price} (tick_size: {tick_size})")
                            else:
                                # Fallback to larger adjustment if ticker fails
                                if side == "Buy":
                                    price = price * Decimal("1.001")  # Move 0.1% above
                                else:
                                    price = price * Decimal("0.999")  # Move 0.1% below
                                system_logger.info(f"Fallback: Adjusted {side} price to {price} for PostOnly acceptance")
                        except Exception as e:
                            system_logger.warning(f"Failed to get ticker/instrument for PostOnly adjustment: {e}")
                            # Fallback to larger adjustment
                            if side == "Buy":
                                price = price * Decimal("1.001")  # Move 0.1% above
                            else:
                                price = price * Decimal("0.999")  # Move 0.1% below
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
                    # PostOnly rejected - implement smart price adjustment
                    postonly_failures += 1
                    system_logger.warning(f"PostOnly rejected (attempt {attempt + 1}/{max_retries}, failures: {postonly_failures}): {result.get('retMsg')}")
                    if attempt < max_retries - 1:
                        try:
                            # Get current market price and instrument info for smart adjustment
                            ticker_response = await client.get_ticker(symbol)
                            instrument_response = await client.get_instrument_info(symbol)
                            
                            if ticker_response and ticker_response.get('retCode') == 0 and 'list' in ticker_response['result']:
                                current_price = Decimal(ticker_response['result']['list'][0]['lastPrice'])
                                
                                # Get tick size for proper price adjustment
                                tick_size = Decimal("0.0001")  # Default tick size
                                if instrument_response and instrument_response.get('retCode') == 0:
                                    instrument_list = instrument_response.get('result', {}).get('list', [])
                                    if instrument_list:
                                        filters = instrument_list[0].get('lotSizeFilter', {})
                                        tick_size = Decimal(str(filters.get('tickSize', '0.0001')))
                                
                                # Calculate smart price adjustment
                                if side == "Buy":
                                    # For Buy orders, move price very close to market to ensure fill
                                    # Use 0.01% above market + tick size buffer
                                    price = current_price * Decimal("1.0001")  # Move 0.01% above market
                                    # Round to tick size
                                    price = (price / tick_size).quantize(Decimal('1')) * tick_size
                                else:
                                    # For Sell orders, move price very close to market to ensure fill
                                    # Use 0.01% below market + tick size buffer
                                    price = current_price * Decimal("0.9999")  # Move 0.01% below market
                                    # Round to tick size
                                    price = (price / tick_size).quantize(Decimal('1')) * tick_size
                                
                                system_logger.info(f"Smart adjustment: {side} price from {current_price} to {price} (tick_size: {tick_size})")
                            else:
                                # Fallback to larger adjustment if ticker fails
                                if side == "Buy":
                                    price = price * Decimal("1.001")  # Move 0.1% above
                                else:
                                    price = price * Decimal("0.999")  # Move 0.1% below
                                system_logger.info(f"Fallback: Adjusted {side} price to {price} for PostOnly acceptance")
                        except Exception as e:
                            system_logger.warning(f"Failed to get ticker/instrument for PostOnly adjustment: {e}")
                            # Fallback to larger adjustment
                            if side == "Buy":
                                price = price * Decimal("1.001")  # Move 0.1% above
                            else:
                                price = price * Decimal("0.999")  # Move 0.1% below
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