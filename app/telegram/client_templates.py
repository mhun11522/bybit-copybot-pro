"""Client-specified Telegram templates - EXACT match to requirements."""

from typing import Dict, Any, List
from decimal import Decimal
from datetime import datetime
from app.core.strict_config import STRICT_CONFIG

class ClientTemplates:
    """Exact templates matching client specification."""
    
    @staticmethod
    def signal_received_swing(signal_data: Dict[str, Any]) -> str:
        """1) Signal mottagen & kopierad – Swing"""
        return f"""✅ Signal mottagen & kopierad 
🕒 Tid: {datetime.now().strftime('%H:%M:%S')}
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Riktning: {signal_data.get('direction', '')}
📍 Typ: Swing

⚙️ Hävstång: x6
💰 IM: {signal_data.get('im', '20')} USDT"""

    @staticmethod
    def signal_received_dynamic(signal_data: Dict[str, Any]) -> str:
        """2) Signal mottagen & kopierad – Dynamisk"""
        entries = signal_data.get('entries', [])
        tps = signal_data.get('tps', [])
        sl = signal_data.get('sl', '')
        
        tp_lines = ""
        for i, tp in enumerate(tps[:4], 1):
            tp_pct = signal_data.get(f'tp{i}_pct', '0')
            tp_lines += f"🎯 TP{i}: {tp} ({tp_pct}%)\n"
        
        return f"""✅ Signal mottagen & kopierad 
🕒 Tid: {datetime.now().strftime('%H:%M:%S')}
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Riktning: {signal_data.get('direction', '')}

💥 Entry: {entries[0] if entries else 'N/A'}
{tp_lines}🚩 SL: {sl} ({signal_data.get('sl_pct', '0')}%)

⚙️ Hävstång: Dynamisk
💰 IM: {signal_data.get('im', '20')} USDT"""

    @staticmethod
    def signal_received_fast(signal_data: Dict[str, Any]) -> str:
        """3) Signal mottagen & kopierad – Fast"""
        entries = signal_data.get('entries', [])
        tps = signal_data.get('tps', [])
        sl = signal_data.get('sl', '')
        
        tp_lines = ""
        for i, tp in enumerate(tps[:4], 1):
            tp_pct = signal_data.get(f'tp{i}_pct', '0')
            tp_lines += f"🎯 TP{i}: {tp} ({tp_pct}%)\n"
        
        return f"""✅ Signal mottagen & kopierad 
🕒 Tid: {datetime.now().strftime('%H:%M:%S')}
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Riktning: {signal_data.get('direction', '')}

💥 Entry: {entries[0] if entries else 'N/A'}
{tp_lines}🚩 SL: {sl} ({signal_data.get('sl_pct', '0')}%)

⚙️ Hävstång: Fast x10
💰 IM: {signal_data.get('im', '20')} USDT"""

    @staticmethod
    def order_placed_swing(signal_data: Dict[str, Any]) -> str:
        """Order placerad – Swing"""
        return f"""✅ Order placerad – Swing
🕒 Tid: {datetime.now().strftime('%H:%M:%S')}
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Riktning: {signal_data.get('direction', '')}
📍 Typ: Swing

⚙️ Hävstång: x6
💰 IM: {signal_data.get('im', '20')} USDT MUST confirm from bybit ({signal_data.get('im_actual', '20')} USDT)
☑️ Post-Only | MUST confirm from bybit
☑️ Reduce-Only MUST confirm from bybit
🔑 Order-ID: {signal_data.get('order_id', 'N/A')} MUST confirm from bybit"""

    @staticmethod
    def order_placed_dynamic(signal_data: Dict[str, Any]) -> str:
        """Order placerad – Dynamisk"""
        entries = signal_data.get('entries', [])
        tps = signal_data.get('tps', [])
        sl = signal_data.get('sl', '')
        
        tp_lines = ""
        for i, tp in enumerate(tps[:4], 1):
            tp_pct = signal_data.get(f'tp{i}_pct', '0')
            tp_lines += f"🎯 TP{i}: {tp} ({tp_pct}%)\n"
        
        return f"""✅ Order placerad – Dynamisk
🕒 Tid: {datetime.now().strftime('%H:%M:%S')}
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Riktning: {signal_data.get('direction', '')}

💥 Entry: {entries[0] if entries else 'N/A'}
{tp_lines}🚩 SL: {sl} ({signal_data.get('sl_pct', '0')}%)

⚙️ Hävstång: Dynamisk
💰 IM: {signal_data.get('im', '20')} USDT MUST confirm from bybit ({signal_data.get('im_actual', '20')} USDT)
☑️ Post-Only | MUST confirm from bybit
☑️ Reduce-Only MUST confirm from bybit
🔑 Order-ID: {signal_data.get('order_id', 'N/A')} MUST confirm from bybit"""

    @staticmethod
    def order_placed_fast(signal_data: Dict[str, Any]) -> str:
        """Order placerad – Fast"""
        entries = signal_data.get('entries', [])
        tps = signal_data.get('tps', [])
        sl = signal_data.get('sl', '')
        
        tp_lines = ""
        for i, tp in enumerate(tps[:4], 1):
            tp_pct = signal_data.get(f'tp{i}_pct', '0')
            tp_lines += f"🎯 TP{i}: {tp} ({tp_pct}%)\n"
        
        return f"""✅ Order placerad – Fast
🕒 Tid: {datetime.now().strftime('%H:%M:%S')}
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Riktning: {signal_data.get('direction', '')}

💥 Entry: {entries[0] if entries else 'N/A'}
{tp_lines}🚩 SL: {sl} ({signal_data.get('sl_pct', '0')}%)

⚙️ Hävstång: Fast x10
💰 IM: {signal_data.get('im', '20')} USDT MUST confirm from bybit ({signal_data.get('im_actual', '20')} USDT)
☑️ Post-Only | MUST confirm from bybit
☑️ Reduce-Only MUST confirm from bybit
🔑 Order-ID: {signal_data.get('order_id', 'N/A')} MUST confirm from bybit"""

    @staticmethod
    def position_opened_swing(signal_data: Dict[str, Any]) -> str:
        """Position öppnad – Swing"""
        return f"""✅ Position öppnad – Swing
🕒 Tid: {datetime.now().strftime('%H:%M:%S')}
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Riktning: {signal_data.get('direction', '')}
📍 Typ: Swing

⚙️ Hävstång: x6
💰 IM: {signal_data.get('im', '20')} USDT MUST confirm from bybit ({signal_data.get('im_actual', '20')} USDT)
☑️ Post-Only | MUST confirm from bybit
☑️ Reduce-Only MUST confirm from bybit
🔑 Order-ID: {signal_data.get('order_id', 'N/A')} MUST confirm from bybit"""

    @staticmethod
    def position_opened_dynamic(signal_data: Dict[str, Any]) -> str:
        """Position öppnad – Dynamisk"""
        entries = signal_data.get('entries', [])
        tps = signal_data.get('tps', [])
        sl = signal_data.get('sl', '')
        
        tp_lines = ""
        for i, tp in enumerate(tps[:4], 1):
            tp_pct = signal_data.get(f'tp{i}_pct', '0')
            tp_lines += f"🎯 TP{i}: {tp} ({tp_pct}%)\n"
        
        return f"""✅ Position öppnad – Dynamisk
🕒 Tid: {datetime.now().strftime('%H:%M:%S')}
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Riktning: {signal_data.get('direction', '')}

💥 Entry: {entries[0] if entries else 'N/A'}
{tp_lines}🚩 SL: {sl} ({signal_data.get('sl_pct', '0')}%)

⚙️ Hävstång: Dynamisk
💰 IM: {signal_data.get('im', '20')} USDT MUST confirm from bybit ({signal_data.get('im_actual', '20')} USDT)
☑️ Post-Only | MUST confirm from bybit
☑️ Reduce-Only MUST confirm from bybit
🔑 Order-ID: {signal_data.get('order_id', 'N/A')} MUST confirm from bybit"""

    @staticmethod
    def position_opened_fast(signal_data: Dict[str, Any]) -> str:
        """Position öppnad – Fast"""
        entries = signal_data.get('entries', [])
        tps = signal_data.get('tps', [])
        sl = signal_data.get('sl', '')
        
        tp_lines = ""
        for i, tp in enumerate(tps[:4], 1):
            tp_pct = signal_data.get(f'tp{i}_pct', '0')
            tp_lines += f"🎯 TP{i}: {tp} ({tp_pct}%)\n"
        
        return f"""✅ Position öppnad – Fast
🕒 Tid: {datetime.now().strftime('%H:%M:%S')}
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Riktning: {signal_data.get('direction', '')}

💥 Entry: {entries[0] if entries else 'N/A'}
{tp_lines}🚩 SL: {sl} ({signal_data.get('sl_pct', '0')}%)

⚙️ Hävstång: Fast x10
💰 IM: {signal_data.get('im', '20')} USDT MUST confirm from bybit ({signal_data.get('im_actual', '20')} USDT)
☑️ Post-Only | MUST confirm from bybit
☑️ Reduce-Only MUST confirm from bybit
🔑 Order-ID: {signal_data.get('order_id', 'N/A')} MUST confirm from bybit"""

    @staticmethod
    def entry_1_taken(signal_data: Dict[str, Any]) -> str:
        """📌 ENTRY 1 TAGEN"""
        return f"""📌 ENTRY 1 TAGEN
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}

💥 Entry: {signal_data.get('entry1', '')}
💵 Kvantitet: {signal_data.get('quantity1', '')}
💰 IM: {signal_data.get('im1', '10')} USDT (IM totalt: {signal_data.get('im_total', '20')} USDT) MUST confirm from bybit ({signal_data.get('im1_actual', '10')} USDT) (like 50/50)"""

    @staticmethod
    def entry_2_taken(signal_data: Dict[str, Any]) -> str:
        """📌 ENTRY 2 TAGEN"""
        return f"""📌 ENTRY 2 TAGEN
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}

💥 Entry: {signal_data.get('entry2', '')}
💵 Kvantitet: {signal_data.get('quantity2', '')}
💰 IM: {signal_data.get('im2', '10')} USDT (IM totalt: {signal_data.get('im_total', '20')} USDT) MUST confirm from bybit ({signal_data.get('im2_actual', '10')} USDT) (like 50/50)"""

    @staticmethod
    def entry_combined(signal_data: Dict[str, Any]) -> str:
        """📌 Sammanställning av ENTRY 1 + ENTRY 2"""
        return f"""📌 Sammanställning av ENTRY 1 + ENTRY 2
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}

📌 ENTRY 1 
💥 Entry: {signal_data.get('entry1', '')}
💵 Kvantitet: {signal_data.get('quantity1', '')}
💰 IM: {signal_data.get('im1', '10')} USDT (IM totalt: {signal_data.get('im_total', '20')} USDT)
⚠️ Måste bekräftas i Bybit (ex. 16,78 USDT eller 21,56 USDT ≈50/50)

📌 ENTRY 2
💥 Entry: {signal_data.get('entry2', '')}
💵 Kvantitet: {signal_data.get('quantity2', '')}
💰 IM: {signal_data.get('im2', '10')} USDT (IM totalt: {signal_data.get('im_total', '20')} USDT)
⚠️ Måste bekräftas i Bybit (ex. 16,78 USDT eller 21,56 USDT ≈50/50)

📌 SAMMANSATT POSITION
💥 Genomsnittligt Entry: {signal_data.get('avg_entry', '')} ← volymvägt mellan entry1 & entry2
💵 Total kvantitet: {signal_data.get('quantity_total', '')}
💰 IM totalt: {signal_data.get('im_total', '20')} USDT
⚠️ Bekräfta i Bybit"""

    @staticmethod
    def take_profit_taken(signal_data: Dict[str, Any]) -> str:
        """🎯 TAKE PROFIT X TAGEN"""
        tp_index = signal_data.get('tp_index', 1)
        result_pct = signal_data.get('result_pct', '0')
        result_usdt = signal_data.get('result_usdt', '0')
        
        # Ensure the result shows the correct USDT amount (not inflated)
        # For 20 USDT trade with 1.59% gain, should show ~3.2 USDT, not 32 USDT
        return f"""🎯 TAKE PROFIT {tp_index} TAGEN
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Sida: {signal_data.get('direction', '')}

📍 TP{tp_index}: {signal_data.get(f'tp{tp_index}', '')} ({signal_data.get(f'tp{tp_index}_pct', '0')}%) MUST confirm from Bybit
💵 Stängd kvantitet: {signal_data.get('quantity', '')} ({signal_data.get('portion', '0')}% av positionen)
📊 Resultat: {result_pct}% inkl. hävstång | {result_usdt} USDT inkl. hävstång"""

    @staticmethod
    def pyramid_step(signal_data: Dict[str, Any]) -> str:
        """📈 PYRAMID steg"""
        level = signal_data.get('level', 1)
        step = signal_data.get('step', 1)
        trigger_pct = signal_data.get('trigger_pct', '0')
        
        if step == 1:  # +1.5%: Check IM
            return f"""📈 PYRAMID {level} steg 1, 1,5% kontrollera IM
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Riktning: {signal_data.get('direction', '')}

💥 Pris: {signal_data.get('price', '')} (+{trigger_pct}%) (måste bekräftas av Bybit)
💵 Tillagd kvantitet: {signal_data.get('quantity', '')} (måste bekräftas av Bybit)
💰 IM påfyllnad: +{signal_data.get('im', '20')} USDT (IM totalt: {signal_data.get('im_total', '40')} USDT) (måste bekräftas av Bybit)"""
        
        elif step == 2:  # +2.3%: SL to BE
            return f"""📈 PYRAMID {level} steg 2, 2,3% Kontroll: SL flyttas till Break Even
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Riktning: {signal_data.get('direction', '')}

💥 Pris: {signal_data.get('price', '')} (+2,3%) 
🛡️ SL justerad till Break Even (måste bekräftas av Bybit)"""
        
        elif step == 3:  # +2.4%: Leverage max
            return f"""📈 PYRAMID {level} steg 3, 2,4% Kontroll: Fyll upp IM till 40 USDT
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Riktning: {signal_data.get('direction', '')}

💥 Pris: {signal_data.get('price', '')} (+2,4%) 
💰 IM-påfyllnad: {signal_data.get('im', '20')} USDT (IM totalt: 40 USDT) (måste bekräftas av Bybit)"""
        
        elif step == 4:  # +2.5%: Leverage raised
            return f"""📈 PYRAMID {level} steg 4, 2,5% Kontroll: Hävstång höjd
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Riktning: {signal_data.get('direction', '')}

💥 Pris: {signal_data.get('price', '')} (+2,5%) 
⚙️ Hävstång höjd till {signal_data.get('leverage', '50')}x (enligt regler, ev. max 50x) (måste bekräftas av Bybit)"""
        
        elif step == 5:  # +4.0%: IM to 60 USDT
            return f"""📈 PYRAMID {level} steg 5, 4,0% Kontroll: Fyll upp IM till 60 USDT
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Riktning: {signal_data.get('direction', '')}

💥 Pris: {signal_data.get('price', '')} (+4,0%) 
💰 IM-påfyllnad: {signal_data.get('im', '20')} USDT (IM totalt: 60 USDT) (måste bekräftas av Bybit)"""
        
        elif step == 6:  # +6.0%: IM to 80 USDT
            return f"""📈 PYRAMID {level} steg 6, 6,0% Kontroll: Fyll upp IM till 80 USDT
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Riktning: {signal_data.get('direction', '')}

💥 Pris: {signal_data.get('price', '')} (+6,0%) 
💰 IM-påfyllnad: {signal_data.get('im', '20')} USDT (IM totalt: 80 USDT) (måste bekräftas av Bybit)"""
        
        elif step == 7:  # +8.6%: IM to 100 USDT
            return f"""📈 PYRAMID {level} steg 7, 8,6% Kontroll: Fyll upp IM till 100 USDT
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Riktning: {signal_data.get('direction', '')}

💥 Pris: {signal_data.get('price', '')} (+8,6%) 
💰 IM-påfyllnad: {signal_data.get('im', '20')} USDT (IM totalt: 100 USDT) (måste bekräftas av Bybit)"""

    @staticmethod
    def trailing_stop_activated(signal_data: Dict[str, Any]) -> str:
        """🔄 TRAILING STOP AKTIVERAD"""
        return f"""🔄 TRAILING STOP AKTIVERAD
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Riktning: {signal_data.get('direction', '')}

📍 Trigger: +{signal_data.get('trigger_pct', '6.1')}%
📍 Avstånd: {signal_data.get('distance_pct', '2.5')}% bakom pris
📍 Ny SL: {signal_data.get('new_sl', '')}"""

    @staticmethod
    def break_even_adjusted(signal_data: Dict[str, Any]) -> str:
        """⚖️ BREAK-EVEN JUSTERAD"""
        return f"""⚖️ BREAK-EVEN JUSTERAD
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}

📍 SL flyttad till: {signal_data.get('sl_moved', '')}"""

    @staticmethod
    def hedge_executed(signal_data: Dict[str, Any]) -> str:
        """🛡️ HEDGE / VÄNDNING AKTIVERAD"""
        return f"""🛡️ HEDGE / VÄNDNING AKTIVERAD
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}

📈 Tidigare position: {signal_data.get('old_side', '')} (stängd)
📉 Ny motriktad position: {signal_data.get('new_side', '')}
💥 Entry: {signal_data.get('entry', '')}

⚙️ Hävstång: {signal_data.get('leverage', '')}x
💰 IM: {signal_data.get('im', '20')} USDT (MUST confirm from Bybit)"""

    @staticmethod
    def hedge_closed(signal_data: Dict[str, Any]) -> str:
        """🛡️ HEDGE / VÄNDNING AVSLUTAD"""
        return f"""🛡️ HEDGE / VÄNDNING AVSLUTAD
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}

📈 Stängd position: {signal_data.get('old_side', '')}
💥 Stängningspris: {signal_data.get('exit', '')}

⚙️ Hävstång (avslutad): {signal_data.get('leverage', '')}x"""

    @staticmethod
    def reentry_executed(signal_data: Dict[str, Any]) -> str:
        """♻️ RE-ENTRY / ÅTERINTRÄDE AKTIVERAD"""
        return f"""♻️ RE-ENTRY / ÅTERINTRÄDE AKTIVERAD
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Sida: {signal_data.get('direction', '')}

💥 Entry: {signal_data.get('entry', '')}
⚙️ Hävstång: {signal_data.get('leverage', '')}x
💰 IM: {signal_data.get('im', '20')} USDT (IM totalt: {signal_data.get('im_total', '20')} USDT)"""

    @staticmethod
    def reentry_closed(signal_data: Dict[str, Any]) -> str:
        """♻️ RE-ENTRY / ÅTERINTRÄDE AVSLUTAD"""
        return f"""♻️ RE-ENTRY / ÅTERINTRÄDE AVSLUTAD
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Sida: {signal_data.get('direction', '')}

💥 Exit: {signal_data.get('exit', '')}
📉 Resultat: {signal_data.get('pnl', '0')} USDT ({signal_data.get('pnl_pct', '0')}%)
⚙️ Hävstång (avslutad): {signal_data.get('leverage', '')}x"""

    @staticmethod
    def stop_loss_hit(signal_data: Dict[str, Any]) -> str:
        """🚩 STOP LOSS TRÄFFAD"""
        return f"""🚩 STOP LOSS TRÄFFAD
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Sida: {signal_data.get('direction', '')}

📍 SL: {signal_data.get('sl', '')}
💵 Stängd kvantitet: {signal_data.get('quantity', '')} (100%)
📊 Resultat: {signal_data.get('result_pct', '0')}% | {signal_data.get('result_usdt', '0')} USDT

🔁 Återinträdeslogik: aktiverad – ny signal tas vid bekräftad trendvändning"""

    @staticmethod
    def position_closed(signal_data: Dict[str, Any]) -> str:
        """✅ POSITION STÄNGD"""
        result_pct = signal_data.get('result_pct', '0')
        result_usdt = signal_data.get('result_usdt', '0')
        
        # Ensure the result shows the correct USDT amount (not inflated)
        # For 20 USDT trade with 1.59% gain, should show ~3.2 USDT, not 32 USDT
        return f"""✅ POSITION STÄNGD
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}
📈 Sida: {signal_data.get('direction', '')}

💵 Stängd kvantitet: {signal_data.get('quantity', '')} (100%)
📍 Exit: {signal_data.get('price', '')}

📊 Resultat: {result_pct}% inkl. hävstång 
📊 Resultat: {result_usdt} USDT inkl. hävstång
📊 PoL: {signal_data.get('pol_usdt', '0')} USDT"""

    # Error templates
    @staticmethod
    def signal_invalid(signal_data: Dict[str, Any]) -> str:
        """❌ SIGNAL OGILTIG ❌"""
        return f"""❌ SIGNAL OGILTIG ❌
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}

📍 Fel: Ofullständig eller felaktig signal mottagen"""

    @staticmethod
    def order_failed(signal_data: Dict[str, Any]) -> str:
        """❌ ORDER MISSLYCKADES ❌"""
        return f"""❌ ORDER MISSLYCKADES ❌
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}

📍 Fel: Order kunde inte placeras (kontrollera saldo eller parametrar)"""

    @staticmethod
    def order_rejected(signal_data: Dict[str, Any]) -> str:
        """❌ ORDER AVVISAD ❌"""
        return f"""❌ ORDER AVVISAD ❌
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}

📍 Fel: Ordern avvisades av Bybit (felaktiga parametrar eller otillåten hävstång)"""

    @staticmethod
    def position_not_opened(signal_data: Dict[str, Any]) -> str:
        """❌ POSITION EJ ÖPPNAD ❌"""
        return f"""❌ POSITION EJ ÖPPNAD ❌
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}

📍 Fel: Positionen kunde inte öppnas (otillräcklig IM eller fel hävstång)"""

    @staticmethod
    def position_not_closed(signal_data: Dict[str, Any]) -> str:
        """❌ POSITION EJ STÄNGD ❌"""
        return f"""❌ POSITION EJ STÄNGD ❌
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}

📍 Fel: Positionen kunde inte stängas (API-problem eller Reduce-Only aktiv)"""

    @staticmethod
    def insufficient_im(signal_data: Dict[str, Any]) -> str:
        """❌ OTILLRÄCKLIG IM ❌"""
        return f"""❌ OTILLRÄCKLIG IM ❌
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}

📍 Fel: Ej tillräckligt med margin för att öppna positionen"""

    @staticmethod
    def insufficient_balance(signal_data: Dict[str, Any]) -> str:
        """❌ OTILLRÄCKLIG BALANS ❌"""
        return f"""❌ OTILLRÄCKLIG BALANS ❌
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}

📍 Fel: Kontosaldo räcker inte för denna order"""

    @staticmethod
    def no_money_left(signal_data: Dict[str, Any]) -> str:
        """❌ SLUT PÅ PENGAR ❌"""
        return f"""❌ SLUT PÅ PENGAR ❌
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}

📍 Fel: Inga medel kvar på kontot för att öppna eller fylla på position"""

    @staticmethod
    def tp_not_executed(signal_data: Dict[str, Any]) -> str:
        """❌ TP EJ UTFÖRD ❌"""
        return f"""❌ TP EJ UTFÖRD ❌
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}

📍 Fel: Take Profit kunde inte aktiveras (order ej placerad eller missad trigger)"""

    @staticmethod
    def sl_not_executed(signal_data: Dict[str, Any]) -> str:
        """❌ SL EJ UTFÖRD ❌"""
        return f"""❌ SL EJ UTFÖRD ❌
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}

📍 Fel: Stop Loss kunde inte placeras (kontrollera orderstatus)"""

    @staticmethod
    def api_error(signal_data: Dict[str, Any]) -> str:
        """❌ API FEL ❌"""
        return f"""❌ API FEL ❌
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}

📍 Fel: Ingen kontakt med Bybit (kontrollera API-nyckel eller nätverk)"""

    @staticmethod
    def system_error(signal_data: Dict[str, Any]) -> str:
        """❌ SYSTEM FEL ❌"""
        return f"""❌ SYSTEM FEL ❌
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}

📍 Fel: Okänt fel i boten (kräver manuell kontroll)"""

    @staticmethod
    def order_deleted(signal_data: Dict[str, Any]) -> str:
        """✔️ ORDER RADERAD ✔️"""
        return f"""✔️ ORDER RADERAD ✔️
📢 Från kanal: {signal_data.get('channel_name', '')}
📊 Symbol: {signal_data.get('symbol', '')}

📍 Fel: Order ej öppnad inom tillåten tid (raderad enligt reglerna)"""

    # Report templates
    @staticmethod
    def daily_report(report_data: Dict[str, Any]) -> str:
        """📑 DAGLIG RAPPORT FRÅN GRUPP"""
        trades = report_data.get('trades', [])
        trade_lines = ""
        for trade in trades[:10]:  # Top 10
            trade_lines += f"{trade.get('symbol', '')}   {trade.get('pct', '0')}     {trade.get('usdt', '0')}\n"
        
        return f"""📑 DAGLIG RAPPORT FRÅN GRUPP: {report_data.get('group_name', '')}

📊 RESULTAT
Symbol        %            USDT
{trade_lines}------------------------------------

📈 Antal signaler: {report_data.get('total_signals', 0)}
💹 Totalt resultat: {report_data.get('total_usdt', '0')} USDT
📊 Vinst/Förlust: {report_data.get('total_pct', '0')}%"""

    @staticmethod
    def weekly_report(report_data: Dict[str, Any]) -> str:
        """📑 VECKORAPPORT FRÅN GRUPP"""
        trades = report_data.get('trades', [])
        trade_lines = ""
        for trade in trades[:20]:  # Top 20
            trade_lines += f"{trade.get('symbol', '')}   {trade.get('pct', '0')}     {trade.get('usdt', '0')}\n"
        
        return f"""📑 VECKORAPPORT FRÅN GRUPP: {report_data.get('group_name', '')}

📊 RESULTAT
Symbol        %            USDT
{trade_lines}...           ...          ...

------------------------------------

📈 Antal signaler: {report_data.get('total_signals', 0)}
💹 Totalt resultat: {report_data.get('total_usdt', '0')} USDT
📊 Vinst/Förlust: {report_data.get('total_pct', '0')}%"""

    @staticmethod
    def daily_error_report(report_data: Dict[str, Any]) -> str:
        """📑 DAGSRAPPORT – FELMEDDELANDEN"""
        return f"""📑 DAGSRAPPORT – FELMEDDELANDEN: {report_data.get('group_name', '')}

📊 FELMEDDELANDEN
Typ                           Antal
Order misslyckades            {report_data.get('order_fail', 0)}
Order avvisad                 {report_data.get('order_reject', 0)}
Position ej öppnad            {report_data.get('pos_fail', 0)}
Position ej stängd            {report_data.get('pos_close_fail', 0)}
Otillräcklig IM               {report_data.get('im_fail', 0)}
Otillräcklig balans           {report_data.get('balance_fail', 0)}
API-fel                       {report_data.get('api_fail', 0)}
Systemfel                     {report_data.get('system_fail', 0)}
Signal ogiltig                {report_data.get('signal_fail', 0)}
SL/TP ej utförd               {report_data.get('sl_tp_fail', 0)}
Slut på pengar                {report_data.get('no_money', 0)}
Order raderad (V)             {report_data.get('v_order_del', 0)}

------------------------------------

📈 Totalt antal fel: {report_data.get('total_errors', 0)}
📊 Felfrekvens: {report_data.get('error_pct', '0')}% av dagens signaler"""

    @staticmethod
    def weekly_error_report(report_data: Dict[str, Any]) -> str:
        """📑 VECKORAPPORT – FELMEDDELANDEN"""
        return f"""📑 VECKORAPPORT – FELMEDDELANDEN: {report_data.get('group_name', '')}

📊 FELMEDDELANDEN
Typ                           Antal
Order misslyckades            {report_data.get('order_fail', 0)}
Order avvisad                 {report_data.get('order_reject', 0)}
Position ej öppnad            {report_data.get('pos_fail', 0)}
Position ej stängd            {report_data.get('pos_close_fail', 0)}
Otillräcklig IM               {report_data.get('im_fail', 0)}
Otillräcklig balans           {report_data.get('balance_fail', 0)}
API-fel                       {report_data.get('api_fail', 0)}
Systemfel                     {report_data.get('system_fail', 0)}
Signal ogiltig                {report_data.get('signal_fail', 0)}
SL/TP ej utförd               {report_data.get('sl_tp_fail', 0)}
Slut på pengar                {report_data.get('no_money', 0)}
Order raderad (V)             {report_data.get('v_order_del', 0)}

------------------------------------

📈 Totalt antal fel: {report_data.get('total_errors', 0)}
📊 Felfrekvens: {report_data.get('error_pct', '0')}% av totala signaler"""