import asyncio
import json
import time
import hmac
import hashlib
from typing import Callable, Dict, Optional
from app.config.settings import BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_ENDPOINT, BYBIT_RECV_WINDOW
from app.core.logging import system_logger

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    system_logger.warning("WebSocket support not available - install websockets package for real-time updates")

class BybitWebSocket:
    """
    Bybit WebSocket client for real-time order and position updates.
    Supports private channels (execution, position) with authentication.
    """
    
    def __init__(self):
        # Determine WebSocket endpoint from REST endpoint
        if "testnet" in BYBIT_ENDPOINT:
            self.ws_url = "wss://stream-testnet.bybit.com/v5/private"
        elif "demo" in BYBIT_ENDPOINT:
            self.ws_url = "wss://stream-demo.bybit.com/v5/private"
        else:
            self.ws_url = "wss://stream.bybit.com/v5/private"
        
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        self.subscriptions = set()
        
        # Event handlers: symbol -> callback(data)
        self.execution_handlers: Dict[str, Callable] = {}
        self.position_handlers: Dict[str, Callable] = {}
        
        # CLIENT SPEC: Heartbeat (30s ping, pong timeout)
        self.last_pong = time.time()
        self.ping_interval = 30  # CLIENT SPEC: 30 seconds
        self.pong_timeout = 60   # Reconnect if no pong in 60s
        
        # CLIENT SPEC: Gap detection
        from app.core.websocket_gap_detector import get_gap_detector
        self.gap_detector = get_gap_detector()
        
    def _generate_auth_signature(self) -> dict:
        """Generate authentication payload for private WebSocket (Bybit V5)
        
        Official format from: https://bybit-exchange.github.io/docs/v5/ws/connect#authentication
        """
        # Generate expires timestamp in seconds (as integer) - CORRECTED
        # Use current time + 5 seconds for expiration (more buffer)
        expires = int(time.time() + 5)
        
        # Sign the payload: signature = HMAC_SHA256("GET/realtime{expires}", secret)
        # This is the OFFICIAL format from Bybit docs for private WebSocket
        sign_str = f"GET/realtime{expires}"
        signature = str(hmac.new(
            bytes(BYBIT_API_SECRET, "utf-8"),
            bytes(sign_str, "utf-8"),
            digestmod="sha256"
        ).hexdigest())
        
        # (do not log API keys or signatures)
        
        return {
            "op": "auth",
            "args": [BYBIT_API_KEY, str(expires), signature]  # EXACTLY 3 args! Ensure expires is string
        }
    
    async def connect(self):
        """Connect to Bybit WebSocket and authenticate"""
        if not WEBSOCKETS_AVAILABLE:
            system_logger.error("WebSocket not available - install websockets package")
            return False
            
        try:
            system_logger.info(f"Connecting to Bybit WebSocket: {self.ws_url}")
            self.ws = await websockets.connect(self.ws_url, ping_interval=None)
            system_logger.info("Bybit WebSocket connected", {"ws_url": self.ws_url})
            
            # Skip authentication for demo trading (not supported)
            if "demo" in BYBIT_ENDPOINT:
                system_logger.info("Demo trading - skipping WebSocket authentication (not supported)")
                return True
            
            # Authenticate for testnet/mainnet
            auth_payload = self._generate_auth_signature()
            system_logger.debug("Sending WebSocket authentication", {"op": "auth"})
            await self.ws.send(json.dumps(auth_payload))
            system_logger.info("Authentication sent, waiting for confirmation")
            
            # Wait for auth response with timeout
            try:
                response = await asyncio.wait_for(self.ws.recv(), timeout=10.0)
                auth_response = json.loads(response)
                
                if auth_response.get("success"):
                    system_logger.info("Bybit WebSocket authenticated successfully")
                    return True
                else:
                    system_logger.error("Bybit WebSocket authentication failed", {
                        "response": auth_response,
                        "api_key_length": len(BYBIT_API_KEY)
                    })
                    return False
            except asyncio.TimeoutError:
                system_logger.error("WebSocket authentication timeout")
                return False
                
        except Exception as e:
            system_logger.error(f"Bybit WebSocket connection failed: {e}", exc_info=True)
            return False
    
    async def subscribe_execution(self, symbol: str, handler: Callable):
        """
        Subscribe to order execution updates for a symbol.
        Handler will be called with execution data when orders are filled.
        """
        self.execution_handlers[symbol] = handler
        
        if self.ws and not self.ws.closed:
            subscribe_msg = {
                "op": "subscribe",
                "args": ["execution"]
            }
            await self.ws.send(json.dumps(subscribe_msg))
            self.subscriptions.add("execution")
            system_logger.info(f"Subscribed to execution updates for {symbol}", {"symbol": symbol})
    
    async def subscribe_position(self, symbol: str, handler: Callable):
        """
        Subscribe to position updates for a symbol.
        Handler will be called when position changes.
        """
        self.position_handlers[symbol] = handler
        
        if self.ws and not self.ws.closed:
            subscribe_msg = {
                "op": "subscribe",
                "args": ["position"]
            }
            await self.ws.send(json.dumps(subscribe_msg))
            self.subscriptions.add("position")
            system_logger.info(f"Subscribed to position updates for {symbol}", {"symbol": symbol})
    
    async def unsubscribe(self, symbol: str):
        """Remove handlers for a symbol"""
        self.execution_handlers.pop(symbol, None)
        self.position_handlers.pop(symbol, None)
        system_logger.info(f"Unsubscribed from updates for {symbol}", {"symbol": symbol})
    
    async def _handle_message(self, message: dict):
        """
        Process incoming WebSocket messages with gap detection.
        
        CLIENT SPEC (doc/10_15.md Lines 86-91):
        - Check sequence numbers for gaps
        - On gap: pause → snapshot → replay → resume
        """
        # Handle pong responses
        if message.get("op") == "pong":
            self.last_pong = time.time()
            self.gap_detector.record_pong()  # CLIENT SPEC: Track heartbeat
            return
        
        # Handle subscription confirmations
        if message.get("op") == "subscribe":
            if message.get("success"):
                system_logger.info(f"Subscription confirmed: {message.get('ret_msg', 'OK')}")
            return
        
        # CLIENT SPEC: Check for sequence gaps
        topic = message.get("topic", "")
        if topic:
            gap_detected = await self.gap_detector.check_message(topic, message)
            if gap_detected:
                # Gap recovery initiated - message processing paused
                system_logger.warning(f"Gap detected on {topic}, recovery initiated")
                return
        
        # Handle execution updates (order fills)
        if topic == "execution":
            data = message.get("data", [])
            for execution in data:
                symbol = execution.get("symbol")
                exec_type = execution.get("execType")  # Trade, Funding, etc.
                order_status = execution.get("orderStatus")
                
                # Only process actual trade executions
                if exec_type == "Trade" and symbol in self.execution_handlers:
                    handler = self.execution_handlers[symbol]
                    try:
                        await handler(execution)
                    except Exception as e:
                        system_logger.error(f"Execution handler error for {symbol}: {e}")
        
        # Handle position updates
        elif topic == "position":
            data = message.get("data", [])
            for position in data:
                symbol = position.get("symbol")
                
                if symbol in self.position_handlers:
                    handler = self.position_handlers[symbol]
                    try:
                        await handler(position)
                    except Exception as e:
                        system_logger.error(f"Position handler error for {symbol}: {e}")
    
    async def _heartbeat_loop(self):
        """
        Send periodic pings to keep connection alive.
        
        CLIENT SPEC (doc/10_15.md Lines 90-91):
        - Ping every 30s
        - Reconnect on pong timeout with snapshot flow
        """
        while self.running and self.ws:
            try:
                # Check if connection is closed
                if hasattr(self.ws, 'closed') and self.ws.closed:
                    break
                
                await asyncio.sleep(self.ping_interval)
                
                # CLIENT SPEC: Send ping
                ping_msg = {"op": "ping"}
                await self.ws.send(json.dumps(ping_msg))
                self.gap_detector.record_ping()  # Track ping sent
                
                # CLIENT SPEC: Check pong timeout
                if self.gap_detector.is_pong_timeout():
                    system_logger.warning(
                        f"No pong received in {self.pong_timeout}s, reconnecting with snapshot...",
                        {"pong_timeout_seconds": self.pong_timeout}
                    )
                    # Reconnect with snapshot flow
                    await self.reconnect()
                    
            except Exception as e:
                system_logger.error(f"Heartbeat error: {e}")
                break
    
    async def _receive_loop(self):
        """Continuously receive and process messages"""
        while self.running and self.ws:
            try:
                message_str = await self.ws.recv()
                message = json.loads(message_str)
                await self._handle_message(message)
                
            except websockets.exceptions.ConnectionClosed:
                system_logger.warning("WebSocket connection closed")
                if self.running:
                    await self.reconnect()
                break
            except Exception as e:
                system_logger.error(f"WebSocket receive error: {e}", exc_info=True)
                if self.running:
                    await asyncio.sleep(1)
    
    async def reconnect(self):
        """
        Reconnect to WebSocket and restore subscriptions.
        
        CLIENT SPEC (doc/10_15.md Lines 88-91):
        - Fetch REST snapshot on reconnect
        - Restore subscriptions
        - Resume with consistent state
        """
        system_logger.info("Reconnecting to Bybit WebSocket with snapshot flow...")
        
        # CLIENT SPEC: Step 1 - Fetch snapshot before reconnecting
        snapshot = await self.gap_detector.fetch_snapshot()
        
        # Store current subscriptions
        old_execution_handlers = self.execution_handlers.copy()
        old_position_handlers = self.position_handlers.copy()
        
        # Close old connection
        if self.ws:
            try:
                await self.ws.close()
            except Exception as e:
                system_logger.warning(f"Error closing WebSocket: {e}")
        
        # Wait before reconnecting
        await asyncio.sleep(2)
        
        # CLIENT SPEC: Step 2 - Reconnect
        if await self.connect():
            # CLIENT SPEC: Step 3 - Restore subscriptions
            for symbol, handler in old_execution_handlers.items():
                await self.subscribe_execution(symbol, handler)
            
            for symbol, handler in old_position_handlers.items():
                await self.subscribe_position(symbol, handler)
            
            system_logger.info("WebSocket reconnected and subscriptions restored", {
                "snapshot_fetched": snapshot is not None,
                "execution_handlers": len(old_execution_handlers),
                "position_handlers": len(old_position_handlers)
            })
        else:
            system_logger.error("Reconnection failed")
    
    async def start(self):
        """Start WebSocket connection and message processing"""
        self.running = True
        
        if not await self.connect():
            return False
        
        # Start background tasks
        asyncio.create_task(self._heartbeat_loop())
        asyncio.create_task(self._receive_loop())
        
        return True
    
    async def stop(self):
        """Stop WebSocket connection"""
        system_logger.info("Stopping Bybit WebSocket")
        self.running = False
        
        if self.ws:
            try:
                await self.ws.close()
            except:
                pass
        
        self.execution_handlers.clear()
        self.position_handlers.clear()
        self.subscriptions.clear()
        system_logger.info("Bybit WebSocket stopped")


# Global WebSocket instance
_ws_instance: Optional[BybitWebSocket] = None

async def get_websocket() -> BybitWebSocket:
    """Get or create the global WebSocket instance"""
    global _ws_instance
    
    if _ws_instance is None:
        _ws_instance = BybitWebSocket()
        await _ws_instance.start()
    
    return _ws_instance

async def stop_websocket():
    """Stop the global WebSocket instance"""
    global _ws_instance
    
    if _ws_instance:
        await _ws_instance.stop()
        _ws_instance = None
