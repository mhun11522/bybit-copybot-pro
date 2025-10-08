"""Swedish Telegram templates with exact client requirements."""

from typing import Dict, Any
from decimal import Decimal

class SwedishTemplatesV2:
    """Swedish templates with exact client requirements and Bybit confirmations."""
    
    @staticmethod
    def signal_received(signal_data: Dict[str, Any]) -> str:
        """Signal mottagen & kopierad template."""
        symbol = signal_data.get('symbol', '')
        direction = signal_data.get('direction', '')
        mode = signal_data.get('mode', '')
        channel_name = signal_data.get('channel_name', '')
        leverage = signal_data.get('leverage', 0)
        
        # Format leverage with proper notation
        leverage_str = f"x{int(leverage)}" if leverage == int(leverage) else f"x{leverage}"
        
        if mode == "SWING":
            return f"""✅ Signal mottagen & kopierad
🕒 Tid: {datetime.now().strftime('%H:%M:%S')}
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}
📍 Typ: Swing

⚙️ Hävstång: {leverage_str}
💰 IM: ~20 USDT

⏳ Väntar på Bybit bekräftelse..."""
        
        elif mode == "FAST":
            return f"""📢 SIGNAL MOTTAGEN & KOPIERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}
🎯 Strategi: FAST {leverage_str}
💰 IM: ~20 USDT

⏳ Väntar på Bybit bekräftelse..."""
        
        else:  # DYNAMIC
            return f"""📢 SIGNAL MOTTAGEN & KOPIERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}
🎯 Strategi: DYNAMISK {leverage_str}
💰 IM: ~20 USDT

⏳ Väntar på Bybit bekräftelse..."""
    
    @staticmethod
    def hedge_activated(signal_data: Dict[str, Any]) -> str:
        """Hedge activated template."""
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
        """Re-entry attempted template."""
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
        """Trailing stop activated template."""
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
        """Entry order placed template."""
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
        """Entry filled template."""
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
        tps = signal_data.get('tps', [])
        sl = signal_data.get('sl', '0')
        
        tp_text = ""
        for i, tp in enumerate(tps[:4], 1):  # Max 4 TPs
            tp_text += f"📍 TP{i}: {tp} MUST confirm from Bybit\n"
        
        return f"""🎯 TP/SL ORDERS PLACERADE
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}

{tp_text}⛔ SL: {sl} MUST confirm from Bybit

✅ Position aktiv - övervakning startad"""
    
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
        """Signal blocked template."""
        symbol = signal_data.get('symbol', '')
        direction = signal_data.get('direction', '')
        channel_name = signal_data.get('channel_name', '')
        reason = signal_data.get('reason', '')
        
        return f"""🚫 SIGNAL BLOCKERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Riktning: {direction}

📍 Anledning: {reason}
⏰ Blockad i 3 timmar (5% tolerans)

ℹ️ Olika riktning eller >5% skillnad är OK"""
    
    @staticmethod
    def breakeven_activated(signal_data: Dict[str, Any]) -> str:
        """Breakeven activated template."""
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
        """Pyramid activated template."""
        symbol = signal_data.get('symbol', '')
        channel_name = signal_data.get('channel_name', '')
        level = signal_data.get('level', 1)
        gain_pct = signal_data.get('gain_pct', '0')
        new_im = signal_data.get('new_im', '20')
        new_leverage = signal_data.get('new_leverage', 'x10')
        
        return f"""📈 PYRAMID NIVÅ {level} AKTIVERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Vinst: +{gain_pct}%

💰 Ny IM: {new_im} USDT
🎯 Ny hävstång: {new_leverage}"""
    
    @staticmethod
    def trailing_stop_activated(signal_data: Dict[str, Any]) -> str:
        """Trailing stop activated template."""
        symbol = signal_data.get('symbol', '')
        channel_name = signal_data.get('channel_name', '')
        gain_pct = signal_data.get('gain_pct', '0')
        
        return f"""🔄 TRAILING STOP AKTIVERAD
📢 Från kanal: {channel_name}
📊 Symbol: {symbol}
📈 Vinst: +{gain_pct}%

⛔ SL följer priset (2.5% bakom)"""
    
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

# Global function to get templates instance
def get_swedish_templates():
    """Get Swedish templates instance."""
    return SwedishTemplatesV2()
