import asyncio
import json
import time
import hmac
import hashlib
from typing import Callable, Dict, Optional
import websockets
from app.config.settings import BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_ENDPOINT, BYBIT_RECV_WINDOW

class BybitWebSocket:
    """
    Bybit WebSocket client for real-time order and position updates.
    Supports private channels (execution, position) with authentication.
    """
    
    def __init__(self):
        # Determine WebSocket endpoint from REST endpoint
        if "testnet" in BYBIT_ENDPOINT:
            self.ws_url = "wss://stream-testnet.bybit.com/v5/private"
        else:
            self.ws_url = "wss://stream.bybit.com/v5/private"
        
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        self.subscriptions = set()
        
        # Event handlers: symbol -> callback(data)
        self.execution_handlers: Dict[str, Callable] = {}
        self.position_handlers: Dict[str, Callable] = {}
        
        # Heartbeat
        self.last_pong = time.time()
        self.ping_interval = 20  # Send ping every 20 seconds
        
    def _generate_auth_signature(self) -> dict:
        """Generate authentication payload for private WebSocket (Bybit V5)
        
        Official format from: https://bybit-exchange.github.io/docs/v5/ws/connect#authentication
        """
        # Generate expires timestamp in milliseconds (as integer)
        expires = int((time.time() + 1) * 1000)
        
        # Sign the payload: signature = HMAC_SHA256("GET/realtime{expires}", secret)
        # This is the OFFICIAL format from Bybit docs for private WebSocket
        sign_str = f"GET/realtime{expires}"
        signature = str(hmac.new(
            bytes(BYBIT_API_SECRET, "utf-8"),
            bytes(sign_str, "utf-8"),
            digestmod="sha256"
        ).hexdigest())
        
        return {
            "op": "auth",
            "args": [BYBIT_API_KEY, expires, signature]  # EXACTLY 3 args!
        }
    
    async def connect(self):
        """Connect to Bybit WebSocket and authenticate"""
        try:
            print(f"🔌 Connecting to Bybit WebSocket: {self.ws_url}")
            self.ws = await websockets.connect(self.ws_url, ping_interval=None)
            print("✅ Bybit WebSocket connected")
            
            # Authenticate
            auth_payload = self._generate_auth_signature()
            print(f"🔐 Sending auth: {auth_payload}")  # Debug log
            await self.ws.send(json.dumps(auth_payload))
            print("🔐 Authentication sent, waiting for confirmation...")
            
            # Wait for auth response
            response = await self.ws.recv()
            auth_response = json.loads(response)
            
            if auth_response.get("success"):
                print("✅ Bybit WebSocket authenticated successfully")
                return True
            else:
                print(f"❌ Bybit WebSocket authentication failed: {auth_response}")
                return False
                
        except Exception as e:
            print(f"❌ Bybit WebSocket connection failed: {e}")
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
            print(f"📡 Subscribed to execution updates for {symbol}")
    
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
            print(f"📡 Subscribed to position updates for {symbol}")
    
    async def unsubscribe(self, symbol: str):
        """Remove handlers for a symbol"""
        self.execution_handlers.pop(symbol, None)
        self.position_handlers.pop(symbol, None)
        print(f"📴 Unsubscribed from updates for {symbol}")
    
    async def _handle_message(self, message: dict):
        """Process incoming WebSocket messages"""
        
        # Handle pong responses
        if message.get("op") == "pong":
            self.last_pong = time.time()
            return
        
        # Handle subscription confirmations
        if message.get("op") == "subscribe":
            if message.get("success"):
                print(f"✅ Subscription confirmed: {message.get('ret_msg', 'OK')}")
            return
        
        # Handle execution updates (order fills)
        topic = message.get("topic", "")
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
                        print(f"⚠️  Execution handler error for {symbol}: {e}")
        
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
                        print(f"⚠️  Position handler error for {symbol}: {e}")
    
    async def _heartbeat_loop(self):
        """Send periodic pings to keep connection alive"""
        while self.running and self.ws and not self.ws.closed:
            try:
                await asyncio.sleep(self.ping_interval)
                
                # Send ping
                ping_msg = {"op": "ping"}
                await self.ws.send(json.dumps(ping_msg))
                
                # Check if we received pong recently
                if time.time() - self.last_pong > 60:
                    print("⚠️  No pong received in 60s, reconnecting...")
                    await self.reconnect()
                    
            except Exception as e:
                print(f"⚠️  Heartbeat error: {e}")
                break
    
    async def _receive_loop(self):
        """Continuously receive and process messages"""
        while self.running and self.ws:
            try:
                message_str = await self.ws.recv()
                message = json.loads(message_str)
                await self._handle_message(message)
                
            except websockets.exceptions.ConnectionClosed:
                print("⚠️  WebSocket connection closed")
                if self.running:
                    await self.reconnect()
                break
            except Exception as e:
                print(f"⚠️  WebSocket receive error: {e}")
                if self.running:
                    await asyncio.sleep(1)
    
    async def reconnect(self):
        """Reconnect to WebSocket and restore subscriptions"""
        print("🔄 Reconnecting to Bybit WebSocket...")
        
        # Store current subscriptions
        old_execution_handlers = self.execution_handlers.copy()
        old_position_handlers = self.position_handlers.copy()
        
        # Close old connection
        if self.ws:
            try:
                await self.ws.close()
            except:
                pass
        
        # Wait a bit before reconnecting
        await asyncio.sleep(2)
        
        # Reconnect
        if await self.connect():
            # Restore subscriptions
            for symbol, handler in old_execution_handlers.items():
                await self.subscribe_execution(symbol, handler)
            
            for symbol, handler in old_position_handlers.items():
                await self.subscribe_position(symbol, handler)
            
            print("✅ WebSocket reconnected and subscriptions restored")
        else:
            print("❌ Reconnection failed")
    
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
        print("🛑 Stopping Bybit WebSocket...")
        self.running = False
        
        if self.ws:
            try:
                await self.ws.close()
            except:
                pass
        
        self.execution_handlers.clear()
        self.position_handlers.clear()
        self.subscriptions.clear()
        print("✅ Bybit WebSocket stopped")


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
