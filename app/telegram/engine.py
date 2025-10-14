"""
Telegram Template Engine (CLIENT SPEC Compliance).

Single normative rendering path for all Telegram messages.
All operational messages go through TemplateEngine.render().

PRIORITY 2 ENHANCEMENT: Message queue for centralized sending.
"""

import asyncio
from typing import Dict, Any, Optional, List
from decimal import Decimal
from collections import deque
from app.telegram.formatting import (
    fmt_usdt, fmt_leverage, fmt_price, fmt_percent, fmt_quantity,
    now_hms_stockholm, symbol_hashtags, ensure_trade_id,
    fmt_leverage_with_type, calculate_tp_sl_percentages, detect_trade_type
)
from app.core.logging import system_logger


class TemplateGuards:
    """
    Validate required fields before rendering templates.
    
    CLIENT SPEC: Certain messages require Bybit confirmation before sending.
    This class enforces those requirements.
    """
    
    # Templates that require Bybit-confirmed fields
    REQUIRED_BYBIT_FIELDS = {
        "ORDER_PLACED",
        "POSITION_OPENED",
        "ENTRY_TAKEN",
        "TP_TAKEN",
        "POSITION_CLOSED"
    }
    
    def check(self, key: str, d: Dict[str, Any]) -> None:
        """
        Validate required fields for a template.
        
        Raises:
            AssertionError: If required fields are missing
        """
        if key in self.REQUIRED_BYBIT_FIELDS:
            # These templates require Bybit confirmation
            if key in ["ORDER_PLACED", "POSITION_OPENED"]:
                assert d.get("order_id"), f"{key}: order_id missing (must confirm from Bybit)"
                assert d.get("post_only") in (True, False), f"{key}: post_only missing"
                assert d.get("reduce_only") in (True, False), f"{key}: reduce_only missing"
                
                im = d.get("im_confirmed")
                assert im is not None and str(im) not in ("", "None"), \
                    f"{key}: im_confirmed missing (must confirm from Bybit)"
            
            # All require basic fields
            assert d.get("symbol"), f"{key}: symbol missing"
            assert d.get("source_name"), f"{key}: source_name missing"


class TemplateRegistry:
    """
    Registry of all Telegram message templates.
    
    CLIENT SPEC: Exact formatting with bold labels, regular values,
    hashtags, and Trade ID at the end of every message.
    """
    
    def signal_received(self, d: Dict[str, Any]) -> str:
        """
        Signal received & copied (ONLY pre-Bybit message allowed).
        
        CLIENT SPEC (doc/10_11.md Lines 1264-1342):
        Must show type, entry, ALL 4 TPs with %, SL with %, leverage with type, Order IDs.
        
        This is the ONLY message that can be sent before Bybit confirmation.
        """
        t = now_hms_stockholm()
        
        # Detect trade type from leverage
        leverage = d.get('leverage', Decimal("6.00"))
        has_sl = bool(d.get('sl'))
        trade_type = detect_trade_type(leverage, has_sl)
        
        # Get entry and TP/SL values
        entry = d.get('entry', Decimal("0"))
        tps = [
            d.get('tp1'),
            d.get('tp2'),
            d.get('tp3'),
            d.get('tp4')
        ]
        sl = d.get('sl')
        side = d.get('side', 'LONG')
        
        # Calculate TP/SL percentages
        percentages = calculate_tp_sl_percentages(entry, tps, sl, side)
        
        # Format leverage with type
        lev_formatted = fmt_leverage_with_type(leverage, trade_type)
        
        # Get Order IDs (initially empty)
        bot_order_id = d.get('bot_order_id', '')
        bybit_order_id = d.get('bybit_order_id', '')
        
        # Get IM (may be estimated initially)
        im = d.get('im', Decimal("20.00"))
        
        # Build message (CLIENT SPEC format)
        lines = [
            "✅ Signal mottagen & kopierad",
            f"🕒 Tid: {t}",
            f"📢 Från kanal: {d['source_name']}",
            f"📊 Symbol: {d['symbol']} {symbol_hashtags(d['symbol'])}",
            f"📈 Riktning: {side}",
            f"📍 Typ: {trade_type}",
            "",
            f"💥 Entry: {fmt_price(entry, decimals=2)}",
        ]
        
        # Add all 4 TPs with percentages
        for i in range(1, 5):
            tp = tps[i-1]
            tp_pct = percentages.get(f'tp{i}_pct')
            if tp and tp_pct is not None:
                lines.append(f"🎯 TP{i}: {fmt_price(tp, decimals=2)} ({fmt_percent(tp_pct)})")
            else:
                lines.append(f"🎯 TP{i}: N/A")
        
        # Add SL with percentage
        sl_pct = percentages.get('sl_pct')
        if sl and sl_pct is not None:
            lines.append(f"🚩 SL: {fmt_price(sl, decimals=2)} ({fmt_percent(sl_pct)})")
        else:
            lines.append(f"🚩 SL: N/A")
        
        lines.extend([
            "",
            lev_formatted,
            f"💰 IM: {fmt_usdt(im)}",
            f"🔑 Order-ID BOT: {bot_order_id}",
            f"🔑 Order-ID Bybit: {bybit_order_id}",
        ])
        
        return "\n".join(lines)
    
    def order_placed(self, d: Dict[str, Any]) -> str:
        """
        Order placed (after Bybit confirmation).
        
        CLIENT SPEC (doc/10_11.md Lines 1434-1515):
        Must show type, Entry1/Entry2, ALL 4 TPs with %, SL with %, 
        leverage with type label, IM from Bybit, Order IDs, Post-Only/Reduce-Only.
        """
        t = now_hms_stockholm()
        
        # Detect trade type from leverage (FROM BYBIT!)
        leverage = d.get('leverage', Decimal("6.00"))
        has_sl = bool(d.get('sl'))
        trade_type = detect_trade_type(leverage, has_sl)
        
        # Get entry and TP/SL values from signal
        entry = d.get('entry', Decimal("0"))
        entry1 = d.get('entry1', entry)  # Dual limit entries
        entry2 = d.get('entry2', entry)
        tps = [
            d.get('tp1'),
            d.get('tp2'),
            d.get('tp3'),
            d.get('tp4')
        ]
        sl = d.get('sl')
        side = d.get('side', 'LONG')
        
        # Calculate TP/SL percentages
        percentages = calculate_tp_sl_percentages(entry, tps, sl, side)
        
        # Format leverage with type (FROM BYBIT!)
        lev_formatted = fmt_leverage_with_type(leverage, trade_type)
        
        # Get IM from Bybit (MUST be confirmed!)
        im = d.get('im_confirmed', d.get('im', Decimal("20.00")))
        
        # Get Order IDs
        bot_order_id = d.get('bot_order_id', '')
        bybit_order_id = d.get('bybit_order_id', '')
        
        # Build message (CLIENT SPEC format - doc/10_11.md Lines 1434-1456)
        # Handle None values for market orders
        entry1_str = fmt_price(entry1, decimals=2) if entry1 and entry1 != 0 else "MARKET"
        entry2_str = fmt_price(entry2, decimals=2) if entry2 and entry2 != 0 else "MARKET"
        
        lines = [
            f"✅ Order placerad – {trade_type}",
            f"🕒 Tid: {t}",
            f"📢 Från kanal: {d['source_name']}",
            f"📊 Symbol: {d['symbol']} {symbol_hashtags(d['symbol'])}",
            f"📈 Riktning: {side}",
            f"📍 Typ: {trade_type}",
            "",
            f"💥 Entry1: {entry1_str}",
            f"💥 Entry2: {entry2_str}",
        ]
        
        # Add all 4 TPs with percentages
        for i in range(1, 5):
            tp = tps[i-1]
            tp_pct = percentages.get(f'tp{i}_pct')
            if tp and tp_pct is not None:
                lines.append(f"🎯 TP{i}: {fmt_price(tp, decimals=2)} ({fmt_percent(tp_pct)})")
            else:
                lines.append(f"🎯 TP{i}: N/A")
        
        # Add SL with percentage
        sl_pct = percentages.get('sl_pct')
        if sl and sl_pct is not None:
            lines.append(f"🚩 SL: {fmt_price(sl, decimals=2)} ({fmt_percent(sl_pct)})")
        else:
            lines.append(f"🚩 SL: N/A")
        
        lines.extend([
            "",
            lev_formatted,
            f"💰 IM: {fmt_usdt(im)}",
            f"🔑 Order-ID BOT: {bot_order_id}",
            f"🔑 Order-ID Bybit: {bybit_order_id}",
            "",
            "✅Post-Only |    ",
            "✅Reduce-Only",
        ])
        
        return "\n".join(lines)
    
    def tp_sl_confirmed(self, d: Dict[str, Any]) -> str:
        """
        TP/SL confirmed by Bybit (NEW template from client spec).
        
        CLIENT SPEC (doc/10_11.md Lines 1356-1427):
        Shows that TP/SL orders were confirmed by Bybit.
        Different from order_placed - this is specifically for TP/SL orders.
        """
        t = now_hms_stockholm()
        
        # Detect trade type from leverage (FROM BYBIT!)
        leverage = d.get('leverage', Decimal("6.00"))
        has_sl = bool(d.get('sl'))
        trade_type = detect_trade_type(leverage, has_sl)
        
        # Format leverage with type
        lev_formatted = fmt_leverage_with_type(leverage, trade_type)
        
        # Get IM from Bybit
        im = d.get('im_confirmed', d.get('im', Decimal("20.00")))
        
        # Get qty/size
        qty = d.get('qty', Decimal("0"))
        
        # Get Order IDs
        bot_order_id = d.get('bot_order_id', '')
        bybit_order_id = d.get('bybit_order_id', '')
        
        side = d.get('side', 'LONG')
        
        # Build message (CLIENT SPEC format - doc/10_11.md Lines 1356-1377)
        lines = [
            f"✅ TP/SL bekräftad av Bybit – {trade_type}",
            f"🕒 Tid: {t}",
            f"📢 Från kanal: {d['source_name']}",
            f"📊 Symbol: {d['symbol']} {symbol_hashtags(d['symbol'])}",
            f"📈 Riktning: {side}",
            f"💰 Storlek: {fmt_quantity(qty)}",
            f"📍 Typ: {trade_type}",
            "",
            "🎯 TP1: Last price OK",
            "🎯 TP2: Last price OK",
            "🎯 TP3: Last price OK",
            "🎯 TP4: Last price OK",
            "🚩 SL: Mark price OK",
            "",
            lev_formatted,
            f"💰 IM: {fmt_usdt(im)}",
            f"🔑 Order-ID BOT: {bot_order_id}",
            f"🔑 Order-ID Bybit: {bybit_order_id}",
            "",
            "✅Post-Only |    ",
            "✅Reduce-Only",
        ]
        
        return "\n".join(lines)
    
    def entry_taken(self, d: Dict[str, Any]) -> str:
        """
        ENTRY 1 or ENTRY 2 taken (dual-limit requirement).
        
        CLIENT SPEC (doc/10_12_3.md Lines 1111-1284):
        Must be PLAIN TEXT (no markdown **bold**), show entry number, price, qty, IM.
        """
        entry_no = d.get("entry_no", 1)
        t = now_hms_stockholm()
        im = fmt_usdt(d.get("im", Decimal("0")))
        im_total = fmt_usdt(d.get("im_total", Decimal("0")))
        
        # Get trade type
        side = d.get('side', 'LONG')
        trade_type = d.get('typ', d.get('trade_type', 'DYNAMIC'))
        
        lines = [
            f"📌 ENTRY {entry_no} TAGEN",  # ✅ Plain text (no ** bold)
            f"🕒 Tid: {t}",
            f"📢 Från kanal: {d['source_name']}",  # ✅ Plain text
            f"📊 Symbol: {d['symbol']} {symbol_hashtags(d['symbol'])}",
            f"📈 Riktning: {side}",
            f"📍 Typ: {trade_type}",
            "",
            f"💥 Entry: {fmt_price(d['price'], decimals=2)}",
            f"💵 Kvantitet: {fmt_quantity(d['qty'])}",
            f"💰 IM: {im} (IM totalt: {im_total})",
            "",
            f"🔑 Order-ID BOT: {d.get('bot_order_id', '')}",
            f"🔑 Order-ID Bybit: {d.get('bybit_order_id', '')}",
            "",
            "✅Post-Only |    ",
            "✅Reduce-Only",
        ]
        return "\n".join(lines)
    
    def entry_consolidated(self, d: Dict[str, Any]) -> str:
        """
        Consolidation of ENTRY 1 + ENTRY 2 (dual-limit).
        
        CLIENT SPEC (doc/10_12_3.md Lines 1286-1376):
        Must show BOTH entries separately, then consolidated position.
        NO MARKDOWN BOLD - Plain text only.
        """
        t = now_hms_stockholm()
        
        # Get entry details (individual)
        entry1_price = d.get('entry1_price', Decimal("0"))
        entry1_qty = d.get('entry1_qty', Decimal("0"))
        entry1_im = d.get('entry1_im', Decimal("0"))
        
        entry2_price = d.get('entry2_price', Decimal("0"))
        entry2_qty = d.get('entry2_qty', Decimal("0"))
        entry2_im = d.get('entry2_im', Decimal("0"))
        
        # Get consolidated values
        avg_entry = d.get('avg_entry', Decimal("0"))
        total_qty = d.get('qty_total', d.get('total_qty', Decimal("0")))
        im_total = d.get('im_total', Decimal("0"))
        
        # Get trade type
        trade_type = d.get('typ', d.get('trade_type', 'DYNAMIC'))
        side = d.get('side', 'LONG')
        
        lines = [
            "📌 Sammanslagning av ENTRY 1 + ENTRY 2",
            f"🕒 Tid: {t}",
            f"📢 Från kanal: {d['source_name']}",
            f"📊 Symbol: {d['symbol']} {symbol_hashtags(d['symbol'])}",
            f"📈 Riktning: {side}",
            f"📍 Typ: {trade_type}",
            "",
            "📌 ENTRY 1",
            f"💥 Entry: {fmt_price(entry1_price, decimals=2)}",
            f"💵 Kvantitet: {fmt_quantity(entry1_qty)}",
            f"💰 IM: {fmt_usdt(entry1_im)} (IM totalt: {fmt_usdt(im_total)})",
            "",
            "📌 ENTRY 2",
            f"💥 Entry: {fmt_price(entry2_price, decimals=2)}",
            f"💵 Kvantitet: {fmt_quantity(entry2_qty)}",
            f"💰 IM: {fmt_usdt(entry2_im)} (IM totalt: {fmt_usdt(im_total)})",
            "",
            "📌 SAMMANSATT POSITION",
            f"💥 Genomsnittligt Entry: {fmt_price(avg_entry, decimals=2)}   ← volymvägt mellan entry1 & entry2",
            f"💵 Total kvantitet: {fmt_quantity(total_qty)}",
            f"💰 IM totalt: {fmt_usdt(im_total)}",
            "",
            f"🔑 Order-ID BOT: {d.get('bot_order_id', '')}",
            f"🔑 Order-ID Bybit: {d.get('bybit_order_id', '')}",
            "",
            "✅Post-Only |    ",
            "✅Reduce-Only",
        ]
        return "\n".join(lines)
    
    def position_opened(self, d: Dict[str, Any]) -> str:
        """
        Position opened (after both entries filled and position confirmed).
        
        CLIENT SPEC: Plain text (no markdown bold).
        """
        t = now_hms_stockholm()
        im = fmt_usdt(d["im_confirmed"])
        lev = fmt_leverage(d["leverage"])
        
        lines = [
            "✅ Position öppnad",
            "",
            f"📊 Symbol: {d['symbol']}",
            f"📈 Riktning: {d['side']}",
            f"💥 Entry: {fmt_price(d['entry_price'])}",
            f"💵 Kvantitet: {fmt_quantity(d['qty'])}",
            f"⚡️ Hävstång: {lev}",
            f"💰 IM: {im}",
            f"📺 Källa: {d['source_name']}",
            f"⏰ Tid: {t}",
            "",
            symbol_hashtags(d["symbol"]),
            f"🆔 {d['trade_id']}",
        ]
        return "\n".join(lines)
    
    def tp_taken(self, d: Dict[str, Any]) -> str:
        """
        Take Profit hit (TP1, TP2, TP3, TP4).
        
        CLIENT SPEC (doc/10_12_3.md Lines 1380-1424):
        Must show type, leverage type, TP price with %, qty closed, Order IDs, RESULT with leverage.
        CLIENT REQUIREMENT: Resultat (result) MUST include leverage!
        """
        tp_no = d.get("tp_no", 1)
        t = now_hms_stockholm()
        
        # Detect trade type from leverage (FROM BYBIT!)
        leverage = d.get("leverage", Decimal("6.00"))
        has_sl = bool(d.get('sl'))
        trade_type = detect_trade_type(leverage, has_sl)
        
        # Format leverage with type
        lev_formatted = fmt_leverage_with_type(leverage, trade_type)
        
        # Get TP price and calculate percentage
        tp_price = d.get('tp_price', Decimal("0"))
        entry_price = d.get('entry_price', Decimal("0"))
        
        # Calculate TP percentage from entry
        if entry_price and tp_price:
            side = d.get('side', 'LONG')
            if side.upper() in ("LONG", "BUY"):
                tp_pct_calc = ((tp_price - entry_price) / entry_price) * 100
            else:
                tp_pct_calc = ((entry_price - tp_price) / entry_price) * 100
            tp_pct = round(float(tp_pct_calc), 2)
        else:
            tp_pct = d.get('tp_pct', 0)
        
        # Get qty closed and percentage of position
        qty_closed = d.get('qty_closed', Decimal("0"))
        qty_pct = d.get('qty_pct', 25)  # Usually 25% per TP
        
        # Get result (WITH LEVERAGE from Bybit!)
        result_pct = d.get('pnl_pct', 0)  # CLIENT SPEC: inkl. leverage
        result_usdt = d.get('pnl_usdt', Decimal("0"))  # CLIENT SPEC: inkl. leverage
        
        # Get Order IDs
        bot_order_id = d.get('bot_order_id', '')
        bybit_order_id = d.get('bybit_order_id', '')
        
        lines = [
            f"🎯 TAKE PROFIT {tp_no} TAGEN",
            f"🕒 Tid: {t}",
            f"📢 Från kanal: {d['source_name']}",
            f"📊 Symbol: {d['symbol']} {symbol_hashtags(d['symbol'])}",
            f"📈 Riktning: {d.get('side', 'LONG')}",
            f"📍 Typ: {trade_type}",
            "",
            f"⚙️ {lev_formatted}",
            f"🔑 Order-ID BOT: {bot_order_id}",
            f"🔑 Order-ID Bybit: {bybit_order_id}",
            "✅ Stängd med Market",
            "✅ Post-Only |    ",
            "✅ Reduce-Only",
            "",
            f"✅TP{tp_no}: {fmt_price(tp_price, decimals=2)} ({fmt_percent(tp_pct)})",
            f"💵 Stängd kvantitet: {fmt_quantity(qty_closed)} ({qty_pct} % av positionen)",
            f"📊 Resultat: {fmt_percent(result_pct)} |",
            f"📊 Resultat: {fmt_usdt(result_usdt)} inkl. leverage!",
        ]
        
        return "\n".join(lines)
    
    def trailing_activated(self, d: Dict[str, Any]) -> str:
        """
        Trailing Stop activated.
        
        CLIENT SPEC (doc/10_11.md Lines 2315-2350):
        Must show type, leverage type, trigger percentage, distance, new SL.
        CLIENT REQUIREMENT: Profit % must include leverage!
        """
        t = now_hms_stockholm()
        
        # Detect trade type from leverage (FROM BYBIT!)
        leverage = d.get("leverage", Decimal("6.00"))
        has_sl = bool(d.get('sl'))
        trade_type = detect_trade_type(leverage, has_sl)
        
        # Format leverage with type
        lev_formatted = fmt_leverage_with_type(leverage, trade_type)
        
        # Get Order IDs
        bot_order_id = d.get('bot_order_id', '')
        bybit_order_id = d.get('bybit_order_id', '')
        
        side = d.get('side', 'LONG')
        trigger_pct = d.get('trigger_pct', 6.1)
        trail_dist_pct = d.get('trail_dist_pct', 2.5)
        new_sl = d.get('new_sl', Decimal("0"))
        
        lines = [
            f"🔄 TRAILING STOP AKTIVERAD – {trade_type}",
            f"🕒 Tid: {t}",
            f"📢 Från kanal: {d['source_name']}",
            f"📊 Symbol: {d['symbol']} {symbol_hashtags(d['symbol'])}",
            f"📈 Riktning: {side}",
            f"📍 Typ: {trade_type}",
            "",
            f"📍 Trigger: {fmt_percent(trigger_pct)}",
            f"🏁 Ny högsta/lägsta: {fmt_price(d.get('new_extreme', Decimal('0')), decimals=2)}",
            f"📍 SL justerad till: {fmt_price(new_sl, decimals=2)} ({fmt_percent(trail_dist_pct)})",
            "",
            f"🔑 Order-ID BOT: {bot_order_id}",
            f"🔑 Order-ID Bybit: {bybit_order_id}",
        ]
        
        return "\n".join(lines)
    
    def breakeven_moved(self, d: Dict[str, Any]) -> str:
        """
        Breakeven - SL moved to entry + cost.
        
        CLIENT SPEC (doc/10_11.md Lines 2352-2405):
        Must show type, leverage type, new SL, Order IDs.
        CLIENT SPEC: After TP2, move SL to BE + 0.0015%.
        """
        t = now_hms_stockholm()
        
        # Detect trade type from leverage (FROM BYBIT!)
        leverage = d.get("leverage", Decimal("6.00"))
        has_sl = bool(d.get('sl'))
        trade_type = detect_trade_type(leverage, has_sl)
        
        # Format leverage with type
        lev_formatted = fmt_leverage_with_type(leverage, trade_type)
        
        # Get Order IDs
        bot_order_id = d.get('bot_order_id', '')
        bybit_order_id = d.get('bybit_order_id', '')
        
        side = d.get('side', 'LONG')
        new_sl = d.get('new_sl', Decimal("0"))
        
        lines = [
            f"✅ BREAKEVEN AKTIVERAD – {trade_type}",
            f"🕒 Tid: {t}",
            f"📢 Från kanal: {d['source_name']}",
            f"📊 Symbol: {d['symbol']} {symbol_hashtags(d['symbol'])}",
            f"📈 Riktning: {side}",
            f"📍 Typ: {trade_type}",
            "",
            f"📍 SL flyttad till: {fmt_price(new_sl, decimals=2)}",
            f"🔑 Order-ID BOT: {bot_order_id}",
            f"🔑 Order-ID Bybit: {bybit_order_id}",
        ]
        
        return "\n".join(lines)
    
    def pyramid_step(self, d: Dict[str, Any]) -> str:
        """
        Pyramid step (levels 1-6).
        
        CLIENT SPEC (doc/10_12_3.md Lines 1480-1776):
        Must show type, trigger percentage, added qty, IM added, IM TOTAL, Order IDs.
        CLIENT REQUIREMENT: Must show IM TOTAL from Bybit!
        """
        level = d.get("level", 1)
        t = now_hms_stockholm()
        
        # Detect trade type from leverage (FROM BYBIT!)
        leverage = d.get("leverage", Decimal("6.00"))
        has_sl = bool(d.get('sl'))
        trade_type = detect_trade_type(leverage, has_sl)
        
        # Get trigger percentage (price movement from entry)
        gain_pct = d.get("gain_pct", 0)  # Trade % (price movement)
        
        # Format leverage with type (FROM BYBIT!)
        lev_formatted = fmt_leverage_with_type(leverage, trade_type)
        
        # Get IM values (MUST show both added and total)
        im_added = d.get('im_added', Decimal('0'))
        im_total = d.get('im_total', Decimal('0'))  # CLIENT SPEC: IM totalt
        
        # Get Order IDs
        bot_order_id = d.get('bot_order_id', '')
        bybit_order_id = d.get('bybit_order_id', '')
        
        side = d.get('side', 'LONG')
        
        lines = [
            f"📈 PYRAMID NIVÅ {level}",
            f"🕒 Tid: {t}",
            f"📢 Från kanal: {d['source_name']}",
            f"📊 Symbol: {d['symbol']} {symbol_hashtags(d['symbol'])}",
            f"📈 Riktning: {side}",
            f"📍 Typ: {trade_type}",
            "",
            f"🔑 Order-ID BOT: {bot_order_id}",
            f"🔑 Order-ID Bybit: {bybit_order_id}",
            f"💥 Pris: {fmt_price(d['price'], decimals=2)} (+{fmt_percent(gain_pct)})",
            f"💵 Tillagd kvantitet: {fmt_quantity(d['qty_added'])}",
            f"💰 IM påfyllnad: +{fmt_usdt(im_added)} (IM totalt: {fmt_usdt(im_total)})",  # CLIENT SPEC: Show both
        ]
        
        return "\n".join(lines)
    
    def hedge_started(self, d: Dict[str, Any]) -> str:
        """
        Hedge started (-2% protection).
        
        CLIENT SPEC (doc/10_11.md Lines 2407-2510):
        Must show type, leverage type, trigger, IM, Order IDs.
        """
        t = now_hms_stockholm()
        
        # Detect trade type from leverage (FROM BYBIT!)
        leverage = d.get("leverage", Decimal("6.00"))
        has_sl = bool(d.get('sl'))
        trade_type = detect_trade_type(leverage, has_sl)
        
        # Format leverage with type
        lev_formatted = fmt_leverage_with_type(leverage, trade_type)
        
        # Get Order IDs
        bot_order_id = d.get('bot_order_id', '')
        bybit_order_id = d.get('bybit_order_id', '')
        
        side = d.get('side', 'LONG')
        hedge_side = "SHORT" if side == "LONG" else "LONG"
        price = d.get('price', Decimal("0"))
        qty = d.get('qty', Decimal("0"))
        im = d.get('im', Decimal("0"))
        
        lines = [
            f"🛡️ HEDGE STARTAD – {trade_type}",
            f"🕒 Tid: {t}",
            f"📢 Från kanal: {d['source_name']}",
            f"📊 Symbol: {d['symbol']} {symbol_hashtags(d['symbol'])}",
            f"📈 Riktning (hedge): {hedge_side}",
            f"📍 Typ: {trade_type}",
            "",
            f"📉 Trigger: -2,00 % från entry",
            f"💥 Pris: {fmt_price(price, decimals=2)}",
            f"💵 Storlek: {fmt_quantity(qty)}",
            f"💰 IM: {fmt_usdt(im)}",
            f"🔑 Order-ID BOT: {bot_order_id}",
            f"🔑 Order-ID Bybit: {bybit_order_id}",
        ]
        
        return "\n".join(lines)
    
    def hedge_stopped(self, d: Dict[str, Any]) -> str:
        """
        Hedge stopped.
        
        CLIENT SPEC: Plain text (no markdown bold).
        """
        t = now_hms_stockholm()
        pnl_usdt = fmt_usdt(d["pnl_usdt"])
        pnl_pct = fmt_percent(d["pnl_pct"])
        
        lines = [
            "🛡️ HEDGE STOPPAD",
            "",
            f"📢 Från kanal: {d['source_name']}",
            f"📊 Symbol: {d['symbol']}",
            f"📈 Resultat: {pnl_pct} | {pnl_usdt}",
            f"⏰ Tid: {t}",
            "",
            symbol_hashtags(d["symbol"]),
            f"🆔 {d['trade_id']}",
        ]
        return "\n".join(lines)
    
    def reentry_started(self, d: Dict[str, Any]) -> str:
        """
        Re-entry started (attempt N of 3).
        
        CLIENT SPEC (doc/10_11.md Lines 2620-2720):
        Must show type, Entry1/Entry2, all TPs/SL, leverage type, IM, Order IDs.
        """
        attempt = d.get("attempt", 1)
        t = now_hms_stockholm()
        
        # Detect trade type from leverage (FROM BYBIT!)
        leverage = d.get("leverage", Decimal("6.00"))
        has_sl = bool(d.get('sl'))
        trade_type = detect_trade_type(leverage, has_sl)
        
        # Get entry and TP/SL values from signal
        entry = d.get('entry', d.get('price', Decimal("0")))
        entry1 = d.get('entry1', entry)
        entry2 = d.get('entry2', entry)
        tps = [
            d.get('tp1'),
            d.get('tp2'),
            d.get('tp3'),
            d.get('tp4')
        ]
        sl = d.get('sl')
        side = d.get('side', 'LONG')
        
        # Calculate TP/SL percentages
        percentages = calculate_tp_sl_percentages(entry, tps, sl, side)
        
        # Format leverage with type
        lev_formatted = fmt_leverage_with_type(leverage, trade_type)
        
        # Get IM from Bybit
        im = d.get('im_confirmed', d.get('im', Decimal("20.00")))
        
        # Get Order IDs
        bot_order_id = d.get('bot_order_id', '')
        bybit_order_id = d.get('bybit_order_id', '')
        
        lines = [
            f"♻️ RE-ENTRY / ÅTERINTRÄDE AKTIVERAD – {trade_type}",
            f"🕒 Tid: {t}",
            f"📢 Från kanal: {d['source_name']}",
            f"📊 Symbol: {d['symbol']} {symbol_hashtags(d['symbol'])}",
            f"📈 Riktning: {side}",
            f"📍 Typ: {trade_type}",
            "",
            f"💥 Entry1: {fmt_price(entry1, decimals=2)}",
            f"💥 Entry2: {fmt_price(entry2, decimals=2)}",
        ]
        
        # Add all 4 TPs with percentages
        for i in range(1, 5):
            tp = tps[i-1]
            tp_pct = percentages.get(f'tp{i}_pct')
            if tp and tp_pct is not None:
                lines.append(f"🎯 TP{i}: {fmt_price(tp, decimals=2)} ({fmt_percent(tp_pct)})")
            else:
                lines.append(f"🎯 TP{i}: N/A")
        
        # Add SL with percentage
        sl_pct = percentages.get('sl_pct')
        if sl and sl_pct is not None:
            lines.append(f"🚩 SL: {fmt_price(sl, decimals=2)} ({fmt_percent(sl_pct)})")
        else:
            lines.append(f"🚩 SL: N/A")
        
        lines.extend([
            "",
            lev_formatted,
            f"💰 IM: {fmt_usdt(im)}",
            f"🔑 Order-ID BOT: {bot_order_id}",
            f"🔑 Order-ID Bybit: {bybit_order_id}",
            "",
            "✅Post-Only |    ",
            "✅Reduce-Only",
        ])
        
        return "\n".join(lines)
    
    def sl_hit(self, d: Dict[str, Any]) -> str:
        """
        Stop Loss hit.
        
        CLIENT SPEC (doc/10_11.md Lines 2787-2850):
        Must show type, leverage type, SL price, result, Order IDs.
        CLIENT SPEC: Show loss in both % and USDT.
        """
        t = now_hms_stockholm()
        
        # Detect trade type from leverage (FROM BYBIT!)
        leverage = d.get("leverage", Decimal("6.00"))
        has_sl = bool(d.get('sl'))
        trade_type = detect_trade_type(leverage, has_sl)
        
        # Format leverage with type
        lev_formatted = fmt_leverage_with_type(leverage, trade_type)
        
        # Get SL data
        sl_price = d.get('sl_price', Decimal("0"))
        qty_closed = d.get('qty_closed', Decimal("0"))
        result_pct = d.get('pnl_pct', 0)
        result_usdt = d.get('pnl_usdt', Decimal("0"))
        
        # Get Order IDs
        bot_order_id = d.get('bot_order_id', '')
        bybit_order_id = d.get('bybit_order_id', '')
        
        side = d.get('side', 'LONG')
        
        lines = [
            f"⛔ SL TRÄFFAD – {trade_type}",
            f"🕒 Tid: {t}",
            f"📢 Från kanal: {d['source_name']}",
            f"📊 Symbol: {d['symbol']} {symbol_hashtags(d['symbol'])}",
            f"📈 Riktning: {side}",
            f"📍 Typ: {trade_type}",
            "",
            f"📍 SL: {fmt_price(sl_price, decimals=2)}",
            f"💵 Stängd kvantitet: {fmt_quantity(qty_closed)} (100 %)",
            f"📊 Resultat: {fmt_percent(result_pct)} | {fmt_usdt(result_usdt)}",
            f"🔑 Order-ID BOT: {bot_order_id}",
            f"🔑 Order-ID Bybit: {bybit_order_id}",
        ]
        
        return "\n".join(lines)
    
    def position_closed(self, d: Dict[str, Any]) -> str:
        """
        Position closed (final message).
        
        CLIENT SPEC (doc/10_11.md Lines 2852-2925):
        Must show type, leverage type, total qty closed, final result, Order IDs.
        CLIENT SPEC: Show final P&L in both % and USDT (including leverage).
        """
        t = now_hms_stockholm()
        
        # Detect trade type from leverage (FROM BYBIT!)
        leverage = d.get("leverage", Decimal("6.00"))
        has_sl = bool(d.get('sl'))
        trade_type = detect_trade_type(leverage, has_sl)
        
        # Format leverage with type
        lev_formatted = fmt_leverage_with_type(leverage, trade_type)
        
        # Get result data
        qty_closed = d.get('qty_closed', Decimal("0"))
        result_pct = d.get('pnl_pct', 0)  # Includes leverage
        result_usdt = d.get('pnl_usdt', Decimal("0"))  # Includes leverage
        
        # Get Order IDs
        bot_order_id = d.get('bot_order_id', '')
        bybit_order_id = d.get('bybit_order_id', '')
        
        side = d.get('side', 'LONG')
        
        lines = [
            f"🏁 POSITION STÄNGD – {trade_type}",
            f"🕒 Tid: {t}",
            f"📢 Från kanal: {d['source_name']}",
            f"📊 Symbol: {d['symbol']} {symbol_hashtags(d['symbol'])}",
            f"📈 Riktning: {side}",
            f"📍 Typ: {trade_type}",
            "",
            f"💵 Stängd kvantitet: {fmt_quantity(qty_closed)} (100 %)",
            f"📚 Underlag ink. alla delsteg (BOT/Bybit): {bot_order_id} / {bybit_order_id}",
            "",
            f"📊 Resultat (prisrörelse): {fmt_percent(result_pct)}",
            f"💰 Resultat (USDT, inkl. hävstång/notional): {fmt_usdt(result_usdt)}",
            f"🔑 Order-ID BOT: {bot_order_id}",
            f"🔑 Order-ID Bybit: {bybit_order_id}",
        ]
        
        return "\n".join(lines)
    
    def error_message(self, d: Dict[str, Any]) -> str:
        """
        Error message template.
        
        CLIENT SPEC: Plain text (no markdown bold).
        """
        t = now_hms_stockholm()
        error = d.get("error", "Unknown error")
        
        lines = [
            "⚠️ FEL",
            "",
            f"📊 Symbol: {d.get('symbol', 'N/A')}",
            f"❌ Fel: {error}",
            f"⏰ Tid: {t}",
        ]
        
        if d.get("trade_id"):
            lines.append("")
            lines.append(f"🆔 {d['trade_id']}")
        
        return "\n".join(lines)
    
    def signal_blocked(self, d: Dict[str, Any]) -> str:
        """
        Signal blocked (duplicate within tolerance window).
        
        CLIENT SPEC (doc/10_12_3.md Lines 2521-2526):
        ❌SIGNAL BLOCKERAD (Dubblett ≤5 %)  ❌
        🕒 Tid: {{tid}} | Gäller i: 2 h
        📊 Avvikelse: {{diff_pct}} %
        📢 Källa: {{kanal_namn}} | Symbol: {{symbol}}
        """
        t = now_hms_stockholm()
        
        # Get values
        diff_pct = d.get('diff_pct', '0')
        source_name = d.get('source_name', 'Unknown')
        symbol = d.get('symbol', 'N/A')
        
        lines = [
            "❌SIGNAL BLOCKERAD (Dubblett ≤5 %)  ❌",
            f"🕒 Tid: {t} | Gäller i: 2 h",
            f"📊 Avvikelse: {diff_pct} %",
            f"📢 Källa: {source_name} | Symbol: {symbol}",
        ]
        
        return "\n".join(lines)
    
    def entry_consolidated(self, d: Dict[str, Any]) -> str:
        """
        Entry consolidated (after both Entry1 and Entry2 filled).
        
        CLIENT SPEC (doc/10_12_3.md Lines 1286-1376):
        Must show BOTH entries separately, then consolidated position.
        """
        t = now_hms_stockholm()
        
        # Get entry details (individual)
        entry1_price = d.get('entry1_price', Decimal("0"))
        entry1_qty = d.get('entry1_qty', Decimal("0"))
        entry1_im = d.get('entry1_im', Decimal("0"))
        
        entry2_price = d.get('entry2_price', Decimal("0"))
        entry2_qty = d.get('entry2_qty', Decimal("0"))
        entry2_im = d.get('entry2_im', Decimal("0"))
        
        # Get consolidated values
        avg_entry = d.get('avg_entry', Decimal("0"))
        total_qty = d.get('qty_total', d.get('total_qty', Decimal("0")))
        im_total = d.get('im_total', Decimal("0"))
        
        # Get trade type
        trade_type = d.get('typ', d.get('trade_type', 'DYNAMIC'))
        side = d.get('side', 'LONG')
        
        lines = [
            "📌 Sammanslagning av ENTRY 1 + ENTRY 2",
            f"🕒 Tid: {t}",
            f"📢 Från kanal: {d['source_name']}",
            f"📊 Symbol: {d['symbol']} {symbol_hashtags(d['symbol'])}",
            f"📈 Riktning: {side}",
            f"📍 Typ: {trade_type}",
            "",
            "📌 ENTRY 1",
            f"💥 Entry: {fmt_price(entry1_price, decimals=2)}",
            f"💵 Kvantitet: {fmt_quantity(entry1_qty)}",
            f"💰 IM: {fmt_usdt(entry1_im)} (IM totalt: {fmt_usdt(im_total)})",
            "",
            "📌 ENTRY 2",
            f"💥 Entry: {fmt_price(entry2_price, decimals=2)}",
            f"💵 Kvantitet: {fmt_quantity(entry2_qty)}",
            f"💰 IM: {fmt_usdt(entry2_im)} (IM totalt: {fmt_usdt(im_total)})",
            "",
            "📌 SAMMANSATT POSITION",
            f"💥 Genomsnittligt Entry: {fmt_price(avg_entry, decimals=2)}   ← volymvägt mellan entry1 & entry2",
            f"💵 Total kvantitet: {fmt_quantity(total_qty)}",
            f"💰 IM totalt: {fmt_usdt(im_total)}",
            "",
            f"🔑 Order-ID BOT: {d.get('bot_order_id', '')}",
            f"🔑 Order-ID Bybit: {d.get('bybit_order_id', '')}",
            "",
            "✅Post-Only |    ",
            "✅Reduce-Only",
        ]
        return "\n".join(lines)
    
    def daily_group_report(self, d: Dict[str, Any]) -> str:
        """
        Daily group report template.
        
        CLIENT SPEC: Per-group daily report with symbol results and statistics.
        Plain text (no markdown bold).
        """
        group_name = d.get("group_name", "Unknown")
        symbols = d.get("symbols", [])  # List of {symbol, pct, usdt}
        num_signals = d.get("num_signals", 0)
        result_usdt = fmt_usdt(d.get("result_usdt", Decimal("0")))
        result_pct = fmt_percent(d.get("result_pct", 0))
        
        lines = [
            f"📑 DAGLIG RAPPORT FRÅN GRUPP: {group_name}",
            "",
            "📊 RESULTAT",
            "Symbol        %         USDT",
        ]
        
        # Add symbol rows (top 3)
        for sym_data in symbols[:3]:
            symbol = sym_data.get("symbol", "").ljust(12)
            pct = fmt_percent(sym_data.get("pct", 0)).ljust(9)
            usdt = fmt_usdt(sym_data.get("usdt", Decimal("0")))
            lines.append(f"{symbol} {pct} {usdt}")
        
        lines.extend([
            "------------------------------------",
            f"📈 Antal signaler: {num_signals}",
            f"💹 Totalt resultat: {result_usdt}",
            f"📊 Vinst/Förlust: {result_pct}",
        ])
        
        # Add error counts if provided
        if d.get("errors"):
            lines.append("")
            lines.append(f"📍 Fel: {d['errors']}")
        
        return "\n".join(lines)


class MessageQueue:
    """
    Priority 2 Enhancement: Centralized message queue for Telegram.
    
    Benefits:
    - Rate limiting (prevent Telegram API throttling)
    - Message ordering (FIFO guarantee)
    - Retry logic (on send failures)
    - Backpressure handling (queue size limits)
    """
    
    def __init__(self, max_queue_size: int = 1000, rate_limit_delay: float = 0.1):
        self.queue: deque = deque(maxlen=max_queue_size)
        self.rate_limit_delay = rate_limit_delay
        self.running = False
        self.worker_task: Optional[asyncio.Task] = None
        self.lock = asyncio.Lock()
    
    async def enqueue(self, template_key: str, data: Dict[str, Any], priority: int = 5) -> bool:
        """
        Enqueue a message for sending.
        
        Args:
            template_key: Template to render (e.g., "PYRAMID_STEP")
            data: Data for template
            priority: Priority level (1=highest, 10=lowest), default=5
        
        Returns:
            True if enqueued, False if queue full
        """
        async with self.lock:
            try:
                self.queue.append({
                    'template_key': template_key,
                    'data': data,
                    'priority': priority,
                    'enqueued_at': asyncio.get_event_loop().time(),
                    'retry_count': 0
                })
                system_logger.debug(f"Enqueued message: {template_key} for {data.get('symbol', 'N/A')}")
                return True
            except Exception as e:
                system_logger.error(f"Failed to enqueue message: {e}")
                return False
    
    async def start(self):
        """Start the queue worker."""
        if self.running:
            return
        
        self.running = True
        self.worker_task = asyncio.create_task(self._worker())
        system_logger.info("Message queue worker started")
    
    async def stop(self):
        """Stop the queue worker."""
        self.running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        system_logger.info("Message queue worker stopped")
    
    async def _worker(self):
        """Worker task that processes queued messages."""
        from app.telegram.output import send_message
        
        while self.running:
            try:
                if self.queue:
                    # Get next message
                    async with self.lock:
                        if self.queue:
                            message = self.queue.popleft()
                        else:
                            message = None
                    
                    if message:
                        # Render and send
                        template_key = message['template_key']
                        data = message['data']
                        
                        try:
                            # Render template
                            rendered = render_template(template_key, data)
                            
                            # Send with rate limiting
                            await send_message(
                                rendered["text"],
                                template_name=rendered["template_name"],
                                trade_id=rendered["trade_id"],
                                symbol=rendered["symbol"],
                                hashtags=rendered["hashtags"],
                                trace_id=data.get("trace_id", "")
                            )
                            
                            # Rate limiting delay
                            await asyncio.sleep(self.rate_limit_delay)
                            
                        except Exception as e:
                            system_logger.error(f"Failed to send queued message: {e}", exc_info=True)
                            
                            # Retry logic (max 3 attempts)
                            if message['retry_count'] < 3:
                                message['retry_count'] += 1
                                async with self.lock:
                                    self.queue.append(message)
                                system_logger.info(f"Re-queued message (attempt {message['retry_count']})")
                else:
                    # Queue empty, sleep briefly
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                system_logger.error(f"Queue worker error: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    def get_queue_size(self) -> int:
        """Get current queue size."""
        return len(self.queue)


class TemplateEngine:
    """
    Main template engine for Telegram messages.
    
    CLIENT SPEC: All Telegram output goes via TemplateEngine.render().
    This ensures consistent formatting and validation.
    
    PRIORITY 2: Now includes message queue for centralized sending.
    """
    
    def __init__(self):
        self.registry = TemplateRegistry()
        self.guards = TemplateGuards()
        self.message_queue = MessageQueue()  # Priority 2: Centralized queue
    
    def render(self, key: str, data: Dict[str, Any]) -> str:
        """
        Render a template with data.
        
        Args:
            key: Template key (e.g., "ORDER_PLACED", "TP_TAKEN")
            data: Data dictionary with required fields
        
        Returns:
            Formatted message string
        
        Raises:
            AssertionError: If required fields are missing
            AttributeError: If template key doesn't exist
        """
        # Ensure trade_id exists
        data["trade_id"] = ensure_trade_id(data.get("trade_id"))
        
        # Validate required fields
        self.guards.check(key, data)
        
        # Get template method (convert key to method name)
        method_name = key.lower()
        
        if not hasattr(self.registry, method_name):
            system_logger.error(f"Unknown template key: {key}")
            return self.registry.error_message({
                "error": f"Unknown template: {key}",
                "symbol": data.get("symbol", "N/A")
            })
        
        # Render template
        template_method = getattr(self.registry, method_name)
        return template_method(data)
    
    async def enqueue_and_send(self, key: str, data: Dict[str, Any], priority: int = 5) -> bool:
        """
        Priority 2: Enqueue message for sending through centralized queue.
        
        This is the recommended way to send messages from strategies.
        
        Args:
            key: Template key (e.g., "PYRAMID_STEP")
            data: Data for template
            priority: Message priority (1=urgent, 10=low), default=5
        
        Returns:
            True if enqueued successfully
        
        Example:
            engine = get_template_engine()
            await engine.enqueue_and_send("PYRAMID_STEP", {
                'symbol': 'BTCUSDT',
                'level': 2,
                'price': Decimal("50000"),
                ...
            })
        """
        return await self.message_queue.enqueue(key, data, priority)
    
    async def start_queue(self):
        """Start the message queue worker."""
        await self.message_queue.start()
    
    async def stop_queue(self):
        """Stop the message queue worker."""
        await self.message_queue.stop()
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            'queue_size': self.message_queue.get_queue_size(),
            'running': self.message_queue.running
        }


# Global template engine instance
_template_engine = None


def get_template_engine() -> TemplateEngine:
    """Get global template engine instance."""
    global _template_engine
    if _template_engine is None:
        _template_engine = TemplateEngine()
    return _template_engine


def render_template(key: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Render a template and return metadata for logging.
    
    CLIENT SPEC: This is the main entry point for rendering Telegram messages.
    All operational messages should use this function.
    
    Args:
        key: Template key (e.g., "ORDER_PLACED", "ENTRY_TAKEN")
        data: Data dictionary with required fields
    
    Returns:
        Dictionary with:
            - text: Formatted message text
            - template_name: Template key
            - trade_id: Trade ID from data
            - symbol: Symbol from data
            - hashtags: Generated hashtags
    
    Example:
        >>> rendered = render_template("ORDER_PLACED", {
        ...     "symbol": "BTCUSDT",
        ...     "side": "LONG",
        ...     "qty": "0.001",
        ...     "leverage": "10",
        ...     "source_name": "VIP Trading",
        ...     "order_id": "abc123",
        ...     "post_only": True,
        ...     "reduce_only": False,
        ...     "im_confirmed": "20.00"
        ... })
        >>> print(rendered["text"])
    """
    engine = get_template_engine()
    text = engine.render(key, data)
    
    return {
        "text": text,
        "template_name": key,
        "trade_id": data.get("trade_id", ""),
        "symbol": data.get("symbol", ""),
        "hashtags": symbol_hashtags(data.get("symbol", ""))
    }

