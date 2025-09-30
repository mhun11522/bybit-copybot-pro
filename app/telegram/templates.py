from __future__ import annotations
from decimal import Decimal
from datetime import datetime
from typing import List, Optional, Dict


def _calc_pct(entry: Decimal, target: Decimal) -> str:
    """Calculate percentage change."""
    if entry == 0:
        return "0.00"
    pct = ((target - entry) / entry) * 100
    return f"{pct:.2f}"


def signal_received(symbol: str, direction: str, mode: str, channel_name: str, 
                   entries: List[Decimal], tps: List[Decimal], sl: Decimal, 
                   leverage: int, im: Decimal) -> str:
    """1. Signal received & copied message."""
    if mode == "SWING":
        return f"""✅ Signal mottagen & kopierad 
🕒 Tid: {datetime.now().strftime('%H:%M:%S')}
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}
📍 Typ: Swing

⚙️ Hävstång: x{leverage}
💰 IM: {im} USDT

✅ Signal received & copied 
🕒 Time: {datetime.now().strftime('%H:%M:%S')}
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Direction: {direction}
📍 Type: Swing

⚙️ Leverage: x{leverage}
💰 IM: {im} USDT"""
    
    elif mode == "FIXED":
        entries_str = ", ".join([str(e) for e in entries])
        return f"""✅ Signal mottagen & kopierad 
🕒 Tid: {datetime.now().strftime('%H:%M:%S')}
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}

💥 Entry: {entries_str}
🎯 TP1: {tps[0] if tps else 'N/A'} ({_calc_pct(entries[0], tps[0]) if tps and entries else 'N/A'}%)
🎯 TP2: {tps[1] if len(tps) > 1 else 'N/A'} ({_calc_pct(entries[0], tps[1]) if len(tps) > 1 and entries else 'N/A'}%)
🎯 TP3: {tps[2] if len(tps) > 2 else 'N/A'} ({_calc_pct(entries[0], tps[2]) if len(tps) > 2 and entries else 'N/A'}%)
🎯 TP4: {tps[3] if len(tps) > 3 else 'N/A'} ({_calc_pct(entries[0], tps[3]) if len(tps) > 3 and entries else 'N/A'}%)
🚩 SL: {sl} ({_calc_pct(entries[0], sl) if entries else 'N/A'}%)

⚙️ Hävstång: Fast x{leverage}
💰 IM: {im} USDT

✅ Signal received & copied 
🕒 Time: {datetime.now().strftime('%H:%M:%S')}
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Direction: {direction}

💥 Entry: {entries_str}
🎯 TP1: {tps[0] if tps else 'N/A'} ({_calc_pct(entries[0], tps[0]) if tps and entries else 'N/A'}%)
🎯 TP2: {tps[1] if len(tps) > 1 else 'N/A'} ({_calc_pct(entries[0], tps[1]) if len(tps) > 1 and entries else 'N/A'}%)
🎯 TP3: {tps[2] if len(tps) > 2 else 'N/A'} ({_calc_pct(entries[0], tps[2]) if len(tps) > 2 and entries else 'N/A'}%)
🎯 TP4: {tps[3] if len(tps) > 3 else 'N/A'} ({_calc_pct(entries[0], tps[3]) if len(tps) > 3 and entries else 'N/A'}%)
🚩 SL: {sl} ({_calc_pct(entries[0], sl) if entries else 'N/A'}%)

⚙️ Leverage: Fixed x{leverage}
💰 IM: {im} USDT"""
    
    else:  # DYNAMIC
        entries_str = ", ".join([str(e) for e in entries])
        return f"""✅ Signal mottagen & kopierad 
🕒 Tid: {datetime.now().strftime('%H:%M:%S')}
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}

💥 Entry: {entries_str}
🎯 TP1: {tps[0] if tps else 'N/A'} ({_calc_pct(entries[0], tps[0]) if tps and entries else 'N/A'}%)
🎯 TP2: {tps[1] if len(tps) > 1 else 'N/A'} ({_calc_pct(entries[0], tps[1]) if len(tps) > 1 and entries else 'N/A'}%)
🎯 TP3: {tps[2] if len(tps) > 2 else 'N/A'} ({_calc_pct(entries[0], tps[2]) if len(tps) > 2 and entries else 'N/A'}%)
🎯 TP4: {tps[3] if len(tps) > 3 else 'N/A'} ({_calc_pct(entries[0], tps[3]) if len(tps) > 3 and entries else 'N/A'}%)
🚩 SL: {sl} ({_calc_pct(entries[0], sl) if entries else 'N/A'}%)

⚙️ Hävstång: Dynamisk
💰 IM: {im} USDT

✅ Signal received & copied 
🕒 Time: {datetime.now().strftime('%H:%M:%S')}
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Direction: {direction}

💥 Entry: {entries_str}
🎯 TP1: {tps[0] if tps else 'N/A'} ({_calc_pct(entries[0], tps[0]) if tps and entries else 'N/A'}%)
🎯 TP2: {tps[1] if len(tps) > 1 else 'N/A'} ({_calc_pct(entries[0], tps[1]) if len(tps) > 1 and entries else 'N/A'}%)
🎯 TP3: {tps[2] if len(tps) > 2 else 'N/A'} ({_calc_pct(entries[0], tps[2]) if len(tps) > 2 and entries else 'N/A'}%)
🎯 TP4: {tps[3] if len(tps) > 3 else 'N/A'} ({_calc_pct(entries[0], tps[3]) if len(tps) > 3 and entries else 'N/A'}%)
🚩 SL: {sl} ({_calc_pct(entries[0], sl) if entries else 'N/A'}%)

⚙️ Leverage: Dynamic
💰 IM: {im} USDT"""


def order_placed(symbol: str, direction: str, mode: str, channel_name: str, 
                entries: List[Decimal], tps: List[Decimal], sl: Decimal, 
                leverage: int, im: Decimal, order_ids: List[str]) -> str:
    """2. Order placed message with Bybit confirmation."""
    order_ids_str = ", ".join(order_ids)
    
    if mode == "SWING":
        return f"""✅ Order placerad – Swing
🕒 Tid: {datetime.now().strftime('%H:%M:%S')}
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}
📍 Typ: Swing

⚙️ Hävstång: x{leverage}
💰 IM: {im} USDT MUST confirm from Bybit ({im} USDT example)
☑️ Post-Only | MUST confirm from Bybit
☑️ Reduce-Only MUST confirm from Bybit
🔑 Order-ID: {order_ids_str} MUST confirm from Bybit

✅ Order placed – Swing
🕒 Time: {datetime.now().strftime('%H:%M:%S')}
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Direction: {direction}
📍 Type: Swing

⚙️ Leverage: x{leverage}
💰 IM: {im} USDT MUST confirm from Bybit ({im} USDT example)
☑️ Post-Only | MUST confirm from Bybit
☑️ Reduce-Only MUST confirm from Bybit
🔑 Order ID: {order_ids_str} MUST confirm from Bybit"""
    
    elif mode == "FIXED":
        entries_str = ", ".join([str(e) for e in entries])
        return f"""✅ Order placerad – Fast
🕒 Tid: {datetime.now().strftime('%H:%M:%S')}
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}

💥 Entry: {entries_str}
🎯 TP1: {tps[0] if tps else 'N/A'} ({_calc_pct(entries[0], tps[0]) if tps and entries else 'N/A'}%)
🎯 TP2: {tps[1] if len(tps) > 1 else 'N/A'} ({_calc_pct(entries[0], tps[1]) if len(tps) > 1 and entries else 'N/A'}%)
🎯 TP3: {tps[2] if len(tps) > 2 else 'N/A'} ({_calc_pct(entries[0], tps[2]) if len(tps) > 2 and entries else 'N/A'}%)
🎯 TP4: {tps[3] if len(tps) > 3 else 'N/A'} ({_calc_pct(entries[0], tps[3]) if len(tps) > 3 and entries else 'N/A'}%)
🚩 SL: {sl} ({_calc_pct(entries[0], sl) if entries else 'N/A'}%)

⚙️ Hävstång: Fast x{leverage}
💰 IM: {im} USDT MUST confirm from Bybit ({im} USDT example)
☑️ Post-Only | MUST confirm from Bybit
☑️ Reduce-Only MUST confirm from Bybit
🔑 Order-ID: {order_ids_str} MUST confirm from Bybit

✅ Order placed – Fixed
🕒 Time: {datetime.now().strftime('%H:%M:%S')}
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Direction: {direction}

💥 Entry: {entries_str}
🎯 TP1: {tps[0] if tps else 'N/A'} ({_calc_pct(entries[0], tps[0]) if tps and entries else 'N/A'}%)
🎯 TP2: {tps[1] if len(tps) > 1 else 'N/A'} ({_calc_pct(entries[0], tps[1]) if len(tps) > 1 and entries else 'N/A'}%)
🎯 TP3: {tps[2] if len(tps) > 2 else 'N/A'} ({_calc_pct(entries[0], tps[2]) if len(tps) > 2 and entries else 'N/A'}%)
🎯 TP4: {tps[3] if len(tps) > 3 else 'N/A'} ({_calc_pct(entries[0], tps[3]) if len(tps) > 3 and entries else 'N/A'}%)
🚩 SL: {sl} ({_calc_pct(entries[0], sl) if entries else 'N/A'}%)

⚙️ Leverage: Fixed x{leverage}
💰 IM: {im} USDT MUST confirm from Bybit ({im} USDT example)
☑️ Post-Only | MUST confirm from Bybit
☑️ Reduce-Only MUST confirm from Bybit
🔑 Order ID: {order_ids_str} MUST confirm from Bybit"""
    
    else:  # DYNAMIC
        entries_str = ", ".join([str(e) for e in entries])
        return f"""✅ Order placerad – Dynamisk
🕒 Tid: {datetime.now().strftime('%H:%M:%S')}
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}

💥 Entry: {entries_str}
🎯 TP1: {tps[0] if tps else 'N/A'} ({_calc_pct(entries[0], tps[0]) if tps and entries else 'N/A'}%)
🎯 TP2: {tps[1] if len(tps) > 1 else 'N/A'} ({_calc_pct(entries[0], tps[1]) if len(tps) > 1 and entries else 'N/A'}%)
🎯 TP3: {tps[2] if len(tps) > 2 else 'N/A'} ({_calc_pct(entries[0], tps[2]) if len(tps) > 2 and entries else 'N/A'}%)
🎯 TP4: {tps[3] if len(tps) > 3 else 'N/A'} ({_calc_pct(entries[0], tps[3]) if len(tps) > 3 and entries else 'N/A'}%)
🚩 SL: {sl} ({_calc_pct(entries[0], sl) if entries else 'N/A'}%)

⚙️ Hävstång: Dynamisk
💰 IM: {im} USDT MUST confirm from Bybit ({im} USDT example)
☑️ Post-Only | MUST confirm from Bybit
☑️ Reduce-Only MUST confirm from Bybit
🔑 Order-ID: {order_ids_str} MUST confirm from Bybit

✅ Order placed – Dynamic
🕒 Time: {datetime.now().strftime('%H:%M:%S')}
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Direction: {direction}

💥 Entry: {entries_str}
🎯 TP1: {tps[0] if tps else 'N/A'} ({_calc_pct(entries[0], tps[0]) if tps and entries else 'N/A'}%)
🎯 TP2: {tps[1] if len(tps) > 1 else 'N/A'} ({_calc_pct(entries[0], tps[1]) if len(tps) > 1 and entries else 'N/A'}%)
🎯 TP3: {tps[2] if len(tps) > 2 else 'N/A'} ({_calc_pct(entries[0], tps[2]) if len(tps) > 2 and entries else 'N/A'}%)
🎯 TP4: {tps[3] if len(tps) > 3 else 'N/A'} ({_calc_pct(entries[0], tps[3]) if len(tps) > 3 and entries else 'N/A'}%)
🚩 SL: {sl} ({_calc_pct(entries[0], sl) if entries else 'N/A'}%)

⚙️ Leverage: Dynamic
💰 IM: {im} USDT MUST confirm from Bybit ({im} USDT example)
☑️ Post-Only | MUST confirm from Bybit
☑️ Reduce-Only MUST confirm from Bybit
🔑 Order ID: {order_ids_str} MUST confirm from Bybit"""


def position_opened(symbol: str, direction: str, mode: str, channel_name: str, 
                   size: Decimal, avg_entry: Decimal, leverage: int, im: Decimal) -> str:
    """3. Position opened message."""
    if mode == "SWING":
        return f"""✅ Position öppnad – Swing
🕒 Tid: {datetime.now().strftime('%H:%M:%S')}
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}
📍 Typ: Swing

⚙️ Hävstång: x{leverage}
💰 IM: {im} USDT MUST confirm from Bybit ({im} USDT example)
☑️ Post-Only | MUST confirm from Bybit
☑️ Reduce-Only MUST confirm from Bybit
🔑 Order-ID: MUST confirm from Bybit

✅ Position opened – Swing
🕒 Time: {datetime.now().strftime('%H:%M:%S')}
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Direction: {direction}
📍 Type: Swing

⚙️ Leverage: x{leverage}
💰 IM: {im} USDT MUST confirm from Bybit ({im} USDT example)
☑️ Post-Only | MUST confirm from Bybit
☑️ Reduce-Only MUST confirm from Bybit
🔑 Order ID: MUST confirm from Bybit"""
    
    else:  # DYNAMIC or FIXED
        mode_text = "Dynamisk" if mode == "DYNAMIC" else "Fast"
        mode_text_en = "Dynamic" if mode == "DYNAMIC" else "Fixed"
        leverage_text = "Dynamisk" if mode == "DYNAMIC" else f"Fast x{leverage}"
        leverage_text_en = "Dynamic" if mode == "DYNAMIC" else f"Fixed x{leverage}"
        
        return f"""✅ Position öppnad – {mode_text}
🕒 Tid: {datetime.now().strftime('%H:%M:%S')}
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}

💥 Entry: {avg_entry}
🎯 TP1: N/A
🎯 TP2: N/A
🎯 TP3: N/A
🎯 TP4: N/A
🚩 SL: N/A

⚙️ Hävstång: {leverage_text}
💰 IM: {im} USDT MUST confirm from Bybit ({im} USDT example)
☑️ Post-Only | MUST confirm from Bybit
☑️ Reduce-Only MUST confirm from Bybit
🔑 Order-ID: MUST confirm from Bybit

✅ Position opened – {mode_text_en}
🕒 Time: {datetime.now().strftime('%H:%M:%S')}
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Direction: {direction}

💥 Entry: {avg_entry}
🎯 TP1: N/A
🎯 TP2: N/A
🎯 TP3: N/A
🎯 TP4: N/A
🚩 SL: N/A

⚙️ Leverage: {leverage_text_en}
💰 IM: {im} USDT MUST confirm from Bybit ({im} USDT example)
☑️ Post-Only | MUST confirm from Bybit
☑️ Reduce-Only MUST confirm from Bybit
🔑 Order ID: MUST confirm from Bybit"""


def entry_taken(entry_num: int, symbol: str, channel_name: str, entry_price: Decimal, 
                qty: Decimal, im: Decimal, im_total: Decimal) -> str:
    """4. Entry taken message."""
    return f"""📌 ENTRY {entry_num} TAGEN
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

💥 Entry: {entry_price}
💵 Kvantitet: {qty}
💰 IM: {im} USDT (IM totalt: {im_total} USDT) MUST confirm from Bybit ({im} USDT example) (like 50/50)

📌 ENTRY {entry_num} TAKEN
📢 From channel: {channel_name}
📊 Symbol: {symbol}

💥 Entry: {entry_price}
💵 Quantity: {qty}
💰 IM: {im} USDT (IM total: {im_total} USDT) MUST confirm from Bybit ({im} USDT example) (like 50/50)"""


def entries_summary(symbol: str, channel_name: str, entry1: Decimal, qty1: Decimal, 
                   im1: Decimal, entry2: Decimal, qty2: Decimal, im2: Decimal, 
                   im_total: Decimal, avg_entry: Decimal, total_qty: Decimal) -> str:
    """5. Summary of both entries."""
    return f"""📌 Sammanställning av ENTRY 1 + ENTRY 2
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

📌 ENTRY 1 
💥 Entry: {entry1}
💵 Kvantitet: {qty1}
💰 IM: {im1} USDT (IM totalt: {im_total} USDT)
⚠️ Måste bekräftas i Bybit (ex. {im1} USDT eller {im2} USDT ≈50/50)

📌 ENTRY 2
💥 Entry: {entry2}
💵 Kvantitet: {qty2}
💰 IM: {im2} USDT (IM totalt: {im_total} USDT)
⚠️ Måste bekräftas i Bybit (ex. {im1} USDT eller {im2} USDT ≈50/50)

📌 SAMMANSATT POSITION
💥 Genomsnittligt Entry: {avg_entry} ← volymvägt mellan entry1 & entry2
💵 Total kvantitet: {total_qty}
💰 IM totalt: {im_total} USDT
⚠️ Bekräfta i Bybit

📌 Summary of ENTRY 1 + ENTRY 2
📢 From channel: {channel_name}
📊 Symbol: {symbol}

📌 ENTRY 1 
💥 Entry: {entry1}
💵 Quantity: {qty1}
💰 IM: {im1} USDT (IM total: {im_total} USDT)
⚠️ Must confirm from Bybit (ex. {im1} USDT or {im2} USDT ≈50/50)

📌 ENTRY 2
💥 Entry: {entry2}
💵 Quantity: {qty2}
💰 IM: {im2} USDT (IM total: {im_total} USDT)
⚠️ Must confirm from Bybit (ex. {im1} USDT or {im2} USDT ≈50/50)

📌 COMBINED POSITION
💥 Average Entry: {avg_entry} ← volume-weighted between entry1 & entry2
💵 Total quantity: {total_qty}
💰 IM total: {im_total} USDT
⚠️ Confirm in Bybit"""


def tp_hit(tp_num: int, symbol: str, channel_name: str, direction: str, 
           tp_price: Decimal, qty: Decimal, pct: Decimal, pnl_pct: Decimal, 
           pnl_usdt: Decimal) -> str:
    """6. Take profit hit message."""
    return f"""🎯 TAKE PROFIT {tp_num} TAGEN
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Sida: {direction}

📍 TP{tp_num}: {tp_price} ({pct}%) MUST confirm from Bybit
💵 Stängd kvantitet: {qty} (100% av positionen)
📊 Resultat: {pnl_pct}% | {pnl_usdt} USDT inkl. hävstång

🎯 TAKE PROFIT {tp_num} TAKEN
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Side: {direction}

📍 TP{tp_num}: {tp_price} ({pct}%) MUST confirm from Bybit
💵 Closed quantity: {qty} (100% of position)
📊 Result: {pnl_pct}% | {pnl_usdt} USDT incl. leverage"""


def pyramid_added(level: int, symbol: str, channel_name: str, direction: str, 
                 price: Decimal, qty: Decimal, im_added: Decimal, im_total: Decimal) -> str:
    """7. Pyramid add message."""
    return f"""📈 PYRAMID {level} steg 1, 1,5% kontrollera IM
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}

💥 Pris: {price} (+1,5%) (måste bekräftas av Bybit)
💵 Tillagd kvantitet: {qty} (måste bekräftas av Bybit)
💰 IM påfyllnad: +{im_added} USDT (IM totalt: {im_total} USDT) (måste bekräftas av Bybit)

📈 PYRAMID {level} step 1, 1.5% check IM
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Direction: {direction}

💥 Price: {price} (+1.5%) (must be confirmed by Bybit)
💵 Added quantity: {qty} (must be confirmed by Bybit)
💰 IM top-up: +{im_added} USDT (IM total: {im_total} USDT) (must be confirmed by Bybit)"""


def pyramid_breakeven(symbol: str, price: str, trade_id: str) -> str:
    """8. Pyramid breakeven SL message."""
    return f"""📈 PYRAMID steg 2, 2,3% Kontroll: SL flyttas till Break Even
📢 Från kanal: {trade_id}
📊 Symbol: {symbol}

💥 Pris: {price} (+2,3%) 
🛡️ SL justerad till Break Even (måste bekräftas av Bybit)

📈 PYRAMID step 2, 2.3% Control: SL moved to Break Even
📢 From channel: {trade_id}
📊 Symbol: {symbol}

💥 Price: {price} (+2.3%) 
🛡️ SL adjusted to Break Even (must be confirmed by Bybit)"""


def pyramid_leverage_raised(symbol: str, leverage: int, trade_id: str) -> str:
    """9. Pyramid leverage raised message."""
    return f"""📈 PYRAMID steg 3, 2,4% Kontroll: Hävstång höjd
📢 Från kanal: {trade_id}
📊 Symbol: {symbol}

💥 Pris: N/A (+2,4%) 
⚙️ Hävstång höjd till {leverage}x (enligt regler, ev. max 50x) (måste bekräftas av Bybit)

📈 PYRAMID step 3, 2.4% Control: Leverage raised
📢 From channel: {trade_id}
📊 Symbol: {symbol}

💥 Price: N/A (+2.4%) 
⚙️ Leverage raised to {leverage}x (according to rules, max 50x if applicable) (must be confirmed by Bybit)"""


def trailing_activated(symbol: str, direction: str, channel_name: str, 
                      trigger_pct: Decimal, distance_pct: Decimal, new_sl: Decimal) -> str:
    """10. Trailing stop activated message."""
    return f"""🔄 TRAILING STOP AKTIVERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}

📍 Trigger: +{trigger_pct}%
📍 Avstånd: {distance_pct}% bakom pris
📍 Ny SL: {new_sl}

🔄 TRAILING STOP ACTIVATED
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Direction: {direction}

📍 Trigger: +{trigger_pct}%
📍 Distance: {distance_pct}% behind price
📍 New SL: {new_sl}"""


def breakeven_adjusted(symbol: str, channel_name: str, sl_moved: Decimal) -> str:
    """11. Break-even adjusted message."""
    return f"""⚖️ BREAK-EVEN JUSTERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

📍 SL flyttad till: {sl_moved}

⚖️ BREAK-EVEN ADJUSTED
📢 From channel: {channel_name}
📊 Symbol: {symbol}

📍 SL moved to: {sl_moved}"""


def hedge_executed(symbol: str, channel_name: str, old_side: str, new_side: str, 
                  entry: Decimal, leverage: int, im: Decimal) -> str:
    """12. Hedge/reversal executed message."""
    return f"""🛡️ HEDGE / VÄNDNING AKTIVERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

📈 Tidigare position: {old_side} (stängd)
📉 Ny motriktad position: {new_side}
💥 Entry: {entry}

⚙️ Hävstång: {leverage}x
💰 IM: {im} USDT (MUST confirm from Bybit)

🛡️ HEDGE / REVERSAL EXECUTED
📢 From channel: {channel_name}
📊 Symbol: {symbol}

📈 Previous position: {old_side} (closed)
📉 New opposite position: {new_side}
💥 Entry: {entry}

⚙️ Leverage: {leverage}x
💰 IM: {im} USDT (MUST confirm from Bybit)"""


def hedge_closed(symbol: str, channel_name: str, old_side: str, exit_price: Decimal, leverage: int) -> str:
    """13. Hedge/reversal closed message."""
    return f"""🛡️ HEDGE / VÄNDNING AVSLUTAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

📈 Stängd position: {old_side}
💥 Stängningspris: {exit_price}

⚙️ Hävstång (avslutad): {leverage}x

🛡️ HEDGE / REVERSAL CLOSED
📢 From channel: {channel_name}
📊 Symbol: {symbol}

📈 Closed position: {old_side}
💥 Closing price: {exit_price}

⚙️ Leverage (closed): {leverage}x"""


def re_entry_executed(symbol: str, direction: str, channel_name: str, 
                     entry: Decimal, leverage: int, im: Decimal, im_total: Decimal) -> str:
    """14. Re-entry executed message."""
    return f"""♻️ RE-ENTRY / ÅTERINTRÄDE AKTIVERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Sida: {direction}

💥 Entry: {entry}
⚙️ Hävstång: {leverage}x
💰 IM: {im} USDT (IM totalt: {im_total} USDT)

♻️ RE-ENTRY / RE-ENTRY EXECUTED
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Side: {direction}

💥 Entry: {entry}
⚙️ Leverage: {leverage}x
💰 IM: {im} USDT (IM total: {im_total} USDT)"""


def re_entry_closed(symbol: str, direction: str, channel_name: str, 
                   exit_price: Decimal, pnl_usdt: Decimal, pnl_pct: Decimal, leverage: int) -> str:
    """15. Re-entry closed message."""
    return f"""♻️ RE-ENTRY / ÅTERINTRÄDE AVSLUTAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Sida: {direction}

💥 Exit: {exit_price}
📉 Resultat: {pnl_usdt} USDT ({pnl_pct}%)
⚙️ Hävstång (avslutad): {leverage}x

♻️ RE-ENTRY / RE-ENTRY CLOSED
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Side: {direction}

💥 Exit: {exit_price}
📉 Result: {pnl_usdt} USDT ({pnl_pct}%)
⚙️ Leverage (closed): {leverage}x"""


def sl_hit(symbol: str, direction: str, channel_name: str, 
           sl_price: Decimal, qty: Decimal, pnl_pct: Decimal, pnl_usdt: Decimal) -> str:
    """16. Stop loss hit message."""
    return f"""🚩 STOP LOSS TRÄFFAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Sida: {direction}

📍 SL: {sl_price}
💵 Stängd kvantitet: {qty} (100%)
📊 Resultat: {pnl_pct}% | {pnl_usdt} USDT

🔁 Återinträdeslogik: aktiverad – ny signal tas vid bekräftad trendvändning

🚩 STOP LOSS HIT
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Side: {direction}

📍 SL: {sl_price}
💵 Closed quantity: {qty} (100%)
📊 Result: {pnl_pct}% | {pnl_usdt} USDT

🔁 Re-entry logic: activated – new signal taken on confirmed trend reversal"""


def position_closed(symbol: str, direction: str, channel_name: str, 
                   qty: Decimal, exit_price: Decimal, pnl_pct: Decimal, 
                   pnl_usdt: Decimal, pol_usdt: Decimal) -> str:
    """17. Position closed message."""
    return f"""✅ POSITION STÄNGD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Sida: {direction}

💵 Stängd kvantitet: {qty} (100%)
📍 Exit: {exit_price}

📊 Resultat: {pnl_pct}% inkl. hävstång 
📊 Resultat: {pnl_usdt} USDT inkl. hävstång
📊 PoL: {pol_usdt} USDT

✅ POSITION CLOSED
📢 From channel: {channel_name}
📊 Symbol: {symbol}
📈 Side: {direction}

💵 Closed quantity: {qty} (100%)
📍 Exit: {exit_price}
📊 Result: {pnl_pct}% incl. leverage 
📊 Result: {pnl_usdt} USDT incl. leverage
📊 PoL: {pol_usdt} USDT"""


def order_deleted(symbol: str, channel_name: str) -> str:
    """18. Order deleted message."""
    return f"""✔️ ORDER RADERAD ✔️
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

📍 Fel: Order ej öppnad inom tillåten tid (raderad enligt reglerna)

✔️ ORDER DELETED ✔️
📢 From channel: {channel_name}
📊 Symbol: {symbol}

📍 Error: Order not opened within allowed time (deleted according to rules)"""


def daily_report(group_name: str, symbol_results: List[Dict], total_signals: int, 
                 total_pnl_usdt: Decimal, total_pnl_pct: Decimal) -> str:
    """19. Daily report message."""
    results_str = ""
    for res in symbol_results:
        results_str += f"{res['symbol']:<13} {res['pct']:<11} {res['usdt']}\n"
    
    return f"""📑 DAGLIG RAPPORT FRÅN GRUPP: {group_name}

📊 RESULTAT
Symbol        %            USDT
{results_str}
------------------------------------

📈 Antal signaler: {total_signals}
💹 Totalt resultat: {total_pnl_usdt} USDT
📊 Vinst/Förlust: {total_pnl_pct}%

📑 DAILY REPORT FROM GROUP: {group_name}

📊 RESULTS
Symbol        %            USDT
{results_str}
------------------------------------

📈 Number of signals: {total_signals}
💹 Total result: {total_pnl_usdt} USDT
📊 Win/Loss: {total_pnl_pct}%"""


def weekly_report(group_name: str, symbol_results: List[Dict], total_signals: int, 
                  total_pnl_usdt: Decimal, total_pnl_pct: Decimal) -> str:
    """20. Weekly report message."""
    results_str = ""
    for res in symbol_results:
        results_str += f"{res['symbol']:<13} {res['pct']:<11} {res['usdt']}\n"
    
    return f"""📑 VECKORAPPORT FRÅN GRUPP: {group_name}

📊 RESULTAT
Symbol        %            USDT
{results_str}
...           ...          ...

------------------------------------

📈 Antal signaler: {total_signals}
💹 Totalt resultat: {total_pnl_usdt} USDT
📊 Vinst/Förlust: {total_pnl_pct}%

📑 WEEKLY REPORT FROM GROUP: {group_name}

📊 RESULTS
Symbol        %            USDT
{results_str}
...           ...          ...

------------------------------------

📈 Number of signals: {total_signals}
💹 Total result: {total_pnl_usdt} USDT
📊 Win/Loss: {total_pnl_pct}%"""


# Additional helper templates for FSM integration
def tpsl_placed(symbol: str, tp_count: int, sl_price: str, channel_name: str) -> str:
    """TP/SL placed confirmation message."""
    return f"""🎯 TP/SL PLACERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

📍 TP: {tp_count} st
🚩 SL: {sl_price if sl_price else 'N/A'}

🎯 TP/SL PLACED
📢 From channel: {channel_name}
📊 Symbol: {symbol}

📍 TP: {tp_count} st
🚩 SL: {sl_price if sl_price else 'N/A'}"""


def error_message(symbol: str, channel_name: str, error: str) -> str:
    """Error message template."""
    return f"""❌ FEL UPPSTOD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

⚠️ Fel: {error}

❌ ERROR OCCURRED
📢 From channel: {channel_name}
📊 Symbol: {symbol}

⚠️ Error: {error}"""

