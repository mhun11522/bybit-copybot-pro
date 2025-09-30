import os, time, hmac, hashlib, json, httpx
from typing import Any, Dict
from app.config.settings import BYBIT_ENDPOINT, BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_RECV_WINDOW

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
    raise BybitAPIError(ret_code, ret_msg, response.get("result"))

def _ts() -> str:
    return str(int(time.time() * 1000))

def _sign(payload: str) -> str:
    return hmac.new(BYBIT_API_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()

def _headers(body: Dict[str, Any]):
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
    def __init__(self):
        self.http = httpx.AsyncClient(base_url=BYBIT_ENDPOINT, timeout=20.0)

    async def instruments(self, category: str, symbol: str):
        r = await self.http.get("/v5/market/instruments-info", params={"category":category,"symbol":symbol})
        r.raise_for_status()
        return _check_response(r.json())

    async def wallet_balance(self, coin="USDT"):
        body = {"accountType":"UNIFIED","coin":coin}
        r = await self.http.post("/v5/account/wallet-balance", headers=_headers(body), content=json.dumps(body))
        r.raise_for_status()
        return _check_response(r.json())

    async def set_leverage(self, category, symbol, buy_leverage, sell_leverage):
        body = {"category":category,"symbol":symbol,"buyLeverage":str(buy_leverage),"sellLeverage":str(sell_leverage)}
        r = await self.http.post("/v5/position/set-leverage", headers=_headers(body), content=json.dumps(body))
        r.raise_for_status()
        return _check_response(r.json())

    async def place_order(self, body: Dict[str, Any]):
        r = await self.http.post("/v5/order/create", headers=_headers(body), content=json.dumps(body))
        r.raise_for_status()
        return _check_response(r.json())

    async def cancel_all(self, category, symbol):
        body = {"category":category,"symbol":symbol}
        r = await self.http.post("/v5/order/cancel-all", headers=_headers(body), content=json.dumps(body))
        r.raise_for_status()
        return _check_response(r.json())

    async def query_open(self, category, symbol):
        body = {"category":category,"symbol":symbol,"openOnly":1}
        r = await self.http.post("/v5/order/realtime", headers=_headers(body), content=json.dumps(body))
        r.raise_for_status()
        return _check_response(r.json())

    async def positions(self, category, symbol):
        body = {"category":category,"symbol":symbol}
        r = await self.http.post("/v5/position/list", headers=_headers(body), content=json.dumps(body))
        r.raise_for_status()
        return _check_response(r.json())

    # Helpers enforce required flags
    async def entry_limit_postonly(self, category, symbol, side, qty, price, link_id):
        body = {"category":category,"symbol":symbol,"side":side,"orderType":"Limit","qty":str(qty),"price":str(price),
                "timeInForce":"PostOnly","reduceOnly":False,"positionIdx":0,"orderLinkId":link_id}
        return await self.place_order(body)

    async def tp_limit_reduceonly(self, category, symbol, side, qty, price, link_id):
        body = {"category":category,"symbol":symbol,"side":side,"orderType":"Limit","qty":str(qty),"price":str(price),
                "timeInForce":"GTC","reduceOnly":True,"positionIdx":0,"orderLinkId":link_id}
        return await self.place_order(body)

    async def sl_market_reduceonly_mark(self, category, symbol, side, qty, sl_trigger, link_id):
        body = {"category":category,"symbol":symbol,"side":side,"orderType":"Market","qty":str(qty),
                "reduceOnly":True,"closeOnTrigger":True,"positionIdx":0,
                "stopLoss":str(sl_trigger),"slOrderType":"Market","slTriggerBy":"MarkPrice",
                "orderLinkId":link_id}
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
        r = await self.http.post("/v5/position/trading-stop", headers=_headers(body), content=json.dumps(body))
        r.raise_for_status()
        return _check_response(r.json())