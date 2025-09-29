from decimal import Decimal
from app.bybit_client import BybitClient
from app.core.precision import q_qty


def wallet_equity_usdt() -> Decimal:
    # Placeholder: adjust to real wallet endpoint/shape if added later
    # For now, assume a fixed demo equity if API not available
    try:
        b = BybitClient().get_wallet_balance("USDT")
        # Expected shape: {"result":{"list":[{"totalEquity":"..."}]}}
        equity_str = (b.get("result", {}).get("list") or [{}])[0].get("totalEquity")
        if equity_str is None:
            return Decimal("1000")
        return Decimal(str(equity_str))
    except Exception:
        return Decimal("1000")


def qty_for_2pct_risk(symbol: str, entry: str | float, sl: str | float, risk_pct: Decimal = Decimal("0.02")) -> Decimal:
    entry_d = Decimal(str(entry))
    sl_d = Decimal(str(sl))
    distance = abs(entry_d - sl_d)
    if distance == 0:
        return Decimal("0")
    equity = wallet_equity_usdt()
    risk_usdt = equity * risk_pct
    raw_qty = risk_usdt / distance
    return q_qty(symbol, raw_qty)


def qty_for_im_step(symbol: str, entry: str | float, leverage: int | str, im_step: Decimal = Decimal("20")) -> Decimal:
    entry_d = Decimal(str(entry))
    lev_d = Decimal(str(leverage))
    if entry_d == 0:
        return Decimal("0")
    raw = (im_step * lev_d) / entry_d
    return q_qty(symbol, raw)

