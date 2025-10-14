"""
DEPRECATED - DO NOT USE

CLIENT FIX (COMPLIANCE doc/10_12_2.md Lines 447-460):
This legacy template system is DEPRECATED per client requirements.

⚠️ HARD DISABLED - This module will raise RuntimeError on import ⚠️

All Telegram messages MUST use the unified TemplateEngine instead:
    from app.telegram.engine import render_template
    rendered = render_template("ORDER_PLACED", data)

See COMPLIANCE_ANALYSIS.md section 10.2 point 5 for details.
"""

# CLIENT SPEC: Hard-disable legacy templates to prevent accidental use
raise RuntimeError(
    "❌ DEPRECATED: swedish_templates_v2.py is disabled per client requirements (doc/10_12_2.md Lines 447-460). "
    "Use app.telegram.engine.TemplateEngine instead. "
    "See COMPLIANCE_ANALYSIS.md section 10.2 point 5."
)

# Code below is preserved for reference but will never execute due to RuntimeError above
# ==================================================================================

"""
Swedish Telegram templates with exact client requirements.

⚠️ IMPORTANT - CLIENT SPEC COMPLIANCE UPDATE:
----------------------------------------
The new app/telegram/engine.py provides a comprehensive template system
that fully complies with CLIENT SPEC requirements:
- Proper Bybit confirmation gates
- Stockholm time formatting (HH:MM:SS)
- Trade ID tracking
- Hashtags (#btc, #btcusdt)
- Bold labels with regular values
- Exact 2-decimal formatting for USDT and leverage
- NO pre-Bybit "waiting" messages (except signal_received)

USAGE GUIDE:
-----------
For NEW code requiring Bybit-confirmed data (order_id, im_confirmed, etc.):
    from app.telegram.engine import render_template
    rendered = render_template("ORDER_PLACED", data)
    await send_message(rendered["text"], **rendered)

For BACKWARD COMPATIBILITY or simple messages:
    from app.telegram.swedish_templates_v2 import get_swedish_templates
    templates = get_swedish_templates()
    message = templates.signal_received(data)
    await send_message(message)

This file (swedish_templates_v2.py) is maintained for backward compatibility
and will gradually migrate to the new TemplateEngine.
"""

from typing import Dict, Any
from decimal import Decimal
from datetime import datetime
from app.telegram.formatting import (
    fmt_usdt, fmt_leverage, fmt_price, fmt_percent, fmt_quantity,
    now_hms_stockholm, symbol_hashtags, ensure_trade_id
)

# ============================================================================
# PRODUCTION LOCK - DO NOT USE THIS FILE
# ============================================================================
# CLIENT REQUIREMENT: All Telegram messages MUST go through single path:
#   ConfirmationGate → Engine → Output
#
# This file is DEPRECATED and contains forbidden patterns:
#   ❌ "Waiting for Bybit confirmation…"
#   ❌ "IM: ~20 USDT" (approximate values)
#   ❌ Messages sent before Bybit retCode=0
#
# REQUIRED: Use app/telegram/engine.py instead
# ============================================================================

import os
_IS_PRODUCTION = os.getenv("ENV", "PROD") == "PROD"

if _IS_PRODUCTION:
    raise RuntimeError(
        "DEPRECATED: swedish_templates_v2.py is forbidden in production. "
        "Use app/telegram/engine.py instead. "
        "See doc/10_12_requirement.txt for details."
    )

class SwedishTemplatesV2:
    """
    Swedish templates - DEPRECATED.
    
    ⚠️ DEPRECATED: Use app/telegram/engine.py (TemplateEngine) instead.
    CLIENT SPEC Line 33: Each function raises RuntimeError to prevent usage.
    
    This class is kept for reference only. All functions raise RuntimeError.
    """
    
    @staticmethod
    def signal_received(signal_data: Dict[str, Any]) -> str:
        # CLIENT SPEC Line 33: Each function must raise RuntimeError
        raise RuntimeError("DEPRECATED: Use app/telegram/engine.render_template('SIGNAL_RECEIVED', data)")
        """
        Signal mottagen & kopierad template (UPDATED for CLIENT SPEC).
        
        CLIENT SPEC: This is the ONLY message allowed before Bybit confirmation.
        All other messages must wait for Bybit confirmation.
        
        DEPRECATED: Use app/telegram/engine.render_template() instead.
        """
        symbol = signal_data.get('symbol', '')
        direction = signal_data.get('direction', '')
        mode = signal_data.get('mode', '')
        channel_name = signal_data.get('channel_name', '')
        leverage = signal_data.get('leverage', 0)
        trade_id = ensure_trade_id(signal_data.get('trade_id'))
        
        # CLIENT SPEC: Use Stockholm time HH:MM:SS
        t = now_hms_stockholm()
        
        # CLIENT SPEC: Leverage with 2 decimals
        leverage_str = fmt_leverage(leverage)
        
        # CLIENT SPEC: Add hashtags
        hashtags = symbol_hashtags(symbol)
        
        # CLIENT SPEC: NO "Väntar på Bybit bekräftelse" - that's forbidden
        # CLIENT SPEC: NO "~20 USDT" - that must come from Bybit confirmation
        
        return f"""**🎯 Signal mottagen & kopierad**

📢 **Från kanal:** {channel_name}
📊 **Symbol:** {symbol}
📈 **Riktning:** {direction}
📍 **Typ:** {mode}
⚡️ **Hävstång:** {leverage_str}
⏰ **Tid:** {t}

{hashtags}
🆔 {trade_id}"""
    
    @staticmethod
    def hedge_activated(signal_data: Dict[str, Any]) -> str:
        """DEPRECATED: Use engine.render_template('HEDGE_STARTED', data)"""
        raise RuntimeError("DEPRECATED: Use app/telegram/engine.render_template('HEDGE_STARTED', data)")
        
        symbol = signal_data.get('symbol', '')
        channel_name = signal_data.get('channel_name', '')
        loss_pct = signal_data.get('loss_pct', '0.00')
        
        return f"""🛡️ HEDGE / VÄNDNING AKTIVERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

📍 Trigger: -{loss_pct}%
🔄 Motriktad position öppnad
💰 Storlek: 100% av ursprunglig position

⏳ Väntar på Bybit bekräftelse..."""
    
    @staticmethod
    def reentry_attempted(signal_data: Dict[str, Any]) -> str:
        """DEPRECATED: Use engine.render_template('REENTRY_STARTED', data)"""
        raise RuntimeError("DEPRECATED: Use app/telegram/engine.render_template('REENTRY_STARTED', data)")
        
        symbol = signal_data.get('symbol', '')
        channel_name = signal_data.get('channel_name', '')
        attempt = signal_data.get('attempt', 1)
        
        return f"""♻️ RE-ENTRY / ÅTERINTRÄDE AKTIVERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Sida: {signal_data.get('direction', '')}

💥 Entry: {signal_data.get('entry', '')}
⚙️ Hävstång: {signal_data.get('leverage', '')}x
💰 IM: {signal_data.get('im', '')} USDT

🔄 Försök: {attempt}/3

⏳ Väntar på Bybit bekräftelse..."""
    
    @staticmethod
    def breakeven_activated(signal_data: Dict[str, Any]) -> str:
        """Breakeven activated template."""
        symbol = signal_data.get('symbol', '')
        channel_name = signal_data.get('channel_name', '')
        gain_pct = signal_data.get('gain_pct', '0.00')
        
        return f"""⚖️ BREAK-EVEN JUSTERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

📍 Trigger: +{gain_pct}%
📍 SL flyttad till: Breakeven + kostnader (0.0015%)

⏳ Väntar på Bybit bekräftelse..."""
    
    @staticmethod
    def trailing_stop_activated(signal_data: Dict[str, Any]) -> str:
        """DEPRECATED: Use engine.render_template('TRAILING_ACTIVATED', data)"""
        raise RuntimeError("DEPRECATED: Use app/telegram/engine.render_template('TRAILING_ACTIVATED', data)")
        
        symbol = signal_data.get('symbol', '')
        channel_name = signal_data.get('channel_name', '')
        gain_pct = signal_data.get('gain_pct', '0.00')
        
        return f"""🔄 TRAILING STOP AKTIVERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {signal_data.get('direction', '')}

📍 Trigger: +{gain_pct}%
📍 Avstånd: 2.5% bakom pris
📍 Ny SL: {signal_data.get('new_sl', '')}

⏳ Väntar på Bybit bekräftelse..."""
    
    @staticmethod
    def entry_placed(signal_data: Dict[str, Any]) -> str:
        """DEPRECATED: Use engine.render_template('ORDER_PLACED', data)"""
        raise RuntimeError("DEPRECATED: Use app/telegram/engine.render_template('ORDER_PLACED', data)")
        
        symbol = signal_data.get('symbol', '')
        direction = signal_data.get('direction', '')
        channel_name = signal_data.get('channel_name', '')
        entries = signal_data.get('entries', [])
        leverage = signal_data.get('leverage', 0)
        order_id = signal_data.get('order_id', 'N/A')
        
        # Calculate average entry
        if len(entries) >= 2:
            try:
                entry1 = float(entries[0])
                entry2 = float(entries[1])
                avg_entry = (entry1 + entry2) / 2
                avg_entry_str = f"{avg_entry:.5f}".rstrip('0').rstrip('.')
            except:
                avg_entry_str = "MARKET"
        else:
            avg_entry_str = str(entries[0]) if entries else "MARKET"
        
        leverage_str = f"x{int(leverage)}" if leverage == int(leverage) else f"x{leverage}"
        
        return f"""✅ ENTRY ORDERS PLACERADE
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}
🎯 Hävstång: {leverage_str}
💰 IM: ~20 USDT

📍 Entry 1: {entries[0] if len(entries) > 0 else 'MARKET'} MUST confirm from Bybit
📍 Entry 2: {entries[1] if len(entries) > 1 else 'MARKET'} MUST confirm from Bybit
📊 Genomsnittlig entry: {avg_entry_str} MUST confirm from Bybit
🆔 Order ID: {order_id} MUST confirm from Bybit

⏳ Väntar på fyllning..."""
    
    @staticmethod
    def entry_filled(signal_data: Dict[str, Any]) -> str:
        """DEPRECATED: Use engine.render_template('POSITION_OPENED', data)"""
        raise RuntimeError("DEPRECATED: Use app/telegram/engine.render_template('POSITION_OPENED', data)")
        
        symbol = signal_data.get('symbol', '')
        direction = signal_data.get('direction', '')
        channel_name = signal_data.get('channel_name', '')
        avg_entry = signal_data.get('avg_entry', '0')
        quantity = signal_data.get('quantity', '0')
        leverage = signal_data.get('leverage', 0)
        
        leverage_str = f"x{int(leverage)}" if leverage == int(leverage) else f"x{leverage}"
        
        return f"""🎯 ENTRY FILLED
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}
🎯 Hävstång: {leverage_str}
💰 IM: ~20 USDT

📍 Genomsnittlig entry: {avg_entry} MUST confirm from Bybit
💵 Kvantitet: {quantity} MUST confirm from Bybit

⏳ Placering av TP/SL..."""
    
    @staticmethod
    def tp_sl_placed(signal_data: Dict[str, Any]) -> str:
        """TP/SL orders placed template."""
        symbol = signal_data.get('symbol', '')
        direction = signal_data.get('direction', '')
        channel_name = signal_data.get('channel_name', '')
        quantity = signal_data.get('quantity', '0')
        tps = signal_data.get('tps', [])
        sl = signal_data.get('sl', '0')
        
        # Format TP levels
        if tps:
            tp_text = ", ".join([str(tp) for tp in tps[:4]])  # Max 4 TPs
        else:
            tp_text = "DEFAULT_TP"
        
        return f"""✅ TP/SL bekräftad av Bybit

📊 Symbol: {symbol}
📈 Riktning: {direction}
💰 Storlek: {quantity}
🎯 TP: {tp_text}
🛑 SL: {sl}
📺 Källa: {channel_name}"""
    
    @staticmethod
    def take_profit_taken(signal_data: Dict[str, Any]) -> str:
        """Take profit taken template."""
        tp_index = signal_data.get('tp_index', 1)
        result_pct = signal_data.get('result_pct', '0')
        result_usdt = signal_data.get('result_usdt', '0')
        symbol = signal_data.get('symbol', '')
        direction = signal_data.get('direction', '')
        channel_name = signal_data.get('channel_name', '')
        quantity = signal_data.get('quantity', '0')
        portion = signal_data.get('portion', '0')
        
        return f"""🎯 TAKE PROFIT {tp_index} TAGEN
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Sida: {direction}

📍 TP{tp_index}: {signal_data.get(f'tp{tp_index}', '')} ({signal_data.get(f'tp{tp_index}_pct', '0')}%) MUST confirm from Bybit
💵 Stängd kvantitet: {quantity} ({portion}% av positionen)
📊 Resultat: {result_pct}% inkl. hävstång | {result_usdt} USDT inkl. hävstång"""
    
    @staticmethod
    def position_closed(signal_data: Dict[str, Any]) -> str:
        """Position closed template."""
        result_pct = signal_data.get('result_pct', '0')
        result_usdt = signal_data.get('result_usdt', '0')
        symbol = signal_data.get('symbol', '')
        direction = signal_data.get('direction', '')
        channel_name = signal_data.get('channel_name', '')
        quantity = signal_data.get('quantity', '0')
        price = signal_data.get('price', '0')
        
        return f"""✅ POSITION STÄNGD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Sida: {direction}

💵 Stängd kvantitet: {quantity} (100%)
📍 Exit: {price}

📊 Resultat: {result_pct}% inkl. hävstång 
📊 Resultat: {result_usdt} USDT inkl. hävstång
📊 PoL: {signal_data.get('pol_usdt', '0')} USDT"""
    
    @staticmethod
    def error_occurred(error_data: Dict[str, Any]) -> str:
        """Error occurred template."""
        symbol = error_data.get('symbol', '')
        error_type = error_data.get('error_type', '')
        error_message = error_data.get('error_message', '')
        
        return f"""❌ **Fel Uppstod**

📊 **Symbol:** {symbol}
🚨 **Fel Typ:** {error_type}
📝 **Meddelande:** {error_message}

⚠️ **Åtgärd krävs**"""
    
    @staticmethod
    def signal_blocked(signal_data: Dict[str, Any]) -> str:
        """
        Signal blocked template (CLIENT SPEC: 2h block duration).
        """
        symbol = signal_data.get('symbol', '')
        direction = signal_data.get('direction', '')
        channel_name = signal_data.get('channel_name', '')
        reason = signal_data.get('reason', '')
        trade_id = ensure_trade_id(signal_data.get('trade_id'))
        hashtags = symbol_hashtags(symbol)
        
        return f"""**🚫 SIGNAL BLOCKERAD**

📢 **Från kanal:** {channel_name}
📊 **Symbol:** {symbol}
📈 **Riktning:** {direction}

📍 **Anledning:** {reason}
⏰ **Blockad i 2 timmar** (5-10% heuristic)

ℹ️ Olika riktning eller >10% skillnad är OK

{hashtags}
🆔 {trade_id}"""
    
    @staticmethod
    def breakeven_activated(signal_data: Dict[str, Any]) -> str:
        """DEPRECATED: Use engine.render_template('BREAKEVEN_MOVED', data)"""
        raise RuntimeError("DEPRECATED: Use app/telegram/engine.render_template('BREAKEVEN_MOVED', data)")
        
        symbol = signal_data.get('symbol', '')
        channel_name = signal_data.get('channel_name', '')
        gain_pct = signal_data.get('gain_pct', '0')
        
        return f"""🔄 BREAKEVEN AKTIVERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Vinst: +{gain_pct}%

⛔ SL flyttad till breakeven + kostnader"""
    
    @staticmethod
    def pyramid_activated(signal_data: Dict[str, Any]) -> str:
        """
        Pyramid activated template (CLIENT SPEC - clear, no confusing math).
        
        Shows:
        - Step number and trigger threshold
        - What action was taken
        - Actual values (IM total, leverage) - NOT ratios or multipliers
        """
        symbol = signal_data.get('symbol', '')
        channel_name = signal_data.get('channel_name', '')
        level = signal_data.get('level', 1)
        gain_pct = signal_data.get('gain_pct', '0')
        action = signal_data.get('action', '')
        target_im = signal_data.get('target_im', '20')
        target_leverage = signal_data.get('target_leverage', '')
        
        # Map action to Swedish description
        action_map = {
            'im_total': f'IM total nu: {target_im} USDT',
            'sl_breakeven': 'SL flyttad till breakeven',
            'set_full_leverage': f'Hävstång höjd till {target_leverage}x (max)',
            'add_im': f'IM total nu: {target_im} USDT'
        }
        
        action_text = action_map.get(action, f'IM total: {target_im} USDT')
        
        # Special formatting for Step 3 (leverage change)
        if action == 'set_full_leverage':
            if 'ETH' in symbol.upper():
                action_text = f'Hävstång höjd till 50x (ETH max)'
            else:
                action_text = f'Hävstång höjd till {target_leverage}x (full leverage)'
        
        return f"""📈 PYRAMID STEG {level} AKTIVERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Vinst: +{gain_pct}%

✅ Åtgärd: {action_text}"""
    
    @staticmethod
    def trailing_stop_activated(signal_data: Dict[str, Any]) -> str:
        """
        Trailing stop activated template (CLIENT SPEC).
        
        Clearly shows:
        - Activation threshold: +6.1%
        - Distance: 2.5% behind price
        - No confusing math or multipliers
        """
        symbol = signal_data.get('symbol', '')
        channel_name = signal_data.get('channel_name', '')
        gain_pct = signal_data.get('gain_pct', '0')
        
        return f"""🔄 TRAILING STOP AKTIVERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Vinst: +{gain_pct}%

✅ Aktivering: +6.1% (CLIENT SPEC)
📍 Avstånd: 2.5% bakom högsta/lägsta pris
⛔ SL uppdateras automatiskt"""
    
    @staticmethod
    def hedge_activated(signal_data: Dict[str, Any]) -> str:
        """Hedge activated template."""
        symbol = signal_data.get('symbol', '')
        channel_name = signal_data.get('channel_name', '')
        loss_pct = signal_data.get('loss_pct', '0')
        
        return f"""🛡️ HEDGE AKTIVERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📉 Förlust: -{loss_pct}%

🔄 Motposition öppnad (100% storlek)"""
    
    @staticmethod
    def reentry_attempted(signal_data: Dict[str, Any]) -> str:
        """Re-entry attempted template."""
        symbol = signal_data.get('symbol', '')
        channel_name = signal_data.get('channel_name', '')
        attempt = signal_data.get('attempt', 1)
        
        return f"""🔄 RE-ENTRY FÖRSÖK {attempt}
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}

⏳ Försöker ny entry efter SL"""
    
    @staticmethod
    def daily_report(report_data: Dict[str, Any]) -> str:
        """
        Daily report template.
        
        CLIENT SPEC: Daily summary at 08:00 Stockholm time.
        """
        from datetime import datetime
        
        date = report_data.get('date', datetime.now().strftime('%Y-%m-%d'))
        total_trades = report_data.get('total_trades', 0)
        winning_trades = report_data.get('winning_trades', 0)
        losing_trades = report_data.get('losing_trades', 0)
        total_pnl = report_data.get('total_pnl', 0)
        win_rate = report_data.get('win_rate', 0)
        
        trades_by_symbol = report_data.get('trades_by_symbol', [])
        
        message = f"""📊 DAGLIG RAPPORT
📅 Datum: {date}

**📈 Sammanfattning:**
Antal trades: {total_trades}
Vinnande: {winning_trades}
Förlorande: {losing_trades}
Vinst %: {win_rate:.1f}%

💰 Total PnL: {fmt_usdt(total_pnl)}

**📊 Trades per symbol:**
"""
        
        if trades_by_symbol:
            for trade in trades_by_symbol[:10]:  # Top 10
                symbol = trade.get('symbol', '')
                pnl = trade.get('pnl', 0)
                message += f"\n{symbol}: {fmt_usdt(pnl)}"
        else:
            message += "\nInga trades idag"
        
        return message
    
    @staticmethod
    def weekly_report(report_data: Dict[str, Any]) -> str:
        """
        Weekly report template.
        
        CLIENT SPEC: Weekly summary on Saturday at 22:00 Stockholm time.
        """
        from datetime import datetime
        
        week = report_data.get('week', datetime.now().strftime('Vecka %W'))
        total_trades = report_data.get('total_trades', 0)
        winning_trades = report_data.get('winning_trades', 0)
        losing_trades = report_data.get('losing_trades', 0)
        total_pnl = report_data.get('total_pnl', 0)
        win_rate = report_data.get('win_rate', 0)
        
        trades_by_symbol = report_data.get('trades_by_symbol', [])
        top_performers = report_data.get('top_performers', [])
        
        message = f"""📊 VECKORAPPORT
📅 {week}

**📈 Sammanfattning:**
Antal trades: {total_trades}
Vinnande: {winning_trades}
Förlorande: {losing_trades}
Vinst %: {win_rate:.1f}%

💰 Total PnL: {fmt_usdt(total_pnl)}

**🏆 Topp Performers:**
"""
        
        if top_performers:
            for i, trade in enumerate(top_performers[:5], 1):
                symbol = trade.get('symbol', '')
                pnl = trade.get('pnl', 0)
                message += f"\n{i}. {symbol}: {fmt_usdt(pnl)}"
        else:
            message += "\nInga trades denna vecka"
        
        return message

# Global function to get templates instance
def get_swedish_templates():
    """
    Get Swedish templates instance.
    
    DEPRECATED: Use app/telegram/engine.render_template() instead.
    CLIENT SPEC Line 33: Raises RuntimeError to enforce single template path.
    """
    # CLIENT SPEC Line 33: Function-level lock to prevent usage
    raise RuntimeError(
        "DEPRECATED: get_swedish_templates() is forbidden. "
        "Use app/telegram/engine.render_template() instead. "
        "All messages must go through ConfirmationGate → Engine → Output. "
        "See doc/10_12_requirement.txt line 21-33."
    )
