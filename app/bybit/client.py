import os, time, hmac, hashlib, json, httpx, asyncio
from typing import Any, Dict
from email.utils import parsedate_to_datetime
from app.core.logging import system_logger

# Read environment variables dynamically to avoid import-time issues
def _get_bybit_endpoint():
    return os.getenv("BYBIT_ENDPOINT", "https://api-demo.bybit.com")

def _get_bybit_api_key():
    return os.getenv("BYBIT_API_KEY", "")

def _get_bybit_api_secret():
    return os.getenv("BYBIT_API_SECRET", "")

def _get_bybit_recv_window():
    return os.getenv("BYBIT_RECV_WINDOW", "30000")

class BybitAPIError(Exception):
    """Raised when Bybit API returns retCode != 0"""
    def __init__(self, ret_code: int, ret_msg: str, result: Any = None):
        self.ret_code = ret_code
        self.ret_msg = ret_msg
        self.result = result
        super().__init__(f"Bybit API error {ret_code}: {ret_msg}")

def _check_response(response: dict) -> dict:
    """Check Bybit response for retCode and raise exception if not 0"""
    ret_code = response.get("retCode", 0)
    if ret_code == 0:
        return response
    # Treat "leverage not modified" as benign
    if ret_code == 110043:
        return response
    ret_msg = response.get("retMsg", "Unknown error")
    
    # Special handling for timestamp errors
    if ret_code == 10002:
        raise BybitAPIError(ret_code, f"Timestamp sync error: {ret_msg}. Check system clock or increase recv_window.", response.get("result"))
    
    raise BybitAPIError(ret_code, ret_msg, response.get("result"))

def _ts() -> str:
    return str(int(time.time() * 1000))

def _sign(payload: str) -> str:
    return hmac.new(_get_bybit_api_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()

def _headers(body: Dict[str, Any]):
    ts = _ts()
    body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    prehash = ts + _get_bybit_api_key() + _get_bybit_recv_window() + body_str
    return {
        "X-BAPI-API-KEY": _get_bybit_api_key(),
        "X-BAPI-TIMESTAMP": ts,
        "X-BAPI-RECV-WINDOW": _get_bybit_recv_window(),
        "X-BAPI-SIGN": _sign(prehash),
        "Content-Type": "application/json",
    }

def _headers_get(params: str = ""):
    """Headers for GET requests with query parameters"""
    ts = _ts()
    prehash = ts + _get_bybit_api_key() + _get_bybit_recv_window() + params
    return {
        "X-BAPI-API-KEY": _get_bybit_api_key(),
        "X-BAPI-TIMESTAMP": ts,
        "X-BAPI-RECV-WINDOW": _get_bybit_recv_window(),
        "X-BAPI-SIGN": _sign(prehash),
    }

class BybitClient:
    """
    Async V5 client with server-time sync and 10002 retry.
    Singleton pattern to ensure single instance across all modules.
    """
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BybitClient, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Only initialize once
        if self._initialized:
            return
            
        # Explicitly clear proxy environment variables to prevent httpx from using them
        os.environ.pop('HTTP_PROXY', None)
        os.environ.pop('HTTPS_PROXY', None)
        os.environ.pop('http_proxy', None)
        os.environ.pop('https_proxy', None)
        
        self.http = httpx.AsyncClient(
            base_url=_get_bybit_endpoint(), 
            timeout=20.0,
            trust_env=False,  # Don't read proxy from environment
            follow_redirects=True  # Follow 301/302 redirects
        )
        self._ts_offset_ms = 0
        self._last_sync = 0.0
        # Allow env override; default 60s
        self._sync_interval = int(os.getenv("BYBIT_TIME_SYNC_INTERVAL", "60"))
        
        # Mark as initialized
        self._initialized = True
        print(f"🔧 BybitClient singleton created with endpoint: {self.http.base_url}")
    
    def ensure_http_client_open(self):
        """Ensure HTTP client is open and ready for requests."""
        if self.http.is_closed:
            # Recreate HTTP client if it was closed
            self.http = httpx.AsyncClient(
                base_url=_get_bybit_endpoint(), 
                timeout=20.0,
                trust_env=False,
                follow_redirects=True
            )
            print(f"🔧 HTTP client recreated for endpoint: {self.http.base_url}")

    async def _server_ms(self) -> int:
        """Get server time in milliseconds"""
        try:
            r = await self.http.get("/v5/market/time")
            r.raise_for_status()
            data = r.json()
            if data.get("retCode") == 0 and "result" in data:
                res = data["result"]
                if "timeSecond" in res:
                    return int(res["timeSecond"]) * 1000
                if "timeNano" in res:
                    return int(res["timeNano"]) // 1000000
        except Exception:
            pass
        # Fallback to local time
        return int(time.time() * 1000)

    async def sync_time(self, force: bool = False):
        """Sync time with Bybit server"""
        now = time.time()
        if (not force) and (now - self._last_sync < self._sync_interval):
            return
        srv = await self._server_ms()
        loc = int(time.time() * 1000)
        self._ts_offset_ms = srv - loc
        self._last_sync = now
        print(f"⏱  Bybit time sync: server={srv} local={loc} offset_ms={self._ts_offset_ms}")

    def _ts_sync(self) -> str:
        """Get timestamp with server offset applied"""
        return str(int(time.time() * 1000 + self._ts_offset_ms))

    def _headers_sync(self, body: Dict[str, Any]):
        """Generate headers with synced timestamp"""
        ts = self._ts_sync()
        # Use same serialization for signature and content
        body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        prehash = ts + _get_bybit_api_key() + _get_bybit_recv_window() + body_str
        return {
            "X-BAPI-API-KEY": _get_bybit_api_key(),
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": _get_bybit_recv_window(),
            "X-BAPI-SIGN": _sign(prehash),
            "Content-Type": "application/json",
        }, body_str

    async def _get_auth(self, path: str, params: Dict[str, Any], retry_on_10002: bool = True):
        """GET with authentication and 10002 retry"""
        await self.sync_time()  # Ensure we have fresh offset
        
        # Ensure HTTP client is open
        self.ensure_http_client_open()
        
        # Build query string for signature
        query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        ts = self._ts_sync()
        prehash = ts + _get_bybit_api_key() + _get_bybit_recv_window() + query_string
        headers = {
            "X-BAPI-API-KEY": _get_bybit_api_key(),
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": _get_bybit_recv_window(),
            "X-BAPI-SIGN": _sign(prehash),
        }
        try:
            r = await self.http.get(path, params=params, headers=headers)
            r.raise_for_status()
            return _check_response(r.json())
        except BybitAPIError as e:
            if retry_on_10002 and e.ret_code == 10002:
                # Re-sync hard and retry once
                await self.sync_time(force=True)
                ts2 = self._ts_sync()
                prehash2 = ts2 + _get_bybit_api_key() + _get_bybit_recv_window() + query_string
                headers2 = {
                    "X-BAPI-API-KEY": _get_bybit_api_key(),
                    "X-BAPI-TIMESTAMP": ts2,
                    "X-BAPI-RECV-WINDOW": _get_bybit_recv_window(),
                    "X-BAPI-SIGN": _sign(prehash2),
                }
                r2 = await self.http.get(path, params=params, headers=headers2)
                r2.raise_for_status()
                return _check_response(r2.json())
            raise

    async def _post_auth(self, path: str, body: Dict[str, Any], retry_on_10002: bool = True):
        """POST with authentication and 10002 retry"""
        await self.sync_time()  # Ensure we have fresh offset
        
        # Ensure HTTP client is open
        self.ensure_http_client_open()
        
        try:
            headers, body_str = self._headers_sync(body)
            r = await self.http.post(path, headers=headers, content=body_str)
            r.raise_for_status()
            return _check_response(r.json())
        except BybitAPIError as e:
            if retry_on_10002 and e.ret_code == 10002:
                # Re-sync hard and retry once
                await self.sync_time(force=True)
                headers2, body_str2 = self._headers_sync(body)
                r2 = await self.http.post(path, headers=headers2, content=body_str2)
                r2.raise_for_status()
                return _check_response(r2.json())
            raise

    async def aclose(self):
        """Close HTTP client cleanly"""
        try:
            await self.http.aclose()
        except Exception:
            pass

    async def instruments(self, category: str, symbol: str):
        r = await self.http.get("/v5/market/instruments-info", params={"category":category,"symbol":symbol})
        r.raise_for_status()
        return _check_response(r.json())
    
    async def get_position(self, category: str, symbol: str):
        """Get current position for a symbol"""
        params = {"category": category, "symbol": symbol}
        return await self._get_auth("/v5/position/list", params)
    
    async def symbol_exists(self, category: str, symbol: str) -> bool:
        """Check if a symbol exists on Bybit and is live/tradable"""
        try:
            result = await self.instruments(category, symbol)
            # Check if we got any instruments back
            instruments = result.get("result", {}).get("list", [])
            if len(instruments) == 0:
                return False
            # Check if symbol is live/tradable
            instrument = instruments[0]
            status = instrument.get("status", "")
            # Only allow Trading status (not PreLaunch, Delivering, Closed, etc.)
            return status == "Trading"
        except Exception as e:
            print(f"⚠️  Symbol validation error for {symbol}: {e}")
            return False
    
    async def get_max_leverage(self, category: str, symbol: str) -> float:
        """Get maximum leverage allowed for a symbol"""
        try:
            result = await self.instruments(category, symbol)
            instruments = result.get("result", {}).get("list", [])
            if instruments:
                leverage_filter = instruments[0].get("leverageFilter", {})
                max_lev = float(leverage_filter.get("maxLeverage", "50"))
                return max_lev
        except Exception as e:
            print(f"⚠️  Could not get max leverage for {symbol}: {e}")
        return 50.0  # Default fallback

    async def wallet_balance(self, coin="USDT"):
        params = {"accountType":"UNIFIED","coin":coin}
        return await self._get_auth("/v5/account/wallet-balance", params)

    async def set_leverage(self, category, symbol, buy_leverage, sell_leverage):
        body = {"category":category,"symbol":symbol,"buyLeverage":str(buy_leverage),"sellLeverage":str(sell_leverage)}
        return await self._post_auth("/v5/position/set-leverage", body)

    async def place_order(self, body: Dict[str, Any], max_retries: int = 3):
        """Place order with retry logic for connection errors."""
        for attempt in range(max_retries):
            try:
                return await self._post_auth("/v5/order/create", body)
            except (httpx.ReadError, httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt < max_retries - 1:
                    system_logger.warning(f"Order placement attempt {attempt + 1} failed: {e}. Retrying...")
                    await asyncio.sleep(1)  # Wait 1 second before retry
                    continue
                else:
                    system_logger.error(f"Order placement failed after {max_retries} attempts: {e}")
                    raise
            except Exception as e:
                # For other errors, don't retry
                raise

    async def cancel_all(self, category, symbol):
        body = {"category":category,"symbol":symbol}
        return await self._post_auth("/v5/order/cancel-all", body)

    async def query_open(self, category, symbol):
        # Use GET method for querying open orders (V5 uses query params, not body)
        # settleCoin is optional, openOnly is not a valid param for V5
        params = {"category":category,"symbol":symbol}
        try:
            return await self._get_auth("/v5/order/realtime", params)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Return empty list if no orders found
                return {"retCode":0, "retMsg":"OK", "result":{"list":[]}}
            raise
        except Exception as e:
            # Return empty list on any error (symbol not live, etc.)
            print(f"⚠️  Query open orders failed: {e}")
            return {"retCode":0, "retMsg":"OK", "result":{"list":[]}}

    async def positions(self, category, symbol):
        """
        Robust: on HTTP 404, pretend 'no positions yet' instead of crashing the FSM.
        """
        body = {"category":category,"symbol":symbol}
        try:
            return await self._post_auth("/v5/position/list", body)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Return empty list if position doesn't exist yet
                return {"retCode":0, "retMsg":"OK", "result":{"list":[]}}
            raise

    # Helpers enforce required flags
    async def entry_limit_postonly(self, category, symbol, side, qty, price, link_id):
        body = {
            "category": category,
            "symbol": symbol,
            "side": side,
            "orderType": "Limit",
            "qty": str(qty),
            "price": str(price),
            "timeInForce": "PostOnly",
            "reduceOnly": False,
            "positionIdx": 0,
            "orderLinkId": link_id
        }
        return await self.place_order(body)

    async def tp_limit_reduceonly(self, category, symbol, side, qty, price, link_id):
        body = {
            "category": category,
            "symbol": symbol,
            "side": side,
            "orderType": "Limit",
            "qty": str(qty),
            "price": str(price),
            "timeInForce": "GTC",
            "reduceOnly": True,
            "positionIdx": 0,
            "orderLinkId": link_id
        }
        return await self.place_order(body)

    async def sl_market_reduceonly_mark(self, category, symbol, side, qty, sl_trigger, link_id):
        # Place a conditional market order that triggers at stop-loss price
        body = {
            "category": category,
            "symbol": symbol,
            "side": side,
            "orderType": "Market",
            "qty": str(qty),
            "reduceOnly": True,
            "closeOnTrigger": True,
            "positionIdx": 0,
            "triggerPrice": str(sl_trigger),
            "triggerBy": "MarkPrice",
            "orderLinkId": link_id
        }
        return await self.place_order(body)

    async def set_trading_stop(self, category, symbol, stop_loss, sl_order_type="Market", sl_trigger_by="MarkPrice"):
        """
        Amend position stop-loss using /v5/position/trading-stop (V5).
        This is the cleanest way to push SL to B/E after TP2.
        """
        body = {
            "category": category,
            "symbol": symbol,
            "stopLoss": str(stop_loss),
            "slOrderType": sl_order_type,
            "slTriggerBy": sl_trigger_by,
            "positionIdx": 0
        }
        body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        r = await self.http.post("/v5/position/trading-stop", headers=_headers(body), content=body_str)
        r.raise_for_status()
        return _check_response(r.json())
    
    async def get_ticker(self, symbol: str, category: str = "linear"):
        """Get ticker data for a symbol."""
        params = {
            "category": category,
            "symbol": symbol
        }
        return await self._get_auth("/v5/market/tickers", params)


# Global singleton instance getter
_global_bybit_client = None

def get_bybit_client() -> BybitClient:
    """Get the global singleton BybitClient instance."""
    global _global_bybit_client
    if _global_bybit_client is None:
        _global_bybit_client = BybitClient()
    return _global_bybit_client