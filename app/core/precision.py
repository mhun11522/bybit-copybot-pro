from decimal import Decimal
from functools import lru_cache
from app.bybit.client import BybitClient

_client = BybitClient()

@lru_cache(maxsize=512)
async def _filters(category: str, symbol: str):
    """
    Fetch tickSize, qtyStep, and minNotional from Bybit once and cache.
    """
    data = await _client.instruments(category, symbol)
    item = data["result"]["list"][0]
    tick = Decimal(item["priceFilter"]["tickSize"])
    step = Decimal(item["lotSizeFilter"]["qtyStep"])
    min_notional = Decimal(item["lotSizeFilter"].get("minNotionalValue", "0"))
    return tick, step, min_notional

async def q_price(category, symbol, price):
    tick, _, _ = await _filters(category, symbol)
    p = Decimal(str(price))
    return (p / tick).quantize(Decimal("1")) * tick

async def q_qty(category, symbol, qty):
    _, step, _ = await _filters(category, symbol)
    q = Decimal(str(qty))
    return (q / step).quantize(Decimal("1")) * step

async def ensure_min_notional(category, symbol, price, qty):
    _, _, min_notional = await _filters(category, symbol)
    notional = Decimal(str(price)) * Decimal(str(qty))
    if notional < min_notional and min_notional > 0:
        needed = min_notional / Decimal(str(price))
        return await q_qty(category, symbol, needed)
    return await q_qty(category, symbol, qty)