"""Swedish/English templates with channel names."""

def signal_received(sig):
    return f"📡 Signal mottagen {sig['symbol']} {sig['direction']} • Källa: {sig.get('channel_name', '?')}"

def leverage_set(symbol, lev, channel_name):
    return f"🔧 Hävstång satt ({symbol} x{lev}) • Källa: {channel_name}"

def entries_placed(symbol, entries, trade_id, channel_name):
    return f"📥 Order lagda {symbol} @ {entries} • Källa: {channel_name}\nID: {trade_id}"

def position_confirmed(symbol, size, avg, channel_name):
    return f"✅ Position bekräftad {symbol} qty={size} avg={avg} • Källa: {channel_name}"

def tpsl_placed(symbol, tps, sl, channel_name):
    return f"🎯 TP/SL placerade TP={tps} SL={sl} • Källa: {channel_name}"

def daily_report(ts, trades, realized_pnl):
    return f"📊 Daglig rapport ({ts})\nAffärer: {trades}\nRealiserad PnL: {realized_pnl}"

def weekly_report(ts, trades, realized_pnl):
    return f"📊 Veckorapport ({ts})\nAffärer: {trades}\nRealiserad PnL: {realized_pnl}"