from __future__ import annotations
from decimal import Decimal


def leverage_set(symbol: str, lev: int, source: str | None = None) -> str:
    src = f"\nKälla/Source: {source}" if source else ""
    return (
        f"🔧 Hävstång satt • {symbol} • x{lev}{src}\n"
        f"🔧 Leverage set • {symbol} • x{lev}{src}"
    )


def entries_placed(symbol: str, order_ids: list[str], source: str | None = None) -> str:
    ids = ", ".join(order_ids)
    src = f"\nKälla/Source: {source}" if source else ""
    return (
        f"📥 Order lagd • {symbol}{src}\nOrder-ID: {ids}\n"
        f"📥 Entry orders placed • {symbol}{src}\nOrder IDs: {ids}"
    )


def position_confirmed(symbol: str, size: Decimal, avg_entry: Decimal | None = None, source: str | None = None) -> str:
    avg_text = f"\nVWAP: {avg_entry}" if avg_entry is not None else ""
    src = f"\nKälla/Source: {source}" if source else ""
    return (
        f"✅ Position bekräftad • {symbol}{src}\nStorlek: {size}{avg_text}\n"
        f"✅ Position confirmed • {symbol}{src}\nSize: {size}{avg_text}"
    )


def tpsl_placed(symbol: str, tp_count: int, sl_price: str, source: str | None = None) -> str:
    src = f"\nKälla/Source: {source}" if source else ""
    return (
        f"🎯 TP/SL placerade • {symbol}{src}\nTP: {tp_count} st • SL: {sl_price}\n"
        f"🎯 TP & SL placed • {symbol}{src}\nTP: {tp_count} • SL: {sl_price}"
    )


def tp_hit(symbol: str, price: str, source: str | None = None) -> str:
    src = f"\nKälla/Source: {source}" if source else ""
    return (
        f"🎯 TP träffad • {symbol}{src}\nPris: {price}\n"
        f"🎯 TP hit • {symbol}{src}\nPrice: {price}"
    )


def sl_hit(symbol: str, price: str, source: str | None = None) -> str:
    src = f"\nKälla/Source: {source}" if source else ""
    return (
        f"🛑 SL träffad • {symbol}{src}\nPris: {price}\n"
        f"🛑 Stop-loss hit • {symbol}{src}\nPrice: {price}"
    )


def pyramid_added(symbol: str, price: str, qty: str) -> str:
    return (
        f"📈 Pyramid-order lagt • {symbol}\nPris: {price} • Kvantitet: {qty}\n"
        f"📈 Pyramid add placed • {symbol}\nPrice: {price} • Qty: {qty}"
    )


def trailing_moved(symbol: str, price: str) -> str:
    return (
        f"🔄 SL flyttad • {symbol}\nMark: {price}\n"
        f"🔄 Trailing stop moved • {symbol}\nMark: {price}"
    )


def hedge_triggered(symbol: str) -> str:
    return (
        f"⚠️ Hedge utlöst • {symbol}\n"
        f"⚠️ Hedge triggered • {symbol}"
    )


def daily_report(ts: str, closed: int, pnl: float) -> str:
    return (
        f"📊 Daglig rapport {ts}\nAvslutade affärer: {closed}\nRealiserad PnL: {pnl:.2f} USDT\n"
        f"📊 Daily Report {ts}\nClosed trades: {closed}\nRealized PnL: {pnl:.2f} USDT"
    )


def weekly_report(ts: str, closed: int, pnl: float) -> str:
    return (
        f"📊 Veckorapport {ts}\nAvslutade affärer: {closed}\nRealiserad PnL: {pnl:.2f} USDT\n"
        f"📊 Weekly Report {ts}\nClosed trades: {closed}\nRealized PnL: {pnl:.2f} USDT"
    )

