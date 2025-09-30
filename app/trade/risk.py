"""Risk management with 2% per trade and IM calculations."""

from decimal import Decimal
from app.bybit.client import BybitClient
from app.core.precision import q_qty

async def wallet_equity_usdt() -> Decimal:
    """Get wallet equity in USDT."""
    r = await BybitClient().wallet_balance("USDT")
    return Decimal(r["result"]["list"][0]["totalEquity"])

async def qty_for_2pct_risk(category, symbol, entry, sl, risk_pct=Decimal("0.02")) -> Decimal:
    """Calculate quantity for 2% risk per trade."""
    eq = await wallet_equity_usdt()
    risk_usdt = eq * risk_pct
    dist = abs(Decimal(str(entry)) - Decimal(str(sl)))
    if dist <= 0:
        return Decimal("0")
    return await q_qty(category, symbol, risk_usdt / dist)

async def qty_for_im_step(category, symbol, entry, leverage, im_step=Decimal("20")) -> Decimal:
    """Calculate quantity for IM step (pyramid adds)."""
    return await q_qty(category, symbol, (im_step * Decimal(leverage)) / Decimal(str(entry)))