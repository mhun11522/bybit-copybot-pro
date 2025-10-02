"""Swedish Telegram templates matching client requirements exactly."""

from typing import Dict, Any, List
from decimal import Decimal
from datetime import datetime
from app.core.strict_config import STRICT_CONFIG

class SwedishTemplates:
    """Swedish Telegram templates for all trade events."""
    
    @staticmethod
    def signal_received(signal_data: Dict[str, Any]) -> str:
        """Signal received template - varies by mode."""
        symbol = signal_data.get('symbol', '')
        direction = signal_data.get('direction', '')
        mode = signal_data.get('mode', 'DYNAMIC')
        channel_name = signal_data.get('channel_name', '')
        
        if mode == "SWING":
            return f"""
🎯 **Signal mottagen & kopierad**

📊 **Symbol:** {symbol}
📈 **Riktning:** {direction}
⚡ **Hävstång:** {signal_data.get('leverage', 'N/A')}x
📺 **Källa:** {channel_name}
⏰ **Tid:** {datetime.now().strftime('%H:%M:%S')}

🔄 **SWING MODE** - Långsiktig position
            """.strip()
        
        elif mode == "FAST":
            return f"""
🎯 **Signal mottagen & kopierad**

📊 **Symbol:** {symbol}
📈 **Riktning:** {direction}
⚡ **Hävstång:** {signal_data.get('leverage', 'N/A')}x
📺 **Källa:** {channel_name}
⏰ **Tid:** {datetime.now().strftime('%H:%M:%S')}

⚡ **FAST MODE** - Snabb position
            """.strip()
        
        else:  # DYNAMIC
            return f"""
🎯 **Signal mottagen & kopierad**

📊 **Symbol:** {symbol}
📈 **Riktning:** {direction}
⚡ **Hävstång:** {signal_data.get('leverage', 'N/A')}x
📺 **Källa:** {channel_name}
⏰ **Tid:** {datetime.now().strftime('%H:%M:%S')}

🔄 **DYNAMISK MODE** - Anpassad position
            """.strip()
    
    @staticmethod
    def order_placed(order_data: Dict[str, Any]) -> str:
        """Order placed template."""
        symbol = order_data.get('symbol', '')
        direction = order_data.get('direction', '')
        order_type = order_data.get('order_type', 'Limit')
        qty = order_data.get('qty', '')
        price = order_data.get('price', '')
        order_id = order_data.get('order_id', '')
        post_only = order_data.get('post_only', False)
        
        return f"""
✅ **Order placerad**

📊 **Symbol:** {symbol}
📈 **Riktning:** {direction}
💰 **Typ:** {order_type}
📦 **Storlek:** {qty}
💵 **Pris:** {price}
🆔 **Order-ID:** {order_id}
🔒 **Post-Only:** {'Ja' if post_only else 'Nej'}

⏳ **Väntar på fyllning...**
            """.strip()
    
    @staticmethod
    def entry_filled(fill_data: Dict[str, Any]) -> str:
        """Entry filled template."""
        symbol = fill_data.get('symbol', '')
        direction = fill_data.get('direction', '')
        qty = fill_data.get('qty', '')
        price = fill_data.get('price', '')
        im = fill_data.get('im', '')
        leverage = fill_data.get('leverage', '')
        
        return f"""
🎯 **Entry fylld**

📊 **Symbol:** {symbol}
📈 **Riktning:** {direction}
💰 **Storlek:** {qty}
💵 **Pris:** {price}
💎 **IM:** {im} USDT
⚡ **Hävstång:** {leverage}x

✅ **Position öppnad**
            """.strip()
    
    @staticmethod
    def tp_sl_placed(tp_sl_data: Dict[str, Any]) -> str:
        """TP/SL placed template."""
        symbol = tp_sl_data.get('symbol', '')
        tps = tp_sl_data.get('tps', [])
        sl = tp_sl_data.get('sl', '')
        reduce_only = tp_sl_data.get('reduce_only', False)
        trigger_by = tp_sl_data.get('trigger_by', 'MarkPrice')
        
        tp_text = ', '.join([str(tp) for tp in tps]) if tps else 'Ingen'
        
        return f"""
🛡️ **TP/SL placerad**

📊 **Symbol:** {symbol}
🎯 **TP:** {tp_text}
🛑 **SL:** {sl}
🔄 **Reduce-Only:** {'Ja' if reduce_only else 'Nej'}
📊 **Trigger:** {trigger_by}

✅ **Skydd aktiverat**
            """.strip()
    
    @staticmethod
    def tp_hit(tp_data: Dict[str, Any]) -> str:
        """TP hit template."""
        symbol = tp_data.get('symbol', '')
        tp_price = tp_data.get('tp_price', '')
        pnl = tp_data.get('pnl', '')
        pnl_pct = tp_data.get('pnl_pct', '')
        
        return f"""
🎯 **TP träffad**

📊 **Symbol:** {symbol}
💰 **TP Pris:** {tp_price}
💵 **PnL:** {pnl} USDT
📈 **PnL %:** {pnl_pct}%

✅ **Vinst realiserad**
            """.strip()
    
    @staticmethod
    def sl_hit(sl_data: Dict[str, Any]) -> str:
        """SL hit template."""
        symbol = sl_data.get('symbol', '')
        sl_price = sl_data.get('sl_price', '')
        pnl = sl_data.get('pnl', '')
        pnl_pct = sl_data.get('pnl_pct', '')
        
        return f"""
🛑 **SL träffad**

📊 **Symbol:** {symbol}
💰 **SL Pris:** {sl_price}
💵 **PnL:** {pnl} USDT
📈 **PnL %:** {pnl_pct}%

❌ **Förlust realiserad**
            """.strip()
    
    @staticmethod
    def breakeven_applied(be_data: Dict[str, Any]) -> str:
        """Breakeven applied template."""
        symbol = be_data.get('symbol', '')
        be_price = be_data.get('be_price', '')
        pyramid_level = be_data.get('pyramid_level', 0)
        
        return f"""
🔄 **Breakeven tillämpad**

📊 **Symbol:** {symbol}
💰 **BE Pris:** {be_price}
📊 **Pyramid Nivå:** {pyramid_level}

✅ **Risk eliminerad**
            """.strip()
    
    @staticmethod
    def pyramid_level(pyramid_data: Dict[str, Any]) -> str:
        """Pyramid level template."""
        symbol = pyramid_data.get('symbol', '')
        level = pyramid_data.get('level', 0)
        action = pyramid_data.get('action', '')
        new_im = pyramid_data.get('new_im', '')
        new_leverage = pyramid_data.get('new_leverage', '')
        
        return f"""
📊 **Pyramid Nivå {level}**

📊 **Symbol:** {symbol}
🔄 **Åtgärd:** {action}
💎 **Ny IM:** {new_im} USDT
⚡ **Ny Hävstång:** {new_leverage}x

✅ **Pyramid uppgraderad**
            """.strip()
    
    @staticmethod
    def trailing_activated(trailing_data: Dict[str, Any]) -> str:
        """Trailing stop activated template."""
        symbol = trailing_data.get('symbol', '')
        trigger_price = trailing_data.get('trigger_price', '')
        initial_sl = trailing_data.get('initial_sl', '')
        
        return f"""
📈 **Trailing Stop Aktiverad**

📊 **Symbol:** {symbol}
💰 **Trigger Pris:** {trigger_price}
🛑 **Initial SL:** {initial_sl}

✅ **Trailing aktivt**
            """.strip()
    
    @staticmethod
    def trailing_updated(trailing_data: Dict[str, Any]) -> str:
        """Trailing stop updated template."""
        symbol = trailing_data.get('symbol', '')
        new_sl = trailing_data.get('new_sl', '')
        high_price = trailing_data.get('high_price', '')
        
        return f"""
📈 **Trailing Stop Uppdaterad**

📊 **Symbol:** {symbol}
🛑 **Ny SL:** {new_sl}
📊 **Högsta Pris:** {high_price}

✅ **Trailing uppdaterat**
            """.strip()
    
    @staticmethod
    def hedge_applied(hedge_data: Dict[str, Any]) -> str:
        """Hedge applied template."""
        symbol = hedge_data.get('symbol', '')
        hedge_direction = hedge_data.get('hedge_direction', '')
        hedge_size = hedge_data.get('hedge_size', '')
        hedge_tp = hedge_data.get('hedge_tp', '')
        hedge_sl = hedge_data.get('hedge_sl', '')
        
        return f"""
🔄 **Hedge Tillämpad**

📊 **Symbol:** {symbol}
📈 **Hedge Riktning:** {hedge_direction}
💰 **Hedge Storlek:** {hedge_size}
🎯 **Hedge TP:** {hedge_tp}
🛑 **Hedge SL:** {hedge_sl}

✅ **Hedge aktiv**
            """.strip()
    
    @staticmethod
    def reentry_attempted(reentry_data: Dict[str, Any]) -> str:
        """Re-entry attempted template."""
        symbol = reentry_data.get('symbol', '')
        attempt = reentry_data.get('attempt', 0)
        max_attempts = reentry_data.get('max_attempts', 3)
        reentry_prices = reentry_data.get('reentry_prices', [])
        
        prices_text = ', '.join([str(p) for p in reentry_prices])
        
        return f"""
🔄 **Re-entry Försök {attempt}/{max_attempts}**

📊 **Symbol:** {symbol}
💰 **Re-entry Priser:** {prices_text}

⏳ **Väntar på fyllning...**
            """.strip()
    
    @staticmethod
    def position_closed(close_data: Dict[str, Any]) -> str:
        """Position closed template."""
        symbol = close_data.get('symbol', '')
        reason = close_data.get('reason', '')
        final_pnl = close_data.get('final_pnl', '')
        final_pnl_pct = close_data.get('final_pnl_pct', '')
        
        return f"""
🔚 **Position Stängd**

📊 **Symbol:** {symbol}
📝 **Anledning:** {reason}
💵 **Slutlig PnL:** {final_pnl} USDT
📈 **Slutlig PnL %:** {final_pnl_pct}%

✅ **Position avslutad**
            """.strip()
    
    @staticmethod
    def error_occurred(error_data: Dict[str, Any]) -> str:
        """Error occurred template."""
        symbol = error_data.get('symbol', '')
        error_type = error_data.get('error_type', '')
        error_message = error_data.get('error_message', '')
        
        return f"""
❌ **Fel Uppstod**

📊 **Symbol:** {symbol}
🚨 **Fel Typ:** {error_type}
📝 **Meddelande:** {error_message}

⚠️ **Åtgärd krävs**
            """.strip()
    
    @staticmethod
    def daily_report(report_data: Dict[str, Any]) -> str:
        """Daily report template."""
        date = report_data.get('date', '')
        total_trades = report_data.get('total_trades', 0)
        winning_trades = report_data.get('winning_trades', 0)
        losing_trades = report_data.get('losing_trades', 0)
        winrate = report_data.get('winrate', 0)
        total_pnl = report_data.get('total_pnl', 0)
        total_pnl_pct = report_data.get('total_pnl_pct', 0)
        top_symbols = report_data.get('top_symbols', [])
        
        top_symbols_text = '\n'.join([f"  {i+1}. {symbol}: {pnl} USDT" for i, (symbol, pnl) in enumerate(top_symbols[:5])])
        
        return f"""
📊 **Daglig Rapport - {date}**

📈 **Handel Statistik:**
  • Totalt antal: {total_trades}
  • Vinnande: {winning_trades}
  • Förlorande: {losing_trades}
  • Vinstprocent: {winrate:.1f}%

💰 **PnL Sammanfattning:**
  • Total PnL: {total_pnl:.2f} USDT
  • Total PnL %: {total_pnl_pct:.2f}%

🏆 **Topp Symboler:**
{top_symbols_text}

⏰ **Rapport genererad:** {datetime.now().strftime('%H:%M:%S')}
            """.strip()
    
    @staticmethod
    def weekly_report(report_data: Dict[str, Any]) -> str:
        """Weekly report template."""
        week = report_data.get('week', '')
        total_trades = report_data.get('total_trades', 0)
        winning_trades = report_data.get('winning_trades', 0)
        winrate = report_data.get('winrate', 0)
        total_pnl = report_data.get('total_pnl', 0)
        total_pnl_pct = report_data.get('total_pnl_pct', 0)
        reentries = report_data.get('reentries', 0)
        hedges = report_data.get('hedges', 0)
        max_pyramid = report_data.get('max_pyramid', 0)
        error_tally = report_data.get('error_tally', {})
        
        error_text = '\n'.join([f"  • {error_type}: {count}" for error_type, count in error_tally.items()])
        
        return f"""
📊 **Veckorapport - Vecka {week}**

📈 **Handel Statistik:**
  • Totalt antal: {total_trades}
  • Vinnande: {winning_trades}
  • Vinstprocent: {winrate:.1f}%

💰 **PnL Sammanfattning:**
  • Total PnL: {total_pnl:.2f} USDT
  • Total PnL %: {total_pnl_pct:.2f}%

🔄 **Strategi Statistik:**
  • Re-entries: {reentries}
  • Hedges: {hedges}
  • Max Pyramid: {max_pyramid}

🚨 **Fel Statistik:**
{error_text}

⏰ **Rapport genererad:** {datetime.now().strftime('%H:%M:%S')}
            """.strip()

# Global templates instance
_templates_instance = None

def get_swedish_templates() -> SwedishTemplates:
    """Get global Swedish templates instance."""
    global _templates_instance
    if _templates_instance is None:
        _templates_instance = SwedishTemplates()
    return _templates_instance