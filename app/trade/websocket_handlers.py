"""
WebSocket handlers for real-time trade execution and position management.
Integrates with the strict FSM and confirmation gate.
"""

import asyncio
from decimal import Decimal
from typing import Dict, Any
from app.core.logging import system_logger
from app.telegram.output import send_message
from app.telegram.swedish_templates_v2 import SwedishTemplatesV2

class WebSocketTradeHandlers:
    """Handlers for WebSocket trade events."""
    
    def __init__(self):
        self.templates = SwedishTemplatesV2()
        self.active_trades: Dict[str, Dict[str, Any]] = {}
    
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
        """Handle entry order fill."""
        try:
            # Update trade state to ENTRY_FILLED
            from app.core.strict_fsm import get_fsm
            fsm = await get_fsm()
            
            # Find the trade by symbol and update state
            trade_id = f"{symbol}_{side}_{int(asyncio.get_event_loop().time())}"
            
            # Update FSM state
            await fsm.handle_entry_filled(trade_id, price, qty)
            
            # Send confirmation message
            direction_text = "LONG" if side == "Buy" else "SHORT"
            message = f"""
🎯 **Entry Order Fylld**

📊 **Symbol:** {symbol}
📈 **Riktning:** {direction_text}
💰 **Kvantitet:** {qty}
💵 **Pris:** {price}
🆔 **Order ID:** {order_id}

✅ **Position öppnad framgångsrikt**
            """.strip()
            
            await send_message(message)
            
            system_logger.info(f"Entry filled: {symbol} {side} {qty}@{price}")
            
        except Exception as e:
            system_logger.error(f"Error handling entry fill: {e}", exc_info=True)
    
    async def _handle_exit_fill(self, symbol: str, side: str, qty: Decimal, price: Decimal, order_id: str):
        """Handle exit order fill (TP/SL)."""
        try:
            # Update trade state to CLOSED
            from app.core.strict_fsm import get_fsm
            fsm = await get_fsm()
            
            trade_id = f"{symbol}_{side}_{int(asyncio.get_event_loop().time())}"
            
            # Update FSM state
            await fsm.handle_trade_closed(trade_id, price, qty)
            
            # Send confirmation message
            direction_text = "LONG" if side == "Buy" else "SHORT"
            message = f"""
🎯 **Exit Order Fylld**

📊 **Symbol:** {symbol}
📈 **Riktning:** {direction_text}
💰 **Kvantitet:** {qty}
💵 **Pris:** {price}
🆔 **Order ID:** {order_id}

✅ **Position stängd framgångsrikt**
            """.strip()
            
            await send_message(message)
            
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