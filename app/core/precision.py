from decimal import Decimal
from functools import lru_cache
from app.bybit_client import BybitClient

_client = BybitClient()


@lru_cache(maxsize=256)
def _filters(symbol: str):
    data = _client.get_instruments_info(symbol) or {}
    item = (data.get("result", {}).get("list") or [{}])[0]
    pricef = item.get("priceFilter", {})
    lot = item.get("lotSizeFilter", {})
    tick = Decimal(str(pricef.get("tickSize", "0.01")))
    step = Decimal(str(lot.get("qtyStep", "0.001")))
    min_notional = Decimal(str(lot.get("minNotionalValue", "0")))
    return tick, step, min_notional


def q_price(symbol: str, p) -> Decimal:
    tick, _, _ = _filters(symbol)
    p = Decimal(str(p))
    if tick == 0:
        return p
    return (p / tick).quantize(Decimal("1")) * tick


def q_qty(symbol: str, q) -> Decimal:
    _, step, _ = _filters(symbol)
    q = Decimal(str(q))
    if step == 0:
        return q
    return (q / step).quantize(Decimal("1")) * step


def ensure_min_notional(symbol: str, price, qty) -> Decimal:
    _, _, min_notional = _filters(symbol)
    price_d = Decimal(str(price))
    qty_d = Decimal(str(qty))
    if min_notional <= 0 or price_d <= 0:
        return q_qty(symbol, qty_d)
    notional = price_d * qty_d
    if notional < min_notional:
        needed = min_notional / price_d
        return q_qty(symbol, needed)
    return q_qty(symbol, qty_d)

