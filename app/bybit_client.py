from __future__ import annotations
import time
import hmac
import hashlib
import json
from decimal import Decimal, ROUND_DOWN
import requests
from app import settings


class BybitClient:
    def __init__(self):
        self.key = settings.BYBIT_API_KEY
        self.secret = settings.BYBIT_API_SECRET
        self.endpoint = settings.BYBIT_ENDPOINT.rstrip("/")
        self.recv_window_ms = 20000  # widen default 5s window
        self._time_offset_ms = 0
        self._last_sync_epoch_ms = 0
        # Dedicated session; ignore system proxy vars to avoid SSL interception issues
        self.session = requests.Session()
        try:
            self.session.trust_env = False
        except Exception:
            pass

    def _build_query_string(self, params: dict | None) -> str:
        if not params:
            return ""
        return "&".join(f"{k}={v}" for k, v in sorted(params.items()))

    def _sign_headers(self, timestamp_ms: int, recv_window_ms: int, query_string: str = "", body: dict | None = None) -> str:
        # Per V5: signText = timestamp + api_key + recv_window + (queryString | jsonBodyString)
        if body is not None:
            body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
            sign_text = f"{timestamp_ms}{self.key}{recv_window_ms}{body_str}"
        else:
            sign_text = f"{timestamp_ms}{self.key}{recv_window_ms}{query_string}"
        return hmac.new(self.secret.encode(), sign_text.encode(), hashlib.sha256).hexdigest()

    def _post(self, path: str, body: dict):
        url = f"{self.endpoint}{path}"
        self._maybe_sync_time(force=True)
        ts = int(self._epoch_ms() + self._time_offset_ms - 500)
        body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        headers = {
            "X-BAPI-API-KEY": self.key,
            "X-BAPI-TIMESTAMP": str(ts),
            "X-BAPI-RECV-WINDOW": str(self.recv_window_ms),
            "X-BAPI-SIGN": self._sign_headers(ts, self.recv_window_ms, body=body),
            "Content-Type": "application/json",
        }
        try:
            resp = self.session.post(url, headers=headers, data=body_str.encode("utf-8"))
            return resp.json()
        except Exception as e:
            return {"retCode": -1, "retMsg": "HTTP/JSON error", "error": str(e)}

    def _get(self, path: str, params: dict | None = None, auth: bool = False):
        url = f"{self.endpoint}{path}"
        if not auth:
            try:
                return self.session.get(url, params=params).json()
            except Exception as e:
                return {"retCode": -1, "retMsg": "HTTP/JSON error", "error": str(e)}
        # Authenticated GET
        self._maybe_sync_time(force=True)
        ts = int(self._epoch_ms() + self._time_offset_ms - 500)
        # Use sorted tuple list to preserve order
        params = params or {}
        items = sorted(params.items())
        qs = "&".join(f"{k}={v}" for k, v in items)
        headers = {
            "X-BAPI-API-KEY": self.key,
            "X-BAPI-TIMESTAMP": str(ts),
            "X-BAPI-RECV-WINDOW": str(self.recv_window_ms),
            "X-BAPI-SIGN": self._sign_headers(ts, self.recv_window_ms, query_string=qs),
        }
        try:
            return self.session.get(url, headers=headers, params=items).json()
        except Exception as e:
            return {"retCode": -1, "retMsg": "HTTP/JSON error", "error": str(e)}

    def _epoch_ms(self) -> int:
        return int(time.time() * 1000)

    def _maybe_sync_time(self, force: bool = False) -> None:
        now_ms = self._epoch_ms()
        if not force and (now_ms - self._last_sync_epoch_ms) < 60_000:
            return
        try:
            resp = self.get_server_time()
            # Prefer 'time' (ms) if present; else derive from result.timeSecond
            if isinstance(resp, dict):
                if "time" in resp and isinstance(resp["time"], int):
                    server_ms = resp["time"]
                else:
                    result = resp.get("result", {})
                    time_second = result.get("timeSecond")
                    if time_second is not None:
                        server_ms = int(time_second) * 1000
                    else:
                        server_ms = now_ms
                self._time_offset_ms = server_ms - now_ms
                self._last_sync_epoch_ms = now_ms
        except Exception:
            # If sync fails, keep previous offset
            pass

    def _auth_params(self) -> dict:
        self._maybe_sync_time()
        ts = self._epoch_ms() + self._time_offset_ms
        return {
            "api_key": self.key,
            "timestamp": int(ts),
            "recv_window": int(self.recv_window_ms),
        }

    def get_server_time(self):
        url = f"{self.endpoint}/v5/market/time"
        return requests.get(url).json()

    def get_instruments_info(self, symbol: str = "BTCUSDT"):
        url = f"{self.endpoint}/v5/market/instruments-info"
        params = {"category": "linear", "symbol": symbol}
        return requests.get(url, params=params).json()

    def get_ticker(self, symbol: str):
        """Fetch real-time ticker for a linear symbol."""
        params = {"category": "linear", "symbol": symbol}
        return self._get("/v5/market/tickers", params, auth=False)

    def create_order(self, symbol: str = "BTCUSDT", side: str = "Buy", qty: str = "", price: str = "20000"):
        body = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": "Limit",
            "qty": qty,
            "price": price,
            "timeInForce": "PostOnly",
            "reduceOnly": False,
            "positionIdx": 0,
        }
        return self._post("/v5/order/create", body)

    # Wallet balance for risk sizing
    def get_wallet_balance(self, coin: str = "USDT"):
        params = {
            "accountType": "UNIFIED",
            "coin": coin,
        }
        return self._get("/v5/account/wallet-balance", params, auth=True)

    # New real endpoints for FSM
    def set_leverage(self, symbol: str, buy_leverage: int = 10, sell_leverage: int = 10):
        body = {
            "category": "linear",
            "symbol": symbol,
            "buyLeverage": str(buy_leverage),
            "sellLeverage": str(sell_leverage),
        }
        return self._post("/v5/position/set-leverage", body)

    def create_entry_order(self, symbol: str, side: str, qty: str, price: str | float, trade_id: str, entry_no: int):
        body = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": "Limit",
            "qty": str(qty),
            "price": str(price),
            "timeInForce": "PostOnly",
            "reduceOnly": False,
            "positionIdx": 0,
            "orderLinkId": f"{trade_id}-E{entry_no}",
        }
        return self._post("/v5/order/create", body)

    def get_open_orders(self, symbol: str):
        params = {
            "category": "linear",
            "symbol": symbol,
        }
        return self._get("/v5/order/realtime", params, auth=True)

    def get_order_history(self, symbol: str):
        params = {
            "category": "linear",
            "symbol": symbol,
        }
        return self._get("/v5/order/history", params, auth=True)

    # Step 7 additions: positions and TP/SL
    def get_positions(self, symbol: str):
        params = {
            "category": "linear",
            "symbol": symbol,
        }
        return self._get("/v5/position/list", params, auth=True)

    def create_tp_order(self, symbol: str, side: str, qty: str, price: str | float, trade_id: str, tp_no: int):
        body = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": "Limit",
            "qty": str(qty),
            "price": str(price),
            "timeInForce": "GTC",
            "reduceOnly": True,
            "positionIdx": 0,
            "orderLinkId": f"{trade_id}-TP{tp_no}",
        }
        return self._post("/v5/order/create", body)

    def create_sl_order(self, symbol: str, side: str, qty: str, trigger_price: str | float, trade_id: str):
        # Per Bybit: triggerDirection 2 for decreasing price triggers (close long with Sell), 1 for increasing (close short with Buy)
        trigger_direction = 2 if side == "Sell" else 1
        body = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": "Market",
            "qty": str(qty),
            "reduceOnly": True,
            "positionIdx": 0,
            "triggerPrice": str(trigger_price),
            "triggerBy": "MarkPrice",
            "triggerDirection": trigger_direction,
            "closeOnTrigger": True,
            "orderLinkId": f"{trade_id}-SL",
        }
        return self._post("/v5/order/create", body)

    def cancel_order(self, symbol: str, order_id: str | None = None, order_link_id: str | None = None):
        body: dict = {
            "category": "linear",
            "symbol": symbol,
        }
        if order_id:
            body["orderId"] = order_id
        if order_link_id:
            body["orderLinkId"] = order_link_id
        return self._post("/v5/order/cancel", body)

    def cancel_all(self, symbol: str):
        body = {
            "category": "linear",
            "symbol": symbol,
            "positionIdx": 0,
        }
        return self._post("/v5/order/cancel-all", body)

    # Quantization helpers to avoid tick/step mistakes at call sites
    @staticmethod
    def quantize_price(price: str | float | Decimal, tick: str | float | Decimal) -> str:
        p = Decimal(str(price))
        t = Decimal(str(tick))
        if t == 0:
            return str(p)
        q = (p / t).quantize(Decimal("1")) * t
        return f"{q}"

    @staticmethod
    def quantize_qty(qty: str | float | Decimal, step: str | float | Decimal) -> str:
        q = Decimal(str(qty))
        s = Decimal(str(step))
        if s == 0:
            return str(q)
        qd = (q / s).to_integral_value(rounding=ROUND_DOWN) * s
        return f"{qd}"