from __future__ import annotations
from decimal import Decimal


def leverage_set(symbol: str, lev: int) -> str:
    return (
        f"🔧 Hävstång satt • {symbol} • x{lev}\n"
        f"🔧 Leverage set • {symbol} • x{lev}"
    )


def entries_placed(symbol: str, order_ids: list[str]) -> str:
    ids = ", ".join(order_ids)
    return (
        f"📥 Order lagd • {symbol}\nOrder-ID: {ids}\n"
        f"📥 Entry orders placed • {symbol}\nOrder IDs: {ids}"
    )


def position_confirmed(symbol: str, size: Decimal, avg_entry: Decimal | None = None) -> str:
    avg_text = f"\nVWAP: {avg_entry}" if avg_entry is not None else ""
    return (
        f"✅ Position bekräftad • {symbol}\nStorlek: {size}{avg_text}\n"
        f"✅ Position confirmed • {symbol}\nSize: {size}{avg_text}"
    )


def tpsl_placed(symbol: str, tp_count: int, sl_price: str) -> str:
    return (
        f"🎯 TP/SL placerade • {symbol}\nTP: {tp_count} st • SL: {sl_price}\n"
        f"🎯 TP & SL placed • {symbol}\nTP: {tp_count} • SL: {sl_price}"
    )


def tp_hit(symbol: str, price: str) -> str:
    return (
        f"🎯 TP träffad • {symbol}\nPris: {price}\n"
        f"🎯 TP hit • {symbol}\nPrice: {price}"
    )


def sl_hit(symbol: str, price: str) -> str:
    return (
        f"🛑 SL träffad • {symbol}\nPris: {price}\n"
        f"🛑 Stop-loss hit • {symbol}\nPrice: {price}"
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

