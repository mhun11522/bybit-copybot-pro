import time
import hmac
import hashlib
import requests
from app import settings


class BybitClient:
    def __init__(self):
        self.key = settings.BYBIT_API_KEY
        self.secret = settings.BYBIT_API_SECRET
        self.endpoint = settings.BYBIT_ENDPOINT.rstrip("/")

    def _sign(self, params: dict) -> dict:
        """Sign params with HMAC SHA256 (per Bybit v5 API rules)."""
        query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        signature = hmac.new(self.secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()
        return {**params, "sign": signature}

    def get_server_time(self):
        url = f"{self.endpoint}/v5/market/time"
        return requests.get(url).json()

    def get_instruments_info(self, symbol: str = "BTCUSDT"):
        url = f"{self.endpoint}/v5/market/instruments-info"
        params = {"category": "linear", "symbol": symbol}
        return requests.get(url, params=params).json()

    def create_order(self, symbol: str = "BTCUSDT", side: str = "Buy", qty: str = "0.001", price: str = "20000"):
        url = f"{self.endpoint}/v5/order/create"
        params = {
            "api_key": self.key,
            "timestamp": int(time.time() * 1000),
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
        signed = self._sign(params)
        return requests.post(url, data=signed).json()