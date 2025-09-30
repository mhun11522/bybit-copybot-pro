"""ACK-gated Bybit V5 client with proper order semantics."""

import os
import time
import hmac
import hashlib
import json
import httpx
from typing import Any, Dict
from app.config.settings import BYBIT_ENDPOINT, BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_RECV_WINDOW

def _ts() -> str:
    """Get current timestamp in milliseconds."""
    return str(int(time.time() * 1000))

def _sign(payload: str) -> str:
    """Sign payload with API secret."""
    return hmac.new(BYBIT_API_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()

def _headers(body: Dict[str, Any]):
    """Generate signed headers for Bybit API."""
    ts = _ts()
    body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    prehash = ts + BYBIT_API_KEY + BYBIT_RECV_WINDOW + body_str
    return {
        "X-BAPI-API-KEY": BYBIT_API_KEY,
        "X-BAPI-TIMESTAMP": ts,
        "X-BAPI-RECV-WINDOW": BYBIT_RECV_WINDOW,
        "X-BAPI-SIGN": _sign(prehash),
        "Content-Type": "application/json",
    }

class BybitClient:
    """ACK-gated Bybit V5 client with proper order semantics."""
    
    def __init__(self):
        self.http = httpx.AsyncClient(base_url=BYBIT_ENDPOINT, timeout=20.0)

    async def instruments(self, category: str, symbol: str):
        """Get instrument info for quantization."""
        r = await self.http.get("/v5/market/instruments-info", params={"category": category, "symbol": symbol})
        r.raise_for_status()
        return r.json()

    async def wallet_balance(self, coin="USDT"):
        """Get wallet balance."""
        body = {"accountType": "UNIFIED", "coin": coin}
        r = await self.http.post("/v5/account/wallet-balance", headers=_headers(body), content=json.dumps(body))
        r.raise_for_status()
        return r.json()

    async def set_leverage(self, category, symbol, buy_leverage, sell_leverage):
        """Set leverage for symbol."""
        body = {
            "category": category,
            "symbol": symbol,
            "buyLeverage": str(buy_leverage),
            "sellLeverage": str(sell_leverage)
        }
        r = await self.http.post("/v5/position/set-leverage", headers=_headers(body), content=json.dumps(body))
        r.raise_for_status()
        return r.json()

    async def place_order(self, body: Dict[str, Any]):
        """Place order with ACK."""
        r = await self.http.post("/v5/order/create", headers=_headers(body), content=json.dumps(body))
        r.raise_for_status()
        return r.json()

    async def cancel_all(self, category, symbol):
        """Cancel all orders for symbol."""
        body = {"category": category, "symbol": symbol}
        r = await self.http.post("/v5/order/cancel-all", headers=_headers(body), content=json.dumps(body))
        r.raise_for_status()
        return r.json()

    async def query_open(self, category, symbol):
        """Query open orders."""
        body = {"category": category, "symbol": symbol, "openOnly": 1}
        r = await self.http.post("/v5/order/realtime", headers=_headers(body), content=json.dumps(body))
        r.raise_for_status()
        return r.json()

    async def positions(self, category, symbol):
        """Get positions."""
        body = {"category": category, "symbol": symbol}
        r = await self.http.post("/v5/position/list", headers=_headers(body), content=json.dumps(body))
        r.raise_for_status()
        return r.json()

    # Enforced order semantics per client requirements:
    
    async def entry_limit_postonly(self, category, symbol, side, qty, price, link_id):
        """Entry: Limit + PostOnly (maker)."""
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
        """TP: Limit + ReduceOnly + GTC."""
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
        """SL: Market + ReduceOnly with triggerBy=MarkPrice."""
        body = {
            "category": category,
            "symbol": symbol,
            "side": side,
            "orderType": "Market",
            "qty": str(qty),
            "reduceOnly": True,
            "closeOnTrigger": True,
            "positionIdx": 0,
            "stopLoss": str(sl_trigger),
            "slOrderType": "Market",
            "slTriggerBy": "MarkPrice",
            "orderLinkId": link_id
        }
        return await self.place_order(body)