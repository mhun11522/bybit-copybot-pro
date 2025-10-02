from decimal import Decimal
from app.bybit.client import BybitClient
from app.core.precision import q_qty, q_price, ensure_min_notional
from app.config.settings import IM_PER_ENTRY_USDT, CATEGORY

async def wallet_equity_usdt() -> Decimal:
    try:
        r = await BybitClient().wallet_balance("USDT")
        if r.get("retCode") == 0:
            return Decimal(r["result"]["list"][0]["totalEquity"])
        else:
            print(f"⚠️  API error getting wallet balance: {r.get('retMsg')} (Code: {r.get('retCode')})")
            return Decimal("1000")  # Default $1000 balance
    except Exception as e:
        print(f"⚠️  Failed to get wallet balance: {e}")
        # Return a default balance for testing purposes
        return Decimal("1000")  # Default $1000 balance

async def qty_for_2pct_risk(category, symbol, entry, sl, risk_pct=Decimal("0.02")) -> Decimal:
    """
    Return exchange-quantized qty such that (risk_pct of balance) is lost if SL hits.
    Assumes linear USDT perps; position value = qty * entry_price; PnL per tick = qty.
    """
    eq = await wallet_equity_usdt()
    risk_usdt = eq * risk_pct
    dist = abs(Decimal(str(entry)) - Decimal(str(sl)))
    if dist <= 0:
        return Decimal("0")
    return await q_qty(category, symbol, risk_usdt / dist)

async def qty_for_im_step(category, symbol, entry, leverage, im_step=Decimal("20")) -> Decimal:
    return await q_qty(category, symbol, (im_step * Decimal(leverage)) / Decimal(str(entry)))

async def qty_from_im(category: str, symbol: str, entry_price: Decimal, leverage: Decimal, im_usdt: Decimal) -> Decimal:
    """
    For perps: notional = qty * price
    Initial margin ~= notional / leverage  => qty = (im * leverage) / price
    """
    raw = (im_usdt * leverage) / entry_price
    q = await q_qty(category, symbol, raw)
    return await ensure_min_notional(category, symbol, entry_price, q)

async def split_dual_qty(category: str, symbol: str, entry1: Decimal, entry2: Decimal, leverage: Decimal):
    """
    Requirement #1/#12/#22: 20 USDT per entry (dual entries 50/50).
    If only one entry is given, caller will synthesize the second at ±0.1% first.
    """
    im = Decimal(str(IM_PER_ENTRY_USDT))
    q1 = await qty_from_im(category, symbol, entry1, leverage, im)
    q2 = await qty_from_im(category, symbol, entry2, leverage, im)
    return q1, q2