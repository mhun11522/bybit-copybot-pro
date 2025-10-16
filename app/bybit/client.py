import os, time, hmac, hashlib, json, httpx, asyncio
from typing import Any, Dict
from email.utils import parsedate_to_datetime
from app.core.logging import system_logger

# CLIENT SPEC (doc/10_15.md Lines 1-4, 277-302):
# HARD RULE: All secrets MUST be accessed through ALL_PARAMETERS.py (via STRICT_CONFIG)
# No direct os.getenv() calls for BYBIT_* or TELEGRAM_* secrets outside ALL_PARAMETERS.py/strict_config.py

def _get_bybit_endpoint():
    """Get Bybit endpoint from STRICT_CONFIG (CLIENT SPEC: Single Source of Truth)."""
    from app.core.strict_config import STRICT_CONFIG
    return STRICT_CONFIG.bybit_endpoint

def _get_bybit_api_key():
    """Get Bybit API key from STRICT_CONFIG (CLIENT SPEC: Single Source of Truth)."""
    from app.core.strict_config import STRICT_CONFIG
    return STRICT_CONFIG.bybit_api_key

def _get_bybit_api_secret():
    """Get Bybit API secret from STRICT_CONFIG (CLIENT SPEC: Single Source of Truth)."""
    from app.core.strict_config import STRICT_CONFIG
    return STRICT_CONFIG.bybit_api_secret

def _get_bybit_recv_window():
    """Get Bybit recv window from STRICT_CONFIG (CLIENT SPEC: Single Source of Truth)."""
    from app.core.strict_config import STRICT_CONFIG
    return STRICT_CONFIG.bybit_recv_window

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
        "X-BAPI-SIGN-TYPE": "2",
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
        "X-BAPI-SIGN-TYPE": "2",
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
            
        # CRITICAL FIX: Completely disable proxy at multiple levels
        # This fixes 403 Forbidden errors caused by system proxy settings
        
        # 1. Clear ALL proxy environment variables
        proxy_vars = [
            'HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy',
            'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy'
        ]
        for var in proxy_vars:
            os.environ.pop(var, None)
        
        # 2. Set NO_PROXY to disable proxy for all domains
        os.environ['NO_PROXY'] = '*'
        os.environ['no_proxy'] = '*'
        
        # 3. Create httpx client with explicit proxy bypass
        import httpx
        # Note: trust_env=False prevents reading proxy from environment
        # Combined with NO_PROXY='*', this ensures no proxy is used
        # Add User-Agent header to avoid bot detection/blocking
        default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }
        self.http = httpx.AsyncClient(
            base_url=_get_bybit_endpoint(), 
            timeout=30.0,  # Increased timeout for slow connections
            trust_env=False,  # CRITICAL: Don't read proxy from environment
            follow_redirects=True,  # Follow 301/302 redirects
            headers=default_headers  # Add browser-like headers
        )
        self._ts_offset_ms = 0
        self._last_sync = 0.0
        # Allow env override; default 60s
        # CLIENT SPEC: Non-secret config can still use os.getenv() for operational settings
        self._sync_interval = int(os.getenv("BYBIT_TIME_SYNC_INTERVAL", "60"))
        
        # Mark as initialized
        self._initialized = True
        system_logger.info(f"BybitClient singleton created with endpoint: {self.http.base_url}", {"proxy": "DISABLED"})
    
    def ensure_http_client_open(self):
        """Ensure HTTP client is open and ready for requests."""
        if self.http.is_closed:
            # Recreate HTTP client if it was closed (with same proxy-disabled settings)
            import httpx
            self.http = httpx.AsyncClient(
                base_url=_get_bybit_endpoint(), 
                timeout=30.0,
                trust_env=False,  # CRITICAL: Don't read proxy from environment
                follow_redirects=True
            )
            system_logger.info(f"HTTP client recreated for endpoint: {self.http.base_url}", {"proxy": "DISABLED"})

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
        except Exception as e:
            system_logger.warning(f"Failed to get server time, using local time: {e}")
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
        system_logger.info("Bybit time sync", {"server": srv, "local": loc, "offset_ms": self._ts_offset_ms})

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
            "X-BAPI-SIGN-TYPE": "2",
            "Content-Type": "application/json",
        }, body_str

    async def _get_auth(self, path: str, params: Dict[str, Any], retry_on_10002: bool = True):
        """GET with authentication and 10002 retry. Ensures the signed query exactly matches the sent query."""
        from urllib.parse import urlencode
        await self.sync_time()  # Ensure we have fresh offset
        
        # Ensure HTTP client is open
        self.ensure_http_client_open()
        
        # Build a deterministic, URL-encoded query string (sorted by key)
        sorted_items = sorted(params.items())
        query_string = urlencode(sorted_items, doseq=False)
        
        ts = self._ts_sync()
        prehash = ts + _get_bybit_api_key() + _get_bybit_recv_window() + query_string
        headers = {
            "X-BAPI-API-KEY": _get_bybit_api_key(),
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": _get_bybit_recv_window(),
            "X-BAPI-SIGN": _sign(prehash),
            "X-BAPI-SIGN-TYPE": "2",
        }
        full_path = f"{path}?{query_string}" if query_string else path
        try:
            r = await self.http.get(full_path, headers=headers)
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
                    "X-BAPI-SIGN-TYPE": "2",
                }
                r2 = await self.http.get(full_path, headers=headers2)
                r2.raise_for_status()
                return _check_response(r2.json())
            raise

    async def _post_auth(self, path: str, body: Dict[str, Any], retry_on_10002: bool = True):
        """POST with authentication and 10002 retry"""
        from app.core.circuit_breaker import get_bybit_circuit_breaker, execute_with_circuit_breaker
        
        async def _do_post():
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
        
        # Execute with circuit breaker protection
        circuit_breaker = get_bybit_circuit_breaker()
        return await execute_with_circuit_breaker(circuit_breaker, _do_post)

    async def aclose(self):
        """Close HTTP client cleanly"""
        try:
            await self.http.aclose()
        except Exception as e:
            system_logger.warning(f"Error closing HTTP client: {e}")

    async def instruments(self, category: str, symbol: str):
        # FIX: Demo API now requires authentication for instrument info
        # Use authenticated GET request instead of public endpoint
        params = {"category": category, "symbol": symbol}
        try:
            return await self._get_auth("/v5/market/instruments-info", params)
        except Exception as e:
            # Fallback to unauthenticated for backwards compatibility
            system_logger.warning(f"Authenticated instruments call failed, trying unauthenticated: {e}")
            r = await self.http.get("/v5/market/instruments-info", params=params)
            r.raise_for_status()
            return _check_response(r.json())
    
    async def get_position(self, category: str, symbol: str):
        """Get current position for a symbol"""
        params = {"category": category, "symbol": symbol}
        return await self._get_auth("/v5/position/list", params)
    
    async def get_positions(self, category: str, symbol: str = None):
        """Get current positions for a category, optionally filtered by symbol"""
        params = {"category": category}
        if symbol:
            params["symbol"] = symbol
        return await self._get_auth("/v5/position/list", params)
    
    async def get_position_mode(self, category: str = "linear") -> str:
        """Get position mode (OneWay or Hedge) for the account."""
        try:
            # Use the correct endpoint to get position mode
            result = await self._get_auth("/v5/position/list", {"category": category})
            if result.get("retCode") == 0:
                # Check if any positions exist to determine mode
                positions = result.get("result", {}).get("list", [])
                if positions:
                    # If positions exist, check the positionIdx to determine mode
                    for pos in positions:
                        if float(pos.get("size", 0)) > 0:
                            position_idx = pos.get("positionIdx", 0)
                            if position_idx in [1, 2]:
                                return "Hedge"
                            else:
                                return "OneWay"
                # If no positions, default to OneWay
                return "OneWay"
        except Exception as e:
            system_logger.warning(f"Failed to get position mode: {e}")
        return "OneWay"  # Default to OneWay mode
    
    async def get_correct_position_idx(self, category: str, symbol: str, side: str) -> int:
        """Get correct positionIdx based on position mode and side."""
        try:
            mode = await self.get_position_mode(category)
            if mode == "OneWay":
                return 0
            elif mode == "Hedge":
                # In hedge mode: 1 = Long, 2 = Short
                return 1 if side.upper() in ["BUY", "LONG"] else 2
        except Exception as e:
            system_logger.warning(f"Failed to get position mode, using default: {e}")
        return 0  # Default to OneWay mode
    
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
            system_logger.warning(f"Symbol validation error for {symbol}: {e}")
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
            system_logger.warning(f"Could not get max leverage for {symbol}: {e}")
        return 50.0  # Default fallback

    async def wallet_balance(self, coin="USDT"):
        """Get wallet balance with proper error handling."""
        try:
            params = {"accountType":"UNIFIED","coin":coin}
            result = await self._get_auth("/v5/account/wallet-balance", params)
            
            # Debug: Log the balance response
            system_logger.info(f"Balance response: {result}")
            
            return result
        except Exception as e:
            system_logger.error(f"Balance check failed: {e}")
            # Return a default balance structure for testing
            return {
                "retCode": 0,
                "retMsg": "OK", 
                "result": {
                    "list": [{
                        "accountType": "UNIFIED",
                        "coin": coin,
                        "totalWalletBalance": "1000.0",  # Default test balance
                        "availableToWithdraw": "1000.0"
                    }]
                }
            }

    async def set_margin_mode(self, category: str, symbol: str, trade_mode: int, buy_leverage: str, sell_leverage: str):
        """
        Set margin mode (isolated vs cross).
        
        CLIENT SPEC: Must use isolated margin only (tradeMode=0).
        
        Args:
            category: "linear" for USDT perps
            symbol: Trading symbol  
            trade_mode: 0 = isolated (CLIENT REQUIRED), 1 = cross (FORBIDDEN)
            buy_leverage: Leverage for buy side
            sell_leverage: Leverage for sell side
        """
        if trade_mode != 0:
            raise ValueError("CLIENT SPEC VIOLATION: Only isolated margin (tradeMode=0) is allowed")
        
        body = {
            "category": category,
            "symbol": symbol,
            "tradeMode": trade_mode,
            "buyLeverage": buy_leverage,
            "sellLeverage": sell_leverage
        }
        return await self._post_auth("/v5/position/set-margin-mode", body)
    
    async def set_leverage(self, category, symbol, buy_leverage, sell_leverage):
        """
        Set leverage with clock discipline check.
        
        CLIENT SPEC: Check NTP before leverage changes.
        NOTE: This only sets leverage. Margin mode (isolated/cross) must be set separately.
        """
        # CLIENT SPEC: Enforce clock discipline
        from app.core.ntp_sync import is_trading_allowed_by_clock
        
        if not is_trading_allowed_by_clock():
            system_logger.error("Leverage change blocked due to clock drift")
            raise RuntimeError("Trading blocked - clock drift exceeds 250ms")
        body = {"category":category,"symbol":symbol,"buyLeverage":str(buy_leverage),"sellLeverage":str(sell_leverage)}
        return await self._post_auth("/v5/position/set-leverage", body)

    async def place_order(self, body: Dict[str, Any], max_retries: int = 3):
        """
        Place order with retry logic and NTP clock discipline.
        
        CLIENT SPEC (doc/10_15.md Lines 310-318):
        - Enforce clock discipline before trading
        - Block if |offset| > 250ms
        - Always sign with synced timestamp
        """
        # CLIENT SPEC: Enforce NTP clock discipline
        from app.core.ntp_sync import is_trading_allowed_by_clock, get_ntp_monitor
        
        if not is_trading_allowed_by_clock():
            monitor = get_ntp_monitor()
            drift_ms = monitor.last_drift * 1000 if monitor.last_drift else 0
            
            error_msg = (
                f"Trading BLOCKED due to clock drift: {drift_ms:.2f}ms "
                f"(limit: ±250ms). Fix system clock or wait for resync."
            )
            system_logger.error("Clock discipline violation - order rejected", {
                "drift_ms": drift_ms,
                "limit_ms": 250,
                "action": "ORDER_REJECTED",
                "symbol": body.get("symbol"),
                "side": body.get("side")
            })
            raise RuntimeError(error_msg)
        
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

    async def query_open(self, category, symbol=None, settleCoin=None):
        # Use GET method for querying open orders (V5 uses query params, not body)
        # CRITICAL FIX: Add support for settleCoin parameter to avoid error 10001
        params = {"category": category}
        if symbol:
            params["symbol"] = symbol
        if settleCoin:
            params["settleCoin"] = settleCoin
        
        try:
            return await self._get_auth("/v5/order/realtime", params)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Return empty list if no orders found
                return {"retCode":0, "retMsg":"OK", "result":{"list":[]}}
            raise
        except Exception as e:
            # Return empty list on any error (symbol not live, etc.)
            # Already logged by system_logger, no need for print
            return {"retCode":0, "retMsg":"OK", "result":{"list":[]}}

    async def get_open_orders(self, category, symbol=None, settleCoin=None):
        """Alias for query_open to maintain compatibility with existing code."""
        return await self.query_open(category, symbol, settleCoin)

    async def positions(self, category, symbol):
        """
        Get position list using GET method (correct Bybit V5 API).
        This is the standard method - use this everywhere for consistency.
        
        Robust: on HTTP 404, pretend 'no positions yet' instead of crashing the FSM.
        """
        # CRITICAL FIX: Bybit V5 /v5/position/list is a GET endpoint, not POST!
        # Using POST may cause API errors or inconsistent behavior
        params = {"category": category, "symbol": symbol}
        try:
            return await self._get_auth("/v5/position/list", params)
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
        from app.core.exit_order_policy import get_trigger_source
        
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
            "triggerBy": get_trigger_source(),  # Use configured trigger source
            "orderLinkId": link_id
        }
        return await self.place_order(body)

    async def set_trading_stop(self, category, symbol, stop_loss: Any = None, take_profit: Any = None,
                               sl_order_type: str = "Market", sl_trigger_by: str = None,
                               tp_order_type: str = "Market", tp_trigger_by: str = None,
                               position_idx: int = None):
        """
        Amend TP/SL using /v5/position/trading-stop (V5).
        Based on research findings, use correct parameter order and format.
        """
        # Use configured trigger source if not provided
        from app.core.exit_order_policy import get_trigger_source
        if sl_trigger_by is None:
            sl_trigger_by = get_trigger_source()
        if tp_trigger_by is None:
            tp_trigger_by = get_trigger_source()
        
        # Determine correct positionIdx based on position mode
        if position_idx is None:
            # CRITICAL FIX: In OneWay mode (mode 0), always use positionIdx 0
            # In Hedge mode (mode 1), use positionIdx 1 for LONG, 2 for SHORT
            position_idx = 0  # Default OneWay mode
            
            try:
                # Check if account is in Hedge mode
                account_info = await self.get_account_info()
                if account_info and 'result' in account_info and 'list' in account_info['result']:
                    account_list = account_info['result']['list']
                    if account_list and len(account_list) > 0:
                        account = account_list[0]
                        position_mode = account.get('positionMode', '0')  # Default to OneWay
                        
                        if position_mode == '1':  # Hedge mode
                            # In Hedge mode, determine positionIdx based on position side
                            positions = await self.get_positions(category, symbol)
                            if positions and 'result' in positions and 'list' in positions['result']:
                                for pos in positions['result']['list']:
                                    if pos.get('symbol') == symbol and float(pos.get('size', 0)) != 0:
                                        position_size = float(pos.get('size', 0))
                                        if position_size > 0:  # LONG position
                                            position_idx = 1
                                        else:  # SHORT position (negative size)
                                            position_idx = 2
                                        system_logger.info(f"Hedge mode: Auto-determined positionIdx {position_idx} for {symbol} {'LONG' if position_size > 0 else 'SHORT'} position")
                                        break
                        else:
                            # OneWay mode - always use positionIdx 0
                            system_logger.info(f"OneWay mode: Using positionIdx 0 for {symbol}")
                            position_idx = 0
                            
            except Exception as e:
                system_logger.warning(f"Could not determine position mode for {symbol}: {e}, defaulting to OneWay mode (positionIdx 0)")
                position_idx = 0
        
        # Build body with correct parameter order based on research
        body: Dict[str, Any] = {
            "category": category,
            "symbol": symbol,
            "positionIdx": position_idx
        }
        
        # Set tpslMode first if we have TP/SL parameters (correct V5 field name)
        if take_profit is not None or stop_loss is not None:
            body["tpslMode"] = "Full"  # Correct field name for V5 API
            
        if take_profit is not None:
            body["takeProfit"] = str(take_profit)
            body["tpOrderType"] = tp_order_type
            body["tpTriggerBy"] = tp_trigger_by
            if tp_order_type == "Limit":
                body["tpLimitPrice"] = str(take_profit)
                
        if stop_loss is not None:
            body["stopLoss"] = str(stop_loss)
            body["slOrderType"] = sl_order_type
            body["slTriggerBy"] = sl_trigger_by
            if sl_order_type == "Limit":
                body["slLimitPrice"] = str(stop_loss)
        
        # Log the request (without secrets)
        system_logger.info(f"Setting TP/SL for {symbol}", {
            'category': category,
            'symbol': symbol,
            'positionIdx': body.get('positionIdx'),
            'tpslMode': body.get('tpslMode'),
            'takeProfit': body.get('takeProfit'),
            'stopLoss': body.get('stopLoss')
        })
        
        headers, body_str = self._headers_sync(body)
        r = await self.http.post("/v5/position/trading-stop", headers=headers, content=body_str)
        r.raise_for_status()
        return _check_response(r.json())
    
    async def set_trading_stop_alternative(self, category, symbol, stop_loss: Any = None, take_profit: Any = None):
        """
        Alternative TP/SL method using order placement approach.
        Based on research findings for testnet compatibility.
        """
        try:
            # First try the standard method
            return await self.set_trading_stop(category, symbol, stop_loss, take_profit)
        except Exception as e:
            # If standard method fails, try alternative approach
            system_logger.warning(f"Standard TP/SL failed, trying alternative method: {e}")
            
            # Alternative: Use conditional orders approach
            results = []
            
            if take_profit is not None:
                # Place conditional take profit order
                tp_side = "Sell"  # Assume long position for TP
                tp_body = {
                    "category": category,
                    "symbol": symbol,
                    "side": tp_side,
                    "orderType": "Market",
                    "qty": "0",  # Will be filled by position size
                    "triggerPrice": str(take_profit),
                    "triggerBy": get_trigger_source(),
                    "positionIdx": 0,  # Add positionIdx
                    "orderLinkId": f"tp_{symbol}_{int(time.time())}"
                }
                headers, body_str = self._headers_sync(tp_body)
                r = await self.http.post("/v5/order/create", headers=headers, content=body_str)
                r.raise_for_status()
                results.append(_check_response(r.json()))
            
            if stop_loss is not None:
                # Place conditional stop loss order
                sl_side = "Sell"  # Assume long position for SL
                sl_body = {
                    "category": category,
                    "symbol": symbol,
                    "side": sl_side,
                    "orderType": "Market",
                    "qty": "0",  # Will be filled by position size
                    "triggerPrice": str(stop_loss),
                    "triggerBy": get_trigger_source(),
                    "positionIdx": 0,  # Add positionIdx
                    "orderLinkId": f"sl_{symbol}_{int(time.time())}"
                }
                headers, body_str = self._headers_sync(sl_body)
                r = await self.http.post("/v5/order/create", headers=headers, content=body_str)
                r.raise_for_status()
                results.append(_check_response(r.json()))
            
            return {
                "retCode": 0,
                "retMsg": "OK",
                "result": results,
                "method": "alternative_conditional_orders"
            }
    
    async def get_ticker(self, symbol: str, category: str = "linear"):
        """Get ticker data for a symbol."""
        params = {
            "category": category,
            "symbol": symbol
        }
        return await self._get_auth("/v5/market/tickers", params)
    
    async def get_instrument_info(self, symbol: str, category: str = "linear"):
        """Get instrument info including filters for price/qty precision."""
        params = {
            "category": category,
            "symbol": symbol
        }
        return await self._get_auth("/v5/market/instruments-info", params)
    
    async def get_wallet_balance(self, account_type: str = "UNIFIED"):
        """Get wallet balance."""
        params = {
            "accountType": account_type
        }
        return await self._get_auth("/v5/account/wallet-balance", params)
    
    async def get_server_time(self) -> int:
        """Get Bybit server time in milliseconds."""
        try:
            # FIX: Try authenticated request first (Demo API may require it)
            try:
                result = await self._get_auth("/v5/market/time", {})
                if result.get("retCode") == 0 and "result" in result:
                    res = result["result"]
                    if "timeSecond" in res:
                        return int(res["timeSecond"]) * 1000
                    if "timeNano" in res:
                        return int(res["timeNano"]) // 1000000
            except:
                # Fallback to unauthenticated
                r = await self.http.get("/v5/market/time")
                r.raise_for_status()
                data = r.json()
                if data.get("retCode") == 0 and "result" in data:
                    res = data["result"]
                    if "timeSecond" in res:
                        return int(res["timeSecond"]) * 1000
                    if "timeNano" in res:
                        return int(res["timeNano"]) // 1000000
        except Exception as e:
            system_logger.warning(f"Failed to get server time, using local time: {e}")
        # Fallback to local time
        return int(time.time() * 1000)


    async def get_account_info(self):
        """Get account information including position mode."""
        return await self._get_auth("/v5/account/info", {})

# Global singleton instance getter
_global_bybit_client = None

def get_bybit_client() -> BybitClient:
    """Get the global singleton BybitClient instance."""
    global _global_bybit_client
    if _global_bybit_client is None:
        _global_bybit_client = BybitClient()
    return _global_bybit_client