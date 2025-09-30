from typing import Iterable

def _join(v: Iterable) -> str:
    return ", ".join(map(str, v))

def signal_received(sig: dict) -> str:
    cn = sig.get("channel_name", "?")
    return (f"📡 Signal mottagen {sig['symbol']} {sig['direction']} • Källa: {cn}\n"
            f"📡 Signal received {sig['symbol']} {sig['direction']} • Source: {cn}")

def leverage_set(symbol, lev, channel_name, mode=None):
    m = f" {mode}" if mode else ""
    return (f"🔧 Hävstång{m} satt ({symbol} x{lev}) • Källa: {channel_name}\n"
            f"🔧 Leverage{m} set ({symbol} x{lev}) • Source: {channel_name}")

def entries_placed(symbol, entries, trade_id, channel_name, post_only=True):
    po = "PostOnly" if post_only else ""
    return (f"📥 Order lagda {symbol} @ [{_join(entries)}] {po} • ID: {trade_id} • Källa: {channel_name}\n"
            f"📥 Entry orders placed {symbol} @ [{_join(entries)}] {po} • ID: {trade_id} • Source: {channel_name}")

def position_confirmed(symbol, size, avg, channel_name):
    return (f"✅ Position bekräftad {symbol} qty={size} avg={avg} • Källa: {channel_name}\n"
            f"✅ Position confirmed {symbol} qty={size} avg={avg} • Source: {channel_name}")

def tpsl_placed(symbol, tps, sl, channel_name, reduce_only=True, trigger_by="MarkPrice"):
    ro = "ReduceOnly" if reduce_only else ""
    return (f"🎯 TP/SL placerade TP=[{_join(tps)}] SL={sl} {ro} ({trigger_by}) • Källa: {channel_name}\n"
            f"🎯 TP/SL placed TP=[{_join(tps)}] SL={sl} {ro} ({trigger_by}) • Source: {channel_name}")

def tp_hit(symbol, tp_no, price, channel_name):
    return (f"🎯 TP{tp_no} träffad {symbol} @ {price} • Källa: {channel_name}\n"
            f"🎯 TP{tp_no} hit {symbol} @ {price} • Source: {channel_name}")

def sl_hit(symbol, price, channel_name):
    return (f"🛑 SL träffad {symbol} @ {price} • Källa: {channel_name}\n"
            f"🛑 Stop-loss hit {symbol} @ {price} • Source: {channel_name}")

def pyramid_added(symbol, link_id, qty, price, im_usdt, channel_name):
    return (f"➕ Pyramid {link_id} qty={qty} @ {price} (IM={im_usdt} USDT) • Källa: {channel_name}\n"
            f"➕ Pyramid {link_id} qty={qty} @ {price} (IM={im_usdt} USDT) • Source: {channel_name}")

def trailing_moved(symbol, new_sl, channel_name):
    return (f"⛳ Trailing flyttade SL till ~B/E @ {new_sl} • Källa: {channel_name}\n"
            f"⛳ Trailing moved SL to ~B/E @ {new_sl} • Source: {channel_name}")

def hedge_flip(symbol, flip_no, old_dir, new_dir, price, channel_name):
    return (f"♻️ Hedge flip {flip_no} {symbol} {old_dir}→{new_dir} @ {price} • Källa: {channel_name}\n"
            f"♻️ Hedge flip {flip_no} {symbol} {old_dir}→{new_dir} @ {price} • Source: {channel_name}")

def tp2_be(symbol, new_sl, channel_name):
    return (f"🧷 TP2 → SL till B/E±0.0015% @ {new_sl} • Källa: {channel_name}\n"
            f"🧷 TP2 → SL to B/E±0.0015% @ {new_sl} • Source: {channel_name}")

def daily_report(ts, trades, realized_pnl, win_rate, errors, top_symbols):
    ts2 = f"{ts}"
    tops = ", ".join(f"{s}:{pnl:.2f}" for s,pnl in top_symbols[:5]) if top_symbols else "-"
    return (f"📊 Daglig rapport {ts2}\n"
            f"• Affärer: {trades}\n• Win-rate: {win_rate:.1f}%\n• Realiserad PnL: {realized_pnl:.2f} USDT\n• Fel: {errors}\n• Topp: {tops}\n—\n"
            f"📊 Daily Report {ts2}\n"
            f"• Trades: {trades}\n• Win-rate: {win_rate:.1f}%\n• Realized PnL: {realized_pnl:.2f} USDT\n• Errors: {errors}\n• Top: {tops}")

def weekly_report(ts, trades, realized_pnl, win_rate, errors, top_symbols):
    ts2 = f"{ts}"
    tops = ", ".join(f"{s}:{pnl:.2f}" for s,pnl in top_symbols[:5]) if top_symbols else "-"
    return (f"📊 Veckorapport {ts2}\n"
            f"• Affärer: {trades}\n• Win-rate: {win_rate:.1f}%\n• Realiserad PnL: {realized_pnl:.2f} USDT\n• Fel: {errors}\n• Topp: {tops}\n—\n"
            f"📊 Weekly Report {ts2}\n"
            f"• Trades: {trades}\n• Win-rate: {win_rate:.1f}%\n• Realized PnL: {realized_pnl:.2f} USDT\n• Errors: {errors}\n• Top: {tops}")