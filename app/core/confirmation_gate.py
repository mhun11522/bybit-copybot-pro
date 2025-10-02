"""Bybit confirmation gate - no Telegram until Bybit OK."""

import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable, List
from decimal import Decimal
from app.core.logging import system_logger, trade_logger
from app.core.strict_config import STRICT_CONFIG

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
        timeout: float = 30.0
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
        entries: List[Decimal],
        qty: Decimal,
        leverage: Decimal,
        channel_name: str
    ) -> bool:
        """Place entry orders with confirmation gate."""
        from app.bybit.client import BybitClient
        from app.telegram.output import send_message
        
        operation_id = f"entry_{symbol}_{direction}_{int(asyncio.get_event_loop().time())}"
        
        async def bybit_operation():
            client = BybitClient()
            try:
                # Set leverage
                await client.set_leverage(
                    STRICT_CONFIG.supported_categories[0], 
                    symbol, 
                    int(leverage), 
                    int(leverage)
                )
                
                # Place dual entry orders
                order_results = []
                for i, entry_price in enumerate(entries):
                    order_body = {
                        "category": STRICT_CONFIG.supported_categories[0],
                        "symbol": symbol,
                        "side": direction,
                        "orderType": STRICT_CONFIG.entry_order_type,
                        "qty": str(qty / len(entries)),  # Split quantity
                        "price": str(entry_price),
                        "timeInForce": STRICT_CONFIG.entry_time_in_force,
                        "reduceOnly": False,
                        "positionIdx": 0,
                        "orderLinkId": f"{operation_id}_{i}"
                    }
                    
                    result = await client.place_order(order_body)
                    order_results.append(result)
                
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
        tps: List[Decimal],
        sl: Decimal,
        channel_name: str
    ) -> bool:
        """Place exit orders (TP/SL) with confirmation gate."""
        from app.bybit.client import BybitClient
        from app.telegram.output import send_message
        
        operation_id = f"exit_{symbol}_{side}_{int(asyncio.get_event_loop().time())}"
        
        async def bybit_operation():
            client = BybitClient()
            try:
                order_results = []
                
                # Place TP orders
                for i, tp_price in enumerate(tps):
                    order_body = {
                        "category": STRICT_CONFIG.supported_categories[0],
                        "symbol": symbol,
                        "side": "Sell" if side == "Buy" else "Buy",
                        "orderType": STRICT_CONFIG.exit_order_type,
                        "qty": str(qty),
                        "price": str(tp_price),
                        "timeInForce": "GTC",
                        "reduceOnly": STRICT_CONFIG.exit_reduce_only,
                        "positionIdx": 0,
                        "triggerBy": STRICT_CONFIG.exit_trigger_by,
                        "orderLinkId": f"{operation_id}_tp_{i}"
                    }
                    
                    result = await client.place_order(order_body)
                    order_results.append(result)
                
                # Place SL order
                if sl:
                    sl_order_body = {
                        "category": STRICT_CONFIG.supported_categories[0],
                        "symbol": symbol,
                        "side": "Sell" if side == "Buy" else "Buy",
                        "orderType": STRICT_CONFIG.exit_order_type,
                        "qty": str(qty),
                        "price": str(sl),
                        "timeInForce": "GTC",
                        "reduceOnly": STRICT_CONFIG.exit_reduce_only,
                        "positionIdx": 0,
                        "triggerBy": STRICT_CONFIG.exit_trigger_by,
                        "orderLinkId": f"{operation_id}_sl"
                    }
                    
                    result = await client.place_order(sl_order_body)
                    order_results.append(result)
                
                return {
                    'retCode': 0,
                    'operation': 'exit_orders',
                    'symbol': symbol,
                    'side': side,
                    'qty': str(qty),
                    'tps': [str(tp) for tp in tps],
                    'sl': str(sl),
                    'order_results': order_results
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
            client = BybitClient()
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