"""
WebSocket handlers for real-time trade execution and position management.
Integrates with the strict FSM and confirmation gate.
"""

import asyncio
from decimal import Decimal
from typing import Dict, Any
from app.core.logging import system_logger
from app.telegram.output import send_message
# CLIENT FIX: Removed unused swedish_templates_v2 import

class WebSocketTradeHandlers:
    """Handlers for WebSocket trade events."""
    
    def __init__(self):
        # CLIENT FIX: Removed unused self.templates
        self.active_trades: Dict[str, Dict[str, Any]] = {}
        # CRITICAL FIX (ERROR #3): Track entry fills for consolidated message
        self._entry_fills: Dict[str, bool] = {}  # {symbol_E1: True/False, symbol_E2: True/False}
        self._entry_data: Dict[str, Dict[str, Any]] = {}  # {symbol_E1: {price, qty, im, ts}, ...}
    
    async def handle_execution(self, execution_data: Dict[str, Any]):
        """Handle order execution updates from WebSocket."""
        try:
            symbol = execution_data.get("symbol", "")
            exec_type = execution_data.get("execType", "")
            order_status = execution_data.get("orderStatus", "")
            side = execution_data.get("side", "")
            qty = execution_data.get("execQty", "0")
            price = execution_data.get("execPrice", "0")
            order_id = execution_data.get("orderId", "")
            
            system_logger.info(f"WebSocket execution: {symbol} {exec_type} {order_status} {side} {qty}@{price}")
            
            # Only process actual trade executions
            if exec_type == "Trade" and order_status == "Filled":
                await self._process_filled_order(symbol, side, qty, price, order_id)
            
        except Exception as e:
            system_logger.error(f"WebSocket execution handler error: {e}", exc_info=True)
    
    async def handle_position(self, position_data: Dict[str, Any]):
        """Handle position updates from WebSocket."""
        try:
            symbol = position_data.get("symbol", "")
            size = position_data.get("size", "0")
            side = position_data.get("side", "")
            unrealized_pnl = position_data.get("unrealisedPnl", "0")
            
            system_logger.info(f"WebSocket position: {symbol} {side} {size} PnL: {unrealized_pnl}")
            
            # Update active trades with real-time position data
            if symbol in self.active_trades:
                self.active_trades[symbol].update({
                    "current_size": Decimal(str(size)),
                    "current_side": side,
                    "unrealized_pnl": Decimal(str(unrealized_pnl))
                })
            
        except Exception as e:
            system_logger.error(f"WebSocket position handler error: {e}", exc_info=True)
    
    async def _process_filled_order(self, symbol: str, side: str, qty: str, price: str, order_id: str):
        """Process a filled order and update trade state."""
        try:
            # Convert to Decimal for precision
            qty_decimal = Decimal(str(qty))
            price_decimal = Decimal(str(price))
            
            # Determine if this is an entry or exit
            is_entry = self._is_entry_order(symbol, order_id)
            
            if is_entry:
                await self._handle_entry_fill(symbol, side, qty_decimal, price_decimal, order_id)
            else:
                await self._handle_exit_fill(symbol, side, qty_decimal, price_decimal, order_id)
                
        except Exception as e:
            system_logger.error(f"Error processing filled order: {e}", exc_info=True)
    
    def _is_entry_order(self, symbol: str, order_id: str) -> bool:
        """Determine if this is an entry order based on order ID pattern."""
        # Entry orders typically have pattern: entry_{symbol}_{direction}_{timestamp}_{index}
        return "entry_" in order_id
    
    async def _handle_entry_fill(self, symbol: str, side: str, qty: Decimal, price: Decimal, order_id: str):
        """
        Handle entry order fill - CLIENT SPEC dual-limit flow.
        
        CRITICAL FIX (ERROR #3): Proper dual-limit tracking with consolidated message.
        Flow: ENTRY 1 filled → ENTRY 2 filled → ENTRY CONSOLIDATED (with VWAP)
        """
        try:
            from app.telegram.engine import render_template
            from app.core.confirmation_gate import get_confirmation_gate
            from app.bybit.client import get_bybit_client
            from datetime import datetime
            
            # Determine which entry this is (E1 or E2) from orderLinkId
            entry_no = 1
            if "-E2" in order_id or "_E2" in order_id:
                entry_no = 2
            elif "-E1" in order_id or "_E1" in order_id:
                entry_no = 1
            else:
                # Fallback: check if this symbol already has one fill
                fill_key_1 = f"{symbol}_E1"
                if self._entry_fills.get(fill_key_1, False):
                    entry_no = 2
            
            # Initialize trade tracking if needed
            if symbol not in self.active_trades:
                self.active_trades[symbol] = {
                    "trade_id": f"{symbol}_{int(asyncio.get_event_loop().time())}",
                    "side": "LONG" if side == "Buy" else "SHORT",
                    "symbol": symbol
                }
            
            trade_info = self.active_trades[symbol]
            
            # Fetch exact IM from Bybit for this symbol
            client = get_bybit_client()
            gate = get_confirmation_gate()
            im_confirmed = await gate._fetch_confirmed_im(symbol)
            
            # CRITICAL FIX: Track this entry fill
            fill_key = f"{symbol}_E{entry_no}"
            self._entry_fills[fill_key] = True
            
            # Store detailed entry data for consolidation
            self._entry_data[fill_key] = {
                'price': price,
                'qty': qty,
                'im': im_confirmed / Decimal("2"),  # IM for this specific entry (50/50 split)
                'timestamp': datetime.now(),
                'order_id': order_id
            }
            
            # Send ENTRY TAKEN message
            rendered = render_template("ENTRY_TAKEN", {
                'entry_no': entry_no,
                'source_name': trade_info.get('channel_name', 'Unknown'),
                'symbol': symbol,
                'side': trade_info.get('side', 'LONG'),
                'trade_type': trade_info.get('trade_type', 'SWING'),
                'entry': price,
                'qty': qty,
                'im': im_confirmed / Decimal("2"),  # IM for this entry
                'im_total': im_confirmed,  # Total IM across both entries
                'trade_id': trade_info['trade_id'],
                'bot_order_id': f"BOT-{trade_info['trade_id']}",
                'bybit_order_id': order_id
            })
            
            await send_message(
                rendered["text"],
                template_name=rendered["template_name"],
                trade_id=rendered["trade_id"],
                symbol=rendered["symbol"],
                hashtags=rendered["hashtags"]
            )
            
            system_logger.info(f"Entry {entry_no} filled and message sent", {
                'symbol': symbol,
                'entry_no': entry_no,
                'price': float(price),
                'qty': float(qty),
                'im': float(im_confirmed / Decimal("2"))
            })
            
            # CRITICAL FIX (ERROR #3): Check if both entries are now filled
            fill_key_1 = f"{symbol}_E1"
            fill_key_2 = f"{symbol}_E2"
            
            if self._entry_fills.get(fill_key_1, False) and self._entry_fills.get(fill_key_2, False):
                # Both entries filled - send CONSOLIDATED message
                await self._send_consolidated_entry(symbol, trade_info)
            
        except Exception as e:
            system_logger.error(f"Error handling entry fill: {e}", exc_info=True)
    
    async def _send_consolidated_entry(self, symbol: str, trade_info: Dict[str, Any]):
        """
        Send consolidated entry message with VWAP calculation.
        
        CLIENT SPEC (doc/requirement.txt Lines 325-345):
        📌 Sammanslagning av ENTRY 1 + ENTRY 2
        Must show ENTRY 1, ENTRY 2, and COMBINED POSITION with VWAP.
        """
        try:
            from app.telegram.engine import render_template
            
            # Get both entry data
            fill_key_1 = f"{symbol}_E1"
            fill_key_2 = f"{symbol}_E2"
            
            entry1 = self._entry_data.get(fill_key_1, {})
            entry2 = self._entry_data.get(fill_key_2, {})
            
            if not entry1 or not entry2:
                system_logger.error(f"Cannot send consolidated message - missing entry data for {symbol}")
                return
            
            # Calculate VWAP (Volume-Weighted Average Price)
            # CLIENT SPEC: "volymvägt mellan entry1 & entry2" (NOT simple average!)
            e1_price = entry1['price']
            e1_qty = entry1['qty']
            e2_price = entry2['price']
            e2_qty = entry2['qty']
            
            total_qty = e1_qty + e2_qty
            vwap = (e1_price * e1_qty + e2_price * e2_qty) / total_qty
            
            # Total IM is sum of both entries
            total_im = entry1['im'] + entry2['im']
            
            # Send consolidated message via Engine
            rendered = render_template("ENTRY_CONSOLIDATED", {
                'source_name': trade_info.get('channel_name', 'Unknown'),
                'symbol': symbol,
                'side': trade_info.get('side', 'LONG'),
                'trade_type': trade_info.get('trade_type', 'SWING'),
                'entry1': e1_price,
                'qty1': e1_qty,
                'im1': entry1['im'],
                'entry2': e2_price,
                'qty2': e2_qty,
                'im2': entry2['im'],
                'avg_entry': vwap,  # CRITICAL: Must be VWAP (volume-weighted)
                'qty_total': total_qty,
                'im_total': total_im,
                'trade_id': trade_info['trade_id'],
                'bot_order_id': f"BOT-{trade_info['trade_id']}",
                'bybit_order_id': entry2.get('order_id', '')  # Use latest order ID
            })
            
            await send_message(
                rendered["text"],
                template_name=rendered["template_name"],
                trade_id=rendered["trade_id"],
                symbol=rendered["symbol"],
                hashtags=rendered["hashtags"]
            )
            
            system_logger.info("Entry consolidated message sent", {
                'symbol': symbol,
                'vwap': float(vwap),
                'entry1': float(e1_price),
                'entry2': float(e2_price),
                'total_qty': float(total_qty),
                'total_im': float(total_im)
            })
            
            # Store VWAP as original_entry_price for this trade
            trade_info['original_entry_price'] = vwap
            trade_info['avg_entry'] = vwap
            trade_info['total_qty'] = total_qty
            trade_info['total_im'] = total_im
            
            # Clean up tracking data
            del self._entry_fills[fill_key_1]
            del self._entry_fills[fill_key_2]
            del self._entry_data[fill_key_1]
            del self._entry_data[fill_key_2]
            
        except Exception as e:
            system_logger.error(f"Error sending consolidated entry message: {e}", exc_info=True)
    
    async def _handle_exit_fill(self, symbol: str, side: str, qty: Decimal, price: Decimal, order_id: str):
        """
        Handle exit order fill (TP/SL) - CLIENT SPEC compliance.
        
        Uses Engine templates for all messages.
        """
        try:
            from app.telegram.engine import render_template
            from app.core.confirmation_gate import ConfirmationGate
            from app.bybit.client import get_bybit_client
            
            # Get trade info
            trade_info = self.active_trades.get(symbol, {})
            trade_id = trade_info.get('trade_id', f"{symbol}_{int(asyncio.get_event_loop().time())}")
            
            # Fetch exact IM from Bybit
            client = get_bybit_client()
            gate = ConfirmationGate(client)
            im_confirmed = await gate._fetch_confirmed_im(symbol)
            
            # Determine if this is TP or SL based on orderLinkId
            is_tp = "-TP" in order_id or "_TP" in order_id
            
            # Send appropriate message via Engine
            if is_tp:
                # Extract TP level (TP1, TP2, etc.)
                tp_level = "TP1"
                if "-TP2" in order_id or "_TP2" in order_id:
                    tp_level = "TP2"
                elif "-TP3" in order_id or "_TP3" in order_id:
                    tp_level = "TP3"
                elif "-TP4" in order_id or "_TP4" in order_id:
                    tp_level = "TP4"
                
                rendered = render_template("TP_TAKEN", {
                    'tp_level': tp_level,
                    'source_name': trade_info.get('channel_name', 'Unknown'),
                    'symbol': symbol,
                    'price': price,
                    'qty': qty,
                    'pnl_usdt': Decimal("0"),  # Would need calculation
                    'pnl_pct': Decimal("0"),   # Would need calculation
                    'trade_id': trade_id
                })
            else:
                # SL hit
                rendered = render_template("SL_HIT", {
                    'source_name': trade_info.get('channel_name', 'Unknown'),
                    'symbol': symbol,
                    'price': price,
                    'qty': qty,
                    'pnl_usdt': Decimal("0"),  # Would need calculation
                    'pnl_pct': Decimal("0"),   # Would need calculation
                    'trade_id': trade_id
                })
            
            await send_message(
                rendered["text"],
                template_name=rendered["template_name"],
                trade_id=rendered["trade_id"],
                symbol=rendered["symbol"],
                hashtags=rendered["hashtags"]
            )
            
            system_logger.info(f"Exit filled: {symbol} {side} {qty}@{price}")
            
        except Exception as e:
            system_logger.error(f"Error handling exit fill: {e}", exc_info=True)
    
    async def subscribe_to_symbol(self, symbol: str):
        """Subscribe to WebSocket updates for a specific symbol."""
        try:
            from app.bybit.websocket import get_websocket
            ws = await get_websocket()
            
            # Subscribe to execution updates
            await ws.subscribe_execution(symbol, self.handle_execution)
            
            # Subscribe to position updates
            await ws.subscribe_position(symbol, self.handle_position)
            
            system_logger.info(f"Subscribed to WebSocket updates for {symbol}")
            
        except Exception as e:
            system_logger.error(f"Error subscribing to {symbol}: {e}", exc_info=True)
    
    async def unsubscribe_from_symbol(self, symbol: str):
        """Unsubscribe from WebSocket updates for a specific symbol."""
        try:
            from app.bybit.websocket import get_websocket
            ws = await get_websocket()
            
            await ws.unsubscribe(symbol)
            
            # Remove from active trades
            self.active_trades.pop(symbol, None)
            
            system_logger.info(f"Unsubscribed from WebSocket updates for {symbol}")
            
        except Exception as e:
            system_logger.error(f"Error unsubscribing from {symbol}: {e}", exc_info=True)


# Global handlers instance
_handlers: WebSocketTradeHandlers = None

async def get_websocket_handlers() -> WebSocketTradeHandlers:
    """Get or create the global WebSocket handlers instance."""
    global _handlers
    
    if _handlers is None:
        _handlers = WebSocketTradeHandlers()
    
    return _handlers