"""
Complete message templates matching client specification.
All messages show channel NAME (not number) and include Bybit confirmations where required.
"""

from datetime import datetime
from typing import List, Optional
from decimal import Decimal

def _time() -> str:
    """Current time in readable format"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _pct(entry: Decimal, price: Decimal) -> str:
    """Calculate percentage difference"""
    if entry == 0: return "0.00"
    pct = abs((price - entry) / entry * Decimal("100"))
    return f"{pct:.2f}"

# ============================================================================
# 1) SIGNAL RECEIVED & COPIED (3 modes: Swing/Dynamic/Fast)
# ============================================================================

def signal_received_swing(symbol: str, channel_name: str, entry: str, tps: List[str], sl: str, im: float) -> str:
    return f"""**✅ Signal mottagen & kopierad**
🕒 Tid: {_time()}
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: LONG
📍 Typ: Swing

⚙️ Hävstång: x6
💰 IM: {im:.2f} USDT

**✅ Signal received & copied**
🕒 Time: {_time()}
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Direction: LONG
📍 Type: Swing

⚙️ Leverage: x6
💰 IM: {im:.2f} USDT"""

def signal_received_dynamic(symbol: str, channel_name: str, direction: str, entry: str, 
                           tps: List[str], sl: str, leverage: float, im: float) -> str:
    tp_lines_sv = "\n".join([f"🎯 TP{i}: {tp}" for i, tp in enumerate(tps, 1)])
    tp_lines_en = "\n".join([f"🎯 TP{i}: {tp}" for i, tp in enumerate(tps, 1)])
    
    return f"""**✅ Signal mottagen & kopierad**
🕒 Tid: {_time()}
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}

💥 Entry: {entry}
{tp_lines_sv}
🚩 SL: {sl}

⚙️ Hävstång: Dynamisk {leverage:.2f}x
💰 IM: {im:.2f} USDT

**✅ Signal received & copied**
🕒 Time: {_time()}
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Direction: {direction}

💥 Entry: {entry}
{tp_lines_en}
🚩 SL: {sl}

⚙️ Leverage: Dynamic {leverage:.2f}x
💰 IM: {im:.2f} USDT"""

def signal_received_fast(symbol: str, channel_name: str, direction: str, entry: str,
                        tps: List[str], sl: str, im: float) -> str:
    tp_lines_sv = "\n".join([f"🎯 TP{i}: {tp}" for i, tp in enumerate(tps, 1)])
    tp_lines_en = "\n".join([f"🎯 TP{i}: {tp}" for i, tp in enumerate(tps, 1)])
    
    return f"""**✅ Signal mottagen & kopierad**
🕒 Tid: {_time()}
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}

💥 Entry: {entry}
{tp_lines_sv}
🚩 SL: {sl}

⚙️ Hävstång: Fast x10
💰 IM: {im:.2f} USDT

**✅ Signal received & copied**
🕒 Time: {_time()}
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Direction: {direction}

💥 Entry: {entry}
{tp_lines_en}
🚩 SL: {sl}

⚙️ Leverage: Fast x10
💰 IM: {im:.2f} USDT"""

# ============================================================================
# 2) ORDER PLACED (with Bybit confirmations)
# ============================================================================

def order_placed(symbol: str, channel_name: str, direction: str, mode: str,
                entry: str, tps: List[str], sl: str, leverage: float, 
                im_actual: float, order_id: str) -> str:
    """
    MUST confirm from Bybit: IM, Order-ID, Post-Only flags
    Note: Entry orders are NOT reduce-only, only TP/SL orders are
    """
    # Format leverage display with decimals for DYNAMIC mode
    if mode == "FAST":
        lev_display_sv = f"Fast x{int(leverage)}"
        lev_display_en = f"Fast x{int(leverage)}"
    elif mode == "DYNAMIC":
        lev_display_sv = f"Dynamisk {leverage:.2f}x"
        lev_display_en = f"Dynamic {leverage:.2f}x"
    else:  # SWING
        lev_display_sv = "Swing x6"
        lev_display_en = "Swing x6"
    
    tp_lines_sv = "\n".join([f"🎯 TP{i}: {tp}" for i, tp in enumerate(tps, 1)])
    tp_lines_en = "\n".join([f"🎯 TP{i}: {tp}" for i, tp in enumerate(tps, 1)])
    
    return f"""✅ Order placerad – {mode}
🕒 Tid: {_time()}
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}

💥 Entry: {entry}
{tp_lines_sv}
🚩 SL: {sl}

⚙️ Hävstång: {lev_display_sv}
💰 IM: {im_actual:.2f} USDT [Bybit bekräftad]
☑️ Post-Only (Entry orders)
🔑 Order-ID: {order_id}

✅ Order placed – {mode}
🕒 Time: {_time()}
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Direction: {direction}

💥 Entry: {entry}
{tp_lines_en}
🚩 SL: {sl}

⚙️ Leverage: {lev_display_en}
💰 IM: {im_actual:.2f} USDT [Bybit confirmed]
☑️ Post-Only (Entry orders)
🔑 Order-ID: {order_id}"""

# ============================================================================
# 3) POSITION OPENED (with Bybit confirmations)
# ============================================================================

def position_opened(symbol: str, channel_name: str, direction: str, mode: str,
                   avg_entry: str, size: str, leverage: float, im_actual: float) -> str:
    """Position opened and confirmed by Bybit"""
    lev_display = f"x{int(leverage)}" if mode == "FAST" else f"Dynamisk {leverage:.2f}x" if mode == "DYNAMIC" else "x6"
    
    return f"""✅ Position öppnad – {mode}
🕒 Tid: {_time()}
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}

💥 Genomsnittligt Entry: {avg_entry} [Bybit bekräftad]
💵 Kvantitet: {size} [Bybit bekräftad]
⚙️ Hävstång: {lev_display}
💰 IM: {im_actual:.2f} USDT [Bybit bekräftad]

✅ Position opened – {mode}
🕒 Time: {_time()}
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Direction: {direction}

💥 Average Entry: {avg_entry} [Bybit confirmed]
💵 Quantity: {size} [Bybit confirmed]
⚙️ Leverage: {lev_display}
💰 IM: {im_actual:.2f} USDT [Bybit confirmed]"""

# ============================================================================
# 4) ENTRY 1 & 2 TAKEN (dual entry confirmation)
# ============================================================================

def entry_filled(symbol: str, channel_name: str, entry_no: int, price: str, 
                qty: str, im: float, im_total: float) -> str:
    """Individual entry fill confirmation"""
    return f"""📌 ENTRY {entry_no} TAGEN
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

💥 Entry: {price}
💵 Kvantitet: {qty}
💰 IM: {im:.2f} USDT (IM totalt: {im_total:.2f} USDT) [Bybit bekräftad]

📌 ENTRY {entry_no} TAKEN
📢 From channel: {channel_name}
📊 Symbol: {symbol}

💥 Entry: {price}
💵 Quantity: {qty}
💰 IM: {im:.2f} USDT (Total IM: {im_total:.2f} USDT) [Bybit confirmed]"""

# ============================================================================
# 5) MERGED POSITION SUMMARY
# ============================================================================

def position_merged(symbol: str, channel_name: str, entry1: str, entry2: str,
                   qty1: str, qty2: str, im1: float, im2: float,
                   avg_entry: str, total_qty: str, total_im: float) -> str:
    """Volume-weighted average of Entry 1 + Entry 2"""
    return f"""📌 Sammanställning av ENTRY 1 + ENTRY 2
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

📌 ENTRY 1
💥 Entry: {entry1}
💵 Kvantitet: {qty1}
💰 IM: {im1:.2f} USDT

📌 ENTRY 2
💥 Entry: {entry2}
💵 Kvantitet: {qty2}
💰 IM: {im2:.2f} USDT

📌 SAMMANSATT POSITION
💥 Genomsnittligt Entry: {avg_entry} [volymvägt]
💵 Total kvantitet: {total_qty}
💰 IM totalt: {total_im:.2f} USDT [Bybit bekräftad]

📌 Summary of ENTRY 1 + ENTRY 2
📢 From channel: {channel_name}
📊 Symbol: {symbol}

📌 ENTRY 1
💥 Entry: {entry1}
💵 Quantity: {qty1}
💰 IM: {im1:.2f} USDT

📌 ENTRY 2
💥 Entry: {entry2}
💵 Quantity: {qty2}
💰 IM: {im2:.2f} USDT

📌 MERGED POSITION
💥 Average Entry: {avg_entry} [volume-weighted]
💵 Total quantity: {total_qty}
💰 Total IM: {total_im:.2f} USDT [Bybit confirmed]"""

# ============================================================================
# 6) TAKE PROFIT HIT (TP1-4, only up to +6.1%)
# ============================================================================

def tp_hit_detailed(symbol: str, channel_name: str, direction: str, tp_no: int,
                   price: str, qty_closed: str, pct_of_position: float,
                   result_pct: float, result_usdt: float) -> str:
    """
    Take profit hit with detailed P&L (including leverage effect)
    Note: Client wants result % to include leverage effect
    """
    return f"""🎯 TAKE PROFIT {tp_no} TAGEN
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Sida: {direction}

📍 TP{tp_no}: {price} [Bybit bekräftad]
💵 Stängd kvantitet: {qty_closed} ({pct_of_position:.0f}% av positionen)
📊 Resultat: {result_pct:.2f}% | {result_usdt:.2f} USDT [inkl. hävstång]

🎯 TAKE PROFIT {tp_no} HIT
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Side: {direction}

📍 TP{tp_no}: {price} [Bybit confirmed]
💵 Closed quantity: {qty_closed} ({pct_of_position:.0f}% of position)
📊 Result: {result_pct:.2f}% | {result_usdt:.2f} USDT [incl. leverage]"""

# ============================================================================
# 7) PYRAMID MESSAGES (7 types)
# ============================================================================

def pyramid_step(symbol: str, channel_name: str, direction: str, step_no: int,
                trigger_pct: float, price: str, action: str, qty_added: str = None,
                im_added: float = None, im_total: float = None, 
                new_leverage: int = None) -> str:
    """Pyramid step messages"""
    
    if action == "check_im":
        detail_sv = f"Kontroll: IM är {im_total:.2f} USDT"
        detail_en = f"Check: IM is {im_total:.2f} USDT"
    elif action == "sl_to_be":
        detail_sv = "🛡️ SL flyttas till Break Even [Bybit bekräftad]"
        detail_en = "🛡️ SL moved to Break Even [Bybit confirmed]"
    elif action == "max_leverage":
        detail_sv = f"⚙️ Hävstång höjd till {new_leverage}x [Bybit bekräftad]"
        detail_en = f"⚙️ Leverage raised to {new_leverage}x [Bybit confirmed]"
    elif action == "add_im":
        detail_sv = f"💰 IM-påfyllnad: +{im_added:.2f} USDT (IM totalt: {im_total:.0f} USDT) [Bybit bekräftad]"
        detail_en = f"💰 IM added: +{im_added:.2f} USDT (Total IM: {im_total:.0f} USDT) [Bybit confirmed]"
    else:
        detail_sv = detail_en = ""

    qty_line_sv = f"💵 Tillagd kvantitet: {qty_added} [Bybit bekräftad]" if qty_added else ""
    qty_line_en = f"💵 Added quantity: {qty_added} [Bybit confirmed]" if qty_added else ""

    return f"""📈 PYRAMID Steg {step_no}
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}

💥 Pris: {price} (+{trigger_pct:.1f}%) [Bybit bekräftad]
{qty_line_sv}
{detail_sv}

📈 PYRAMID Step {step_no}
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Direction: {direction}

💥 Price: {price} (+{trigger_pct:.1f}%) [Bybit confirmed]
{qty_line_en}
{detail_en}"""

# ============================================================================
# 8) TRAILING STOP ACTIVATED
# ============================================================================

def trailing_activated(symbol: str, channel_name: str, direction: str,
                      trigger_pct: float, distance_pct: float, new_sl: str) -> str:
    return f"""🔄 TRAILING STOP AKTIVERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}

📍 Trigger: +{trigger_pct:.1f}%
📍 Avstånd: {distance_pct:.1f}% bakom pris
📍 Ny SL: {new_sl} [Bybit bekräftad]

🔄 TRAILING STOP ACTIVATED
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Direction: {direction}

📍 Trigger: +{trigger_pct:.1f}%
📍 Distance: {distance_pct:.1f}% behind price
📍 New SL: {new_sl} [Bybit confirmed]"""

# ============================================================================
# 9) BREAK-EVEN ADJUSTED
# ============================================================================

def breakeven_adjusted(symbol: str, channel_name: str, sl_moved_to: str) -> str:
    return f"""⚖️ BREAK-EVEN JUSTERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

📍 SL flyttad till: {sl_moved_to} [Bybit bekräftad]

⚖️ BREAK-EVEN ADJUSTED
📢 From channel: {channel_name}
📊 Symbol: {symbol}

📍 SL moved to: {sl_moved_to} [Bybit confirmed]"""

# ============================================================================
# 10) HEDGE OPENED/CLOSED
# ============================================================================

def hedge_opened(symbol: str, channel_name: str, old_side: str, new_side: str,
                entry: str, leverage: int, im: float) -> str:
    return f"""🛡️ HEDGE / VÄNDNING AKTIVERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

📈 Tidigare position: {old_side} (stängd)
📉 Ny motriktad position: {new_side}
💥 Entry: {entry}

⚙️ Hävstång: {leverage}x
💰 IM: {im:.2f} USDT [Bybit bekräftad]

🛡️ HEDGE / REVERSAL ACTIVATED
📢 From channel: {channel_name}
📊 Symbol: {symbol}

📈 Previous position: {old_side} (closed)
📉 New opposite position: {new_side}
💥 Entry: {entry}

⚙️ Leverage: {leverage}x
💰 IM: {im:.2f} USDT [Bybit confirmed]"""

def hedge_closed(symbol: str, channel_name: str, side: str, exit_price: str, leverage: int) -> str:
    return f"""🛡️ HEDGE / VÄNDNING AVSLUTAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

📈 Stängd position: {side}
💥 Stängningspris: {exit_price}

⚙️ Hävstång (avslutad): {leverage}x

🛡️ HEDGE / REVERSAL CLOSED
📢 From channel: {channel_name}
📊 Symbol: {symbol}

📈 Closed position: {side}
💥 Exit price: {exit_price}

⚙️ Leverage (closed): {leverage}x"""

# ============================================================================
# 11) RE-ENTRY ACTIVATED/CLOSED
# ============================================================================

def reentry_activated(symbol: str, channel_name: str, direction: str, attempt: int,
                     entry: str, leverage: int, im: float, im_total: float) -> str:
    return f"""♻️ RE-ENTRY / ÅTERINTRÄDE #{attempt} AKTIVERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Sida: {direction}

💥 Entry: {entry}
⚙️ Hävstång: {leverage}x
💰 IM: {im:.2f} USDT (IM totalt: {im_total:.2f} USDT)

♻️ RE-ENTRY / RE-ENTRANCE #{attempt} ACTIVATED
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Side: {direction}

💥 Entry: {entry}
⚙️ Leverage: {leverage}x
💰 IM: {im:.2f} USDT (Total IM: {im_total:.2f} USDT)"""

def reentry_closed(symbol: str, channel_name: str, direction: str, exit_price: str,
                  pnl_usdt: float, pnl_pct: float, leverage: int) -> str:
    return f"""♻️ RE-ENTRY / ÅTERINTRÄDE AVSLUTAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Sida: {direction}

💥 Exit: {exit_price}
📉 Resultat: {pnl_usdt:.2f} USDT ({pnl_pct:.2f}%)
⚙️ Hävstång (avslutad): {leverage}x

♻️ RE-ENTRY / RE-ENTRANCE CLOSED
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Side: {direction}

💥 Exit: {exit_price}
📉 Result: {pnl_usdt:.2f} USDT ({pnl_pct:.2f}%)
⚙️ Leverage (closed): {leverage}x"""

# ============================================================================
# 12) STOP-LOSS HIT
# ============================================================================

def stop_loss_hit(symbol: str, channel_name: str, direction: str, sl_price: str,
                 qty_closed: str, result_pct: float, result_usdt: float) -> str:
    """Stop-loss triggered"""
    return f"""🚩 STOP LOSS TRÄFFAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Sida: {direction}

📍 SL: {sl_price} [Bybit bekräftad]
💵 Stängd kvantitet: {qty_closed} (100%)
📊 Resultat: {result_pct:.2f}% | {result_usdt:.2f} USDT

🔁 Återinträdeslogik: aktiverad – ny signal tas vid bekräftad trendvändning

🚩 STOP LOSS HIT
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Side: {direction}

📍 SL: {sl_price} [Bybit confirmed]
💵 Closed quantity: {qty_closed} (100%)
📊 Result: {result_pct:.2f}% | {result_usdt:.2f} USDT

🔁 Re-entry logic: activated – new signal on confirmed trend reversal"""

# ============================================================================
# 13) POSITION CLOSED (final)
# ============================================================================

def position_closed(symbol: str, channel_name: str, direction: str, 
                   qty_closed: str, exit_price: str,
                   result_pct: float, result_usdt: float, pol_usdt: float) -> str:
    """Final position close with P&L including leverage"""
    return f"""✅ POSITION STÄNGD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Sida: {direction}

💵 Stängd kvantitet: {qty_closed} (100%)
📍 Exit: {exit_price}

📊 Resultat: {result_pct:.2f}% [inkl. hävstång]
📊 Resultat: {result_usdt:.2f} USDT [inkl. hävstång]
📊 P&L: {pol_usdt:.2f} USDT

✅ POSITION CLOSED
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Side: {direction}

💵 Closed quantity: {qty_closed} (100%)
📍 Exit: {exit_price}

📊 Result: {result_pct:.2f}% [incl. leverage]
📊 Result: {result_usdt:.2f} USDT [incl. leverage]
📊 P&L: {pol_usdt:.2f} USDT"""

# ============================================================================
# ERROR MESSAGES (14 types)
# ============================================================================

def error_signal_invalid(symbol: str, channel_name: str) -> str:
    return f"""**❌ SIGNAL OGILTIG ❌**
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

📍 Fel: Ofullständig eller felaktig signal mottagen

**❌ SIGNAL INVALID ❌**
📢 From channel: {channel_name}
📊 Symbol: {symbol}

📍 Error: Incomplete or invalid signal received"""

def error_order_failed(symbol: str, channel_name: str) -> str:
    return f"""**❌ ORDER MISSLYCKADES ❌**
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

📍 Fel: Order kunde inte placeras (kontrollera saldo eller parametrar)

**❌ ORDER FAILED ❌**
📢 From channel: {channel_name}
📊 Symbol: {symbol}

📍 Error: Order could not be placed (check balance or parameters)"""

def error_order_rejected(symbol: str, channel_name: str, reason: str = "") -> str:
    return f"""**❌ ORDER AVVISAD ❌**
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

📍 Fel: Ordern avvisades av Bybit {reason}

**❌ ORDER REJECTED ❌**
📢 From channel: {channel_name}
📊 Symbol: {symbol}

📍 Error: Order rejected by Bybit {reason}"""

def error_position_not_opened(symbol: str, channel_name: str) -> str:
    return f"""**❌ POSITION EJ ÖPPNAD ❌**
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

📍 Fel: Positionen kunde inte öppnas (otillräcklig IM eller fel hävstång)

**❌ POSITION NOT OPENED ❌**
📢 From channel: {channel_name}
📊 Symbol: {symbol}

📍 Error: Position could not be opened (insufficient IM or wrong leverage)"""

def error_insufficient_balance(symbol: str, channel_name: str) -> str:
    return f"""**❌ OTILLRÄCKLIG BALANS ❌**
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

📍 Fel: Kontosaldo räcker inte för denna order

**❌ INSUFFICIENT BALANCE ❌**
📢 From channel: {channel_name}
📊 Symbol: {symbol}

📍 Error: Account balance insufficient for this order"""

def error_api_failed(symbol: str, channel_name: str, error_code: str = "") -> str:
    return f"""**❌ API FEL ❌**
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

📍 Fel: Ingen kontakt med Bybit (kontrollera API-nyckel eller nätverk) {error_code}

**❌ API ERROR ❌**
📢 From channel: {channel_name}
📊 Symbol: {symbol}

📍 Error: No contact with Bybit (check API key or network) {error_code}"""

def error_order_deleted(symbol: str, channel_name: str) -> str:
    """Order not opened within 6 days - deleted per rules"""
    return f"""✔️ ORDER RADERAD ✔️
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

📍 Fel: Order ej öppnad inom tillåten tid (raderad enligt reglerna)

✔️ ORDER DELETED ✔️
📢 From channel: {channel_name}
📊 Symbol: {symbol}

📍 Info: Order not opened within allowed time (deleted per rules)"""

def error_symbol_invalid(symbol: str, channel_name: str, reason: str = "") -> str:
    """Symbol doesn't exist or not available on Bybit"""
    reason_text = f" ({reason})" if reason else ""
    return f"""**❌ SYMBOL OGILTIGT ❌**
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

📍 Fel: Symbol finns inte på Bybit eller fel marknadstyp{reason_text}
ℹ️ Tips: Detta är troligen en SPOT-signal men botten handlar FUTURES

**❌ SYMBOL INVALID ❌**
📢 From channel: {channel_name}
📊 Symbol: {symbol}

📍 Error: Symbol doesn't exist on Bybit or wrong market type{reason_text}
ℹ️ Tip: This is likely a SPOT signal but bot trades FUTURES"""

def position_merged(channel: str, symbol: str, side: str, qty: float, avg_entry: float, 
                   im_total: float, lev: float, mode: str) -> str:
    """Merged position message after both entries fill"""
    return f"""**✅ MERGED POSITION ✅**
🕒 Tid: {_time()}
📢 Från kanal: {channel}
📊 Symbol: {symbol}
📈 Riktning: {side}
📍 Typ: {mode}

💰 Kvantitet: {qty:.6f}
📍 Genomsnittlig Entry: {avg_entry:.6f}
💰 Total IM: {im_total:.2f} USDT
⚙️ Hävstång: {lev:.2f}x ({mode})
✅ Bybit bekräftad

**✅ MERGED POSITION ✅**
🕒 Time: {_time()}
📢 From channel: {channel}
📊 Symbol: {symbol}
📈 Direction: {side}
📍 Type: {mode}

💰 Quantity: {qty:.6f}
📍 Average Entry: {avg_entry:.6f}
💰 Total IM: {im_total:.2f} USDT
⚙️ Leverage: {lev:.2f}x ({mode})
✅ Bybit confirmed"""
