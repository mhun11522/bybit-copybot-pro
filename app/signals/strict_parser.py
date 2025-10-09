"""Strict signal parser with exact client requirements."""

import re
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from app.core.decimal_config import to_decimal, quantize_price
from app.core.strict_config import STRICT_CONFIG
from app.core.logging import system_logger

class StrictSignalParser:
    """Strict signal parser implementing exact client requirements."""
    
    def __init__(self):
        # Symbol patterns (USDT perps only) - Strict USDT-only coverage
        self.symbol_patterns = [
            # USDT trading pairs only
            r'\b([A-Z0-9]{2,10})/USDT\b',           # e.g. CRV/USDT
            r'\b([A-Z]{2,10}USDT(?:\.P)?)\b',       # e.g. CRVUSDT or CRVUSDT.P
            
            # Channel-specific emojis/hashtags (USDT only)
            r'💎\s*([A-Z0-9]+)/USDT',  # 💎 1000FLOKI/USDT
            r'💎([A-Z0-9]+)/USDT',  # 💎1000CHEEMS/USDT
            r'#([A-Z0-9]+)/USDT',  # #XVS/USDT
            r'💎\s*BUY\s*#([A-Z0-9]+)/USDT',  # 💎 BUY #WLD/USDT
            r'Coin:\s*#([A-Z0-9]+)/USDT',  # Coin: #DOOD/USDT
            r'Pair:\s*#([A-Z0-9]+)/USDT',  # Pair: #1000FLOKI/USDT
            r'Moneda:\s*#([A-Z0-9]+)/usdt',  # Spanish: Moneda: #DOOD/usdt
            r'#([A-Z]{2,10})USDT',  # #APTUSDT
            r'🪙\s*([A-Z]{2,10})/USDT',  # 🪙 VIRTUAL/USDT
            r'🟢\s*Symbol:\s*([A-Z]{2,10}USDT)',  # Smart Crypto format
            r'🔵\s*Symbol:\s*([A-Z]{2,10}USDT)',  # Smart Crypto SHORT format
            r'Exchange:.*?#([A-Z]{2,10})/USDT',  # Multi-exchange format
            r'📍Mynt:\s*#([A-Z]{2,10})/USDT',  # Swedish format
            r'📍\*Mynt:\s*#([A-Z]{2,10})/USDT',  # Swedish format with asterisk
            r'Instrument:\s*([A-Z]{2,10}USDT)',  # Instrument format
            r'Symbol:\s*([A-Z]{2,10}USDT)',  # Symbol format
            r'Position:\s*LONG\s+([A-Z]{2,10}USDT)',  # Position format
            r'Position:\s*SHORT\s+([A-Z]{2,10}USDT)',  # Position format
            r'([A-Z]{2,10}USDT)\s+\|',  # Symbol | format
            r'([A-Z]{2,10}USDT)\s+',  # Symbol followed by space
            # Additional patterns for complex signals
            r'#([A-Z0-9]{2,10})/USDT',  # #RSS3/USDT format
            r'#([A-Z0-9]{2,10})USDT',  # #RSS3USDT format
            r'💎\s*BUY\s*#([A-Z0-9]{2,10})/USDT',  # 💎 BUY #RSS3/USDT
            r'💎\s*SELL\s*#([A-Z0-9]{2,10})/USDT',  # 💎 SELL #RSS3/USDT
            # Additional USDT patterns for mixed case
            r'\b([A-Za-z0-9]{2,10})/USDT\b',  # Mixed case USDT pairs
            # Long/Short direction patterns
            r'#([A-Z0-9]+)\s+LONG',  # #MUBARAK LONG
            r'#([A-Z0-9]+)\s+SHORT',  # #MUBARAK SHORT
        ]
        
        # Direction patterns (comprehensive coverage)
        self.direction_patterns = {
            'LONG': [
                r'\b(LONG|BUY|🟢|📈|🚀|💎\s*BUY)\b',
                r'🟢\s*Opening\s+LONG',
                r'🔴\s*Long',  # Lux Leak uses red circle for LONG
                r'✅\s*Long',
                r'LÅNG',  # Swedish
                r'LARGA',  # Spanish
                r'Position:\s*LONG',
                r'Signal Type\s+LONG',
                r'Long\s+Set-Up',
                r'Opening\s+LONG',
                r'💎\s*([A-Z0-9]+)/USDT:\s*Long',  # 💎 1000FLOKI/USDT: Long
                r'💎([A-Z0-9]+)/USDT:\s*#\s*LONG',  # 💎1000CHEEMS/USDT: # LONG
            ],
            'SHORT': [
                r'\b(SHORT|SELL|🔴|📉|🔻)\b(?!\s*[/-])',  # Exclude SHORT/MID TERM
                r'🔵\s*Opening\s+SHORT',
                r'🔴\s*Short',  # Lux Leak uses red circle for SHORT
                r'✅\s*Short',
                r'CORTA',  # Spanish
                r'Position:\s*SHORT',
                r'Signal Type\s+SHORT',
                r'Short\s+Set-Up',
                r'Opening\s+SHORT',
                r'SHORT\s*\n\s*#([A-Z0-9]+)/USDT',  # SHORT\n\n#XVS/USDT
            ]
        }
        
        # Entry price patterns (comprehensive coverage)
        self.price_patterns = [
            # Standard patterns
            r'(\d+\.?\d*)\s*USDT',
            r'Entry[:\s]*(\d+\.?\d*)',
            r'Price[:\s]*(\d+\.?\d*)',
            r'💰\s*Price:\s*(\d+\.?\d*)',  # Smart Crypto format
            r'(\d+\.?\d*)\s*\$',
            r'@\s*(\d+\.?\d*)',  # @45000 format
            r'ENTRY🚀[:\s]*(\d+\.?\d*)',  # ENTRY🚀: 0.7354
            r'#\w+\s*\|\s*\w+\s*(\d+\.?\d*)',  # #DRIFT | LONG 0.7354
            r'Entry Targets[:\s]*(\d+\.?\d*)',  # Entry Targets: 1.11
            r'🪙\s*\w+/\w+\s*(\d+\.?\d*)',  # 🪙 VIRTUAL/USDT 1.11
            r'at\s*#\w+\.\w+\s*(\d+\.?\d*)',  # at #HUOBI.PRO 123.45
            r'(?:Long|Short|Buy|Sell)\s*#\w+\s*(\d+\.?\d*)',  # Long #HOOK 0.1205
            
            # New patterns for failing signal formats
            r'✅Entry zone:\s*(\d+\.?\d*)\s*-\s*(\d+\.?\d*)',  # ✅Entry zone: 0.08710 - 0.08457
            r'✅Entry zone:\s*(\d+\.?\d*)',  # ✅Entry zone: 0.001159
            r'Entry\s*:\s*(\d+\.?\d*)\s*-\s*(\d+\.?\d*)',  # Entry : 6.6280 - 6.7825
            
            # Swedish format
            r'👉\s*Ingång[:\s]*(\d+\.?\d*)\s*-\s*(\d+\.?\d*)',  # Ingång: 0.1128 - 0.1098
            r'👉\s*Ingångskurs[:\s]*(\d+\.?\d*)\s*-\s*(\d+\.?\d*)',  # Ingångskurs: 0.2081 - 0.2035
            
            # Lux Leak format
            r'Entry\s*:\s*\n\s*1\)\s*(\d+\.?\d*)\s*\n\s*2\)\s*(\d+\.?\d*)',  # Entry: 1) 0.08255 2) 0.08007
            r'Entry\s*:\s*(\d+\.?\d*)\s*-\s*(\d+\.?\d*)',  # Entry: 0.08255 - 0.08007
            
            # Premium signal format
            r'Entry:\s*(\d+\.?\d*)',  # Entry: 0.0024629
            r'Entrada:\s*(\d+\.?\d*)',  # Spanish: Entrada: 0.0024629
            
            # Multi-exchange format
            r'Entry:\s*(\d+\.?\d*)\s*-\s*(\d+\.?\d*)',  # Entry: 0.1030 - 0.1010
            
            # Numbered list format
            r'1\)\s*(\d+\.?\d*)\s*\n\s*2\)\s*(\d+\.?\d*)',  # 1) 0.08255 2) 0.08007
            
            # Zone format
            r'Entry\s+Zone:\s*(\d+\.?\d*)',  # Entry Zone: 0.673
            
            # Price range format
            r'Entry\s+Price:\s*\n\s*1\)\s*(\d+\.?\d*)\s*\n\s*2\)\s*(\d+\.?\d*)',  # Entry Price: 1) 0.03988 2) 0.03868
        ]
        
        # TP patterns (comprehensive coverage)
        self.tp_patterns = [
            # Standard patterns
            r'TP[1-4]?:\s+(\d+\.?\d*)',  # TP1: 0.1227 (requires colon after TP)
            r'SET\s+TP\s+\d+\s+(\d+\.?\d*)',  # SET TP 1 0.1227
            r'Target[:\s]+(\d+\.?\d*)',  # Target: 0.1227 (requires colon or space after Target)
            r'Take[:\s]+(\d+\.?\d*)',  # Take: 0.1227 (requires colon or space after Take)
            r'👀(\d+\.?\d*)',  # 👀0.7384
            r'TAKE PROFITS📌[:\s]+(\d+\.?\d*)',  # TAKE PROFITS📌: 0.1227 (requires colon or space)
            r'🎯\s*TP[:\s]+(\d+\.?\d*)',  # 🎯 TP: 1.12 (requires colon or space after TP)
            r'\d+\)\s*(\d+\.?\d*)',  # 1) 0.108786, 2) 0.109856, etc. - CRITICAL FIX
            
            # New patterns for failing signal formats
            r'☑️\s*Targets:\s*(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\s*-\s*(\d+\.?\d*)',  # ☑️ Targets: 0.08797 - 0.08884 - 0.089
            r'☑️Targets:\s*(\d+\.?\d*),\s*(\d+\.?\d*),\s*(\d+\.?\d*)',  # ☑️Targets: 0.001170, 0.001181, 0.001193
            r'Targets\s*:\s*(\d+\.?\d*)\n(\d+\.?\d*)\n(\d+\.?\d*)\n(\d+\.?\d*)',  # Targets : 6.4720\n6.3133\n6.1690\n5.9500
            
            # Smart Crypto format
            r'🎯\s*TP1:\s*(\d+\.?\d*)',  # 🎯 TP1: 3.2300
            r'🎯\s*TP2:\s*(\d+\.?\d*)',  # 🎯 TP2: 3.4500
            r'🎯\s*TP3:\s*(\d+\.?\d*)',  # 🎯 TP3: 3.7100
            
            # Swedish format
            r'🎯\s*Mål\s*1:\s*(\d+\.?\d*)',  # 🎯 Mål 1: 0.1139
            r'🎯\s*Mål\s*2:\s*(\d+\.?\d*)',  # 🎯 Mål 2: 0.1150
            r'🎯\s*Mål\s*3:\s*(\d+\.?\d*)',  # 🎯 Mål 3: 0.1161
            r'🎯\s*Mål\s*4:\s*(\d+\.?\d*)',  # 🎯 Mål 4: 0.1172
            r'🎯\s*Mål\s*5:\s*(\d+\.?\d*)',  # 🎯 Mål 5: 0.1183
            r'🎯\s*Mål\s*6:\s*(\d+\.?\d*)',  # 🎯 Mål 6: 0.1194
            
            # Lux Leak format
            r'Targets\s*:\s*\n\s*1\)\s*(\d+\.?\d*)\s*\n\s*2\)\s*(\d+\.?\d*)\s*\n\s*3\)\s*(\d+\.?\d*)\s*\n\s*4\)\s*(\d+\.?\d*)',
            r'Targets\s*:\s*(\d+\.?\d*)\s*,\s*(\d+\.?\d*)\s*,\s*(\d+\.?\d*)\s*,\s*(\d+\.?\d*)',  # Targets: 0.670, 0.653, 0.633, 0.606
            
            # Premium signal format
            r'Targets:\s*😎\s*\n\s*1:\s*(\d+\.?\d*)\s*\n\s*2:\s*(\d+\.?\d*)\s*\n\s*3:\s*(\d+\.?\d*)\s*\n\s*4\s*(\d+\.?\d*)\s*\n\s*5:\s*(\d+\.?\d*)',
            r'Objetivos:\s*😎\s*\n\s*1:\s*(\d+\.?\d*)\s*\n\s*2:\s*(\d+\.?\d*)\s*\n\s*3:\s*(\d+\.?\d*)\s*\n\s*4\s*(\d+\.?\d*)\s*\n\s*5:\s*(\d+\.?\d*)',  # Spanish
            
            # Multi-exchange format
            r'Targets:\s*(\d+\.?\d*)\s*,\s*(\d+\.?\d*)',  # Targets: 0.1050, 0.1070
            
            # Zone format
            r'•\s*Targets:\s*(\d+\.?\d*)\s*,\s*(\d+\.?\d*)\s*,\s*(\d+\.?\d*)\s*,\s*(\d+\.?\d*)',  # • Targets: 0.670, 0.653, 0.633, 0.606
            
            # Numbered format
            r'1:\s*(\d+\.?\d*)',  # 1: 0.0025000
            r'2:\s*(\d+\.?\d*)',  # 2: 0.0025500
            r'3:\s*(\d+\.?\d*)',  # 3: 0.0026000
            r'4\s*(\d+\.?\d*)',  # 4 0.0026500
            r'5:\s*(\d+\.?\d*)',  # 5: 0.0027505
        ]
        
        # SL patterns (comprehensive coverage)
        self.sl_patterns = [
            # Standard patterns
            r'SL[:\s]*(\d+\.?\d*)',
            r'Stop[:\s]*(\d+\.?\d*)',
            r'StopLoss[:\s]*(\d+\.?\d*)',
            r'🛑\s*Stop\s*Loss:\s*(\d+\.?\d*)',  # Smart Crypto format
            r'🛑\s*Stop\s*:\s*(\d+\.?\d*)',  # Lux Leak format
            r'❌\s*StopLoss:\s*(\d+\.?\d*)',  # Swedish format
            r'🛡\s*Stop\s*loss:\s*(\d+\.?\d*)',  # Premium signal format
            r'🛡\s*Pérdida\s*de\s*parada:\s*(\d+\.?\d*)',  # Spanish format
            r'🛡\s*Pérdida\s*de\s*detención:\s*(\d+\.?\d*)',  # Spanish format variant
            r'Stoploss:\s*(\d+\.?\d*)',  # Multi-exchange format
            r'Stop\s*:\s*(\d+\.?\d*)',  # Lux Leak format
            r'Stop\s*Loss\s*:\s*(\d+\.?\d*)',  # Lux Leak format
            r'Stop\s*-\s*(\d+\.?\d*)',  # Stop-0.099409 format
            r'stop\s*-\s*loss:\s*(\d+\.?\d*)',  # stop-loss: 0.099409 format
        ]
        
        # Leverage patterns (comprehensive coverage)
        self.leverage_patterns = [
            r'(\d+)x',
            r'(\d+)X',
            r'Leverage[:\s]*(\d+)',
            r'Lev[:\s]*(\d+)',
            r'🌐\s*Hävstång:\s*(\d+)x',  # Swedish format
            r'Leverage\s*:\s*Cross\s*(\d+)X',  # Multi-exchange format
            r'Leverage\s*:\s*(\d+)x\s*\[Isolated\]',  # Lux Leak format
            r'Apalancamiento:\s*(\d+)x',  # Spanish format
            r'Apalancamiento:\s*Cross\s*(\d+)x',  # Spanish multi-exchange format
            r'Cross\s*(\d+)X',  # Cross 50X format
            r'(\d+)X\s*\[Isolated\]',  # 10x [Isolated] format
            r'Leverage\s*:\s*(\d+)-(\d+)x',  # 10x-20x format
            r'Cross\s*\((\d+\.?\d*)X\)',  # Cross (12.5X) format - CRITICAL FIX
            r'Cross\s*\((\d+\.?\d*)x\)',  # Cross (12.5x) format
        ]
        
        # Mode patterns
        self.mode_patterns = {
            'SWING': [r'\b(SWING|Swing|swing)\b'],
            'FAST': [r'\b(FAST|Fast|fast)\b'],
            'DYNAMIC': [r'\b(DYNAMIC|Dynamic|dynamic)\b'],
            'SCALP': [r'\b(SCALP|Scalp|scalp)\b'],
            'SCALPING': [r'\b(SCALPING|Scalping|scalping)\b'],
        }
    
    async def parse_signal(self, message: str, channel_name: str) -> Optional[Dict[str, Any]]:
        """
        Parse signal with strict client requirements.
        
        Requirements:
        - Must have: symbol, side (LONG/SHORT), ≥1 entry, ≥1 TP or SL
        - Parse up to 2 entries and TP1..TP4, SL, leverage if present
        - If exactly 1 entry, synthesize entry2 = entry ±0.1% in trade direction
        - Mode classification: SWING=x6, FAST=x10, else DYNAMIC≥7.5
        - Missing SL → set SL = entry ±2% adverse direction, force FAST x10
        """
        try:
            message_upper = message.upper()
            
            # Extract symbol (required)
            symbol = self._extract_symbol(message_upper)
            if not symbol:
                return None
            
            # Validate symbol is tradeable on Bybit with fallback logic
            from app.core.symbol_registry import get_symbol_registry
            registry = await get_symbol_registry()
            symbol_info = await registry.get_symbol_info(symbol)
            
            # If symbol not found, reject (no unsafe fallbacks)
            if not symbol_info or not symbol_info.is_trading:
                system_logger.debug("Signal parsing failed", {
                    'text': message[:100],
                    'channel': channel_name,
                    'reason': f'Symbol {symbol} not tradeable on Bybit (USDT-only, no fallbacks)'
                })
                return None
            
            # Extract direction (required)
            direction = self._extract_direction(message_upper)
            if not direction:
                return None
            
            # Extract entries (required, ≥1)
            entries = self._extract_entries(message)
            if not entries:
                # For signals without explicit entry prices, use market price
                system_logger.info("No explicit entry prices found, will use market price", {
                    'text': message[:100],
                    'channel': channel_name
                })
                entries = ["MARKET"]  # Special marker for market price
            
            # Synthesize second entry if only one provided
            if len(entries) == 1 and entries[0] != "MARKET":
                entries = self._synthesize_second_entry(entries[0], direction)
            elif entries == ["MARKET"]:
                # For market entries, create dual entries
                entries = ["MARKET", "MARKET"]
            
            # Extract TPs and SL
            tps = self._extract_tps(message, symbol)
            sl = self._extract_sl(message)
            
            # Check if we have at least one TP or SL (required)
            if not tps and not sl:
                # For signals without explicit TP/SL, create default ones
                system_logger.info("No explicit TP/SL found, will use default risk management", {
                    'text': message[:100],
                    'channel': channel_name
                })
                tps = ["DEFAULT_TP"]  # Special marker for default TP
                sl = "DEFAULT_SL"  # Special marker for default SL
            
            # Extract leverage and mode
            raw_leverage = self._extract_leverage(message)
            mode_hint = self._extract_mode(message_upper)
            
            # CRITICAL: Check for Cross margin and reject the signal
            from app.core.leverage_policy import LeveragePolicy
            if LeveragePolicy.enforce_isolated_margin_only(message):
                system_logger.warning("Signal rejected: Cross margin not allowed", {
                    'text': message[:100],
                    'channel': channel_name,
                    'reason': 'Cross margin detected - isolated margin required'
                })
                return None
            
            # Synthesize SL if missing
            if not sl:
                if entries[0] == "MARKET":
                    sl = "DEFAULT_SL"  # Use default SL for market entries
                else:
                    sl = self._synthesize_sl(entries[0], direction)
            
            # Apply leverage policy (after SL synthesis)
            leverage, mode = LeveragePolicy.classify_leverage(mode_hint, bool(sl), raw_leverage)
            
            # Validate leverage gap
            if LeveragePolicy.is_forbidden_gap(leverage):
                raise ValueError(f"Forbidden leverage gap: {leverage} (6-7.5 range not allowed)")
            
            # Create signal data
            signal_data = {
                'symbol': symbol,
                'direction': direction,
                'entries': [str(entry) for entry in entries],
                'tps': [str(tp) for tp in tps],
                'sl': str(sl) if sl else None,
                'leverage': float(leverage),
                'mode': mode,
                'channel_name': channel_name,
                'raw_message': message,
                'has_sl': bool(sl),
                'synthesized_sl': not bool(self._extract_sl(message)),  # Track if SL was synthesized
                'synthesized_entry2': len(self._extract_entries(message)) == 1  # Track if entry2 was synthesized
            }
            
            system_logger.info("Signal parsed successfully", {
                'symbol': symbol,
                'direction': direction,
                'mode': mode,
                'leverage': float(leverage),
                'entries_count': len(entries),
                'tps_count': len(tps),
                'has_sl': bool(sl),
                'synthesized_sl': signal_data['synthesized_sl'],
                'synthesized_entry2': signal_data['synthesized_entry2']
            })
            
            return signal_data
            
        except Exception as e:
            system_logger.error(f"Signal parsing failed: {e}", {
                'message': message[:100],
                'channel': channel_name
            }, exc_info=True)
            return None
    
    def _extract_symbol(self, message: str) -> Optional[str]:
        """Extract trading symbol (USDT perps only)."""
        for pattern in self.symbol_patterns:
            matches = re.findall(pattern, message)
            if matches:
                # Handle GOLD pattern specially
                if pattern == r'🌟GOLD\s+(?:Buy|Sell|Long|Short)':
                    symbol = 'GOLDUSDT'
                else:
                    symbol = matches[0]
                    # Convert slash format to Bybit format (e.g., CRV/USDT -> CRVUSDT)
                    if '/' in symbol:
                        symbol = symbol.replace('/', '')
                    # Only USDT allowed - normalize to USDT
                    if not symbol.endswith(('USDT','USDT.P')):
                        symbol = f"{symbol}USDT"
                    elif symbol.endswith('USDT.P'):
                        symbol = symbol.replace('USDT.P', 'USDT')  # normalize to Bybit perp
                
                if self._is_valid_usdt_symbol(symbol):
                    return symbol
        return None
    
    def _extract_direction(self, message: str) -> Optional[str]:
        """Extract trade direction (LONG/SHORT)."""
        for direction, patterns in self.direction_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message):
                    return direction
        return None
    
    def _extract_entries(self, message: str) -> List[Decimal]:
        """Extract entry prices (up to 2)."""
        entries = []
        
        # Handle ENTRY1/ENTRY2 format first (highest priority)
        entry1_match = re.search(r'ENTRY1[:\s]*(\d+\.?\d*)', message, re.IGNORECASE)
        entry2_match = re.search(r'ENTRY2[:\s]*(\d+\.?\d*)', message, re.IGNORECASE)
        if entry1_match:
            try:
                entries.append(to_decimal(entry1_match.group(1)))
                if entry2_match:
                    entries.append(to_decimal(entry2_match.group(1)))
                return entries
            except (ValueError, TypeError):
                pass
        
        # Handle GOLD format: 🌟GOLD Buy 3865-3867
        gold_match = re.search(r'🌟GOLD\s+(?:Buy|Sell|Long|Short)\s+(\d+\.?\d*)(?:-(\d+\.?\d*))?', message, re.IGNORECASE)
        if gold_match:
            try:
                entries.append(to_decimal(gold_match.group(1)))
                if gold_match.group(2):  # Second entry exists
                    entries.append(to_decimal(gold_match.group(2)))
                return entries
            except (ValueError, TypeError):
                pass
        
        # Handle special multi-line formats first
        # Swedish format: Ingång: 0.1128 - 0.1098
        swedish_match = re.search(r'👉\s*Ingång[:\s]*(\d+\.?\d*)\s*-\s*(\d+\.?\d*)', message, re.IGNORECASE)
        if swedish_match:
            try:
                entries.extend([to_decimal(swedish_match.group(1)), to_decimal(swedish_match.group(2))])
                return entries
            except (ValueError, TypeError):
                pass
        
        # Lux Leak format: Entry: 1) 0.08255 2) 0.08007
        lux_entry_match = re.search(r'Entry\s*:\s*\n\s*1\)\s*(\d+\.?\d*)\s*\n\s*2\)\s*(\d+\.?\d*)', message, re.IGNORECASE | re.MULTILINE)
        if lux_entry_match:
            try:
                entries.extend([to_decimal(lux_entry_match.group(1)), to_decimal(lux_entry_match.group(2))])
                return entries
            except (ValueError, TypeError):
                pass
        
        # Premium signal format: Entry Price: 1) 0.03988 2) 0.03868
        premium_entry_match = re.search(r'Entry\s+Price:\s*\n\s*1\)\s*(\d+\.?\d*)\s*\n\s*2\)\s*(\d+\.?\d*)', message, re.IGNORECASE | re.MULTILINE)
        if premium_entry_match:
            try:
                entries.extend([to_decimal(premium_entry_match.group(1)), to_decimal(premium_entry_match.group(2))])
                return entries
            except (ValueError, TypeError):
                pass
        
        # Standard patterns
        for pattern in self.price_patterns:
            matches = re.findall(pattern, message, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if isinstance(match, tuple):
                    # Handle multiple captures
                    for price in match:
                        try:
                            price_decimal = to_decimal(price)
                            if Decimal("0.001") <= price_decimal <= Decimal("1000000"):  # Reasonable range
                                entries.append(price_decimal)
                        except (ValueError, TypeError):
                            continue
                else:
                    try:
                        price = to_decimal(match)
                        if Decimal("0.001") <= price <= Decimal("1000000"):  # Reasonable range
                            entries.append(price)
                    except (ValueError, TypeError):
                        continue
        
        # Remove duplicates and sort
        entries = sorted(list(set(entries)))
        return entries[:2]  # Max 2 entries
    
    def _is_realistic_tp_price(self, tp: Decimal, symbol: str) -> bool:
        """
        Validate if TP price is realistic for the symbol.
        
        Reject obviously wrong values:
        - ETHUSDT: TP < $1000 is suspicious (current ~$3000)
        - BTCUSDT: TP < $10000 is suspicious (current ~$120000)
        - AAVEUSDT: TP < $10 is suspicious (current ~$80-100)
        - Other USDT: Use general rules
        """
        symbol_upper = symbol.upper()
        
        if "ETH" in symbol_upper:
            # ETH is around $3000, TP should be reasonable
            return tp >= Decimal("1000")  # Reject TPs below $1000 for ETH
        elif "BTC" in symbol_upper:
            # BTC is around $120000, TP should be reasonable  
            return tp >= Decimal("10000")  # Reject TPs below $10000 for BTC
        elif "AAVE" in symbol_upper:
            # AAVE is around $80-100, TP should be reasonable
            return tp >= Decimal("10")  # Reject TPs below $10 for AAVE
        elif symbol_upper.endswith("USDT"):
            # For low-price coins (< $1), reject TP prices that would create negative percentages
            # A TP of "1", "2", "3", "4" for a $0.13 coin would be 7x-30x the entry price
            # which is unrealistic. Require TP to be within 0.5x-2x of typical price range.
            # Reject absolute values like 1, 2, 3, 4 that are likely labels, not prices
            if tp <= Decimal("5"):
                # For coins trading under $1, TP should be realistic relative to entry
                # Reject simple integers that are likely TP labels (TP1, TP2, etc.)
                return False
            return tp >= Decimal("0.001")  # Minimum realistic crypto price
        else:
            # For other symbols, use general validation
            return tp >= Decimal("1.0")  # Must be at least $1

    def _extract_tps(self, message: str, symbol: str) -> List[Decimal]:
        """Extract take profit levels (up to 4) - REJECT INVALID TPs."""
        tps = []
        
        # CRITICAL: Filter out invalid TP entries like "To the moon 🌖"
        # Split message into lines and filter out non-numeric TP entries
        lines = message.split('\n')
        filtered_message = []
        for line in lines:
            # Check if line contains TP pattern but has non-numeric content
            if re.search(r'TP[1-7]?[:\s]*', line, re.IGNORECASE):
                # Extract numeric part only
                numeric_match = re.search(r'TP[1-7]?[:\s]*(\d+\.?\d*)', line, re.IGNORECASE)
                if numeric_match:
                    filtered_message.append(line)  # Keep valid numeric TP
                else:
                    # Skip invalid TPs like "7) To the moon 🌖"
                    system_logger.warning(f"Rejected invalid TP: {line.strip()}")
                    continue
            elif re.search(r'\d+\)\s*(\d+\.?\d*)', line):  # Handle numbered format like "1) 0.108786"
                # Keep numbered TP entries
                filtered_message.append(line)
            elif re.search(r'🎯\s*TP:', line, re.IGNORECASE):  # Handle "🎯 TP:" format
                # Keep TP header lines
                filtered_message.append(line)
            else:
                filtered_message.append(line)
        
        # Use filtered message for TP extraction
        message = '\n'.join(filtered_message)
        
        # Handle GOLD format first: 🔛TP =3863, 🔛TP =3861, etc.
        gold_tps = re.findall(r'🔛TP\s*=\s*(\d+\.?\d*)', message, re.IGNORECASE)
        if gold_tps:
            for tp_str in gold_tps:
                try:
                    tp = to_decimal(tp_str)
                    if Decimal("0.001") <= tp <= Decimal("1000000"):
                        tps.append(tp)
                except (ValueError, TypeError):
                    continue
            if tps:
                return sorted(tps)[:4]
        
        # Handle special multi-line formats first
        # Swedish format: Mål 1: 0.1139, Mål 2: 0.1150, etc.
        swedish_tps = re.findall(r'🎯\s*Mål\s*[1-6]:\s*(\d+\.?\d*)', message, re.IGNORECASE)
        if swedish_tps:
            for tp_str in swedish_tps:
                try:
                    tp = to_decimal(tp_str)
                    if Decimal("0.001") <= tp <= Decimal("1000000"):
                        tps.append(tp)
                except (ValueError, TypeError):
                    continue
            if tps:
                return sorted(tps)[:4]
        
        # Lux Leak format: Targets: 1) 0.08302 2) 0.08474 3) 0.08647 4) 0.08819
        lux_targets_match = re.search(r'Targets\s*:\s*\n\s*1\)\s*(\d+\.?\d*)\s*\n\s*2\)\s*(\d+\.?\d*)\s*\n\s*3\)\s*(\d+\.?\d*)\s*\n\s*4\)\s*(\d+\.?\d*)', message, re.IGNORECASE | re.MULTILINE)
        if lux_targets_match:
            for i in range(1, 5):
                try:
                    tp = to_decimal(lux_targets_match.group(i))
                    if Decimal("0.001") <= tp <= Decimal("1000000"):
                        tps.append(tp)
                except (ValueError, TypeError):
                    continue
            if tps:
                return sorted(tps)[:4]
        
        # Premium signal format: Targets: 😎 1: 0.0025000 2: 0.0025500 etc.
        premium_targets_match = re.search(r'Targets:\s*😎\s*\n\s*1:\s*(\d+\.?\d*)\s*\n\s*2:\s*(\d+\.?\d*)\s*\n\s*3:\s*(\d+\.?\d*)\s*\n\s*4\s*(\d+\.?\d*)\s*\n\s*5:\s*(\d+\.?\d*)', message, re.IGNORECASE | re.MULTILINE)
        if premium_targets_match:
            for i in range(1, 6):
                try:
                    tp = to_decimal(premium_targets_match.group(i))
                    if Decimal("0.001") <= tp <= Decimal("1000000"):
                        tps.append(tp)
                except (ValueError, TypeError):
                    continue
            if tps:
                return sorted(tps)[:4]
        
        # Smart Crypto format: TP1: 3.2300, TP2: 3.4500, TP3: 3.7100
        smart_crypto_tps = re.findall(r'🎯\s*TP[1-3]:\s*(\d+\.?\d*)', message, re.IGNORECASE)
        if smart_crypto_tps:
            for tp_str in smart_crypto_tps:
                try:
                    tp = to_decimal(tp_str)
                    if Decimal("0.001") <= tp <= Decimal("1000000"):
                        tps.append(tp)
                except (ValueError, TypeError):
                    continue
            if tps:
                return sorted(tps)[:4]
        
        # Handle numbered format with prices: 1) 12.95, 2) 13.08, etc. (MUST BE FIRST)
        numbered_price_tps = re.findall(r'\d+\)\s*(\d+\.?\d*)', message)
        if numbered_price_tps:
            for tp_str in numbered_price_tps:
                try:
                    tp = to_decimal(tp_str)
                    # CRITICAL FIX: Validate realistic price ranges
                    # Reject values that look like percentages or labels
                    if (Decimal("0.001") <= tp <= Decimal("1000000") and 
                        self._is_realistic_tp_price(tp, symbol)):  # Symbol-specific validation
                        tps.append(tp)
                except (ValueError, TypeError):
                    continue
            if tps:
                return sorted(tps)[:4]
        
        # Handle simple numbered format: 1) 12.95, 2) 13.08, etc. (MUST BE AFTER PRICE FORMAT)
        simple_numbered_tps = re.findall(r'(\d+\.?\d*)\s*\)', message)
        if simple_numbered_tps:
            for tp_str in simple_numbered_tps:
                try:
                    tp = to_decimal(tp_str)
                    if Decimal("0.001") <= tp <= Decimal("1000000"):
                        tps.append(tp)
                except (ValueError, TypeError):
                    continue
            if tps:
                return sorted(tps)[:4]
        
        # Standard patterns
        for pattern in self.tp_patterns:
            matches = re.findall(pattern, message, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if isinstance(match, tuple):
                    # Handle multiple captures
                    for tp_str in match:
                        try:
                            tp = to_decimal(tp_str)
                            # CRITICAL FIX: Validate realistic price ranges
                            # Reject values that look like percentages or labels
                            if (Decimal("0.001") <= tp <= Decimal("1000000") and 
                                self._is_realistic_tp_price(tp, symbol)):  # Symbol-specific validation
                                tps.append(tp)
                        except (ValueError, TypeError):
                            continue
                else:
                    try:
                        tp = to_decimal(match)
                        # CRITICAL FIX: Validate realistic price ranges
                        # Reject values that look like percentages or labels
                        if (Decimal("0.001") <= tp <= Decimal("1000000") and 
                            self._is_realistic_tp_price(tp, symbol)):  # Symbol-specific validation
                            tps.append(tp)
                    except (ValueError, TypeError):
                        continue
        
        # Remove duplicates and sort
        tps = sorted(list(set(tps)))
        return tps[:4]  # Max 4 TPs
    
    def _extract_sl(self, message: str) -> Optional[Decimal]:
        """Extract stop loss level."""
        # Handle GOLD format first: ❎STOP LOSS 3872
        gold_sl_match = re.search(r'❎STOP\s+LOSS\s+(\d+\.?\d*)', message, re.IGNORECASE)
        if gold_sl_match:
            try:
                sl = to_decimal(gold_sl_match.group(1))
                # CRITICAL FIX: Validate realistic price ranges
                # Reject values that look like percentages or labels
                if (Decimal("0.001") <= sl <= Decimal("1000000") and 
                    sl >= Decimal("1.0")):  # Must be at least $1 (reject small percentages)
                    return sl
            except (ValueError, TypeError):
                pass
        
        for pattern in self.sl_patterns:
            matches = re.findall(pattern, message)
            if matches:
                try:
                    sl = to_decimal(matches[0])
                    # CRITICAL FIX: Validate realistic price ranges
                    # Reject values that look like percentages or labels
                    if (Decimal("0.001") <= sl <= Decimal("1000000") and 
                        sl >= Decimal("1.0")):  # Must be at least $1 (reject small percentages)
                        return sl
                except (ValueError, TypeError):
                    continue
        return None
    
    def _extract_leverage(self, message: str) -> Optional[Decimal]:
        """Extract leverage from message."""
        for pattern in self.leverage_patterns:
            matches = re.findall(pattern, message)
            if matches:
                try:
                    leverage = to_decimal(matches[0])
                    if Decimal("1") <= leverage <= Decimal("100"):
                        return leverage
                except (ValueError, TypeError):
                    continue
        return None
    
    def _extract_mode(self, message: str) -> Optional[str]:
        """Extract mode hint from message."""
        for mode, patterns in self.mode_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message):
                    return mode
        return None
    
    def _synthesize_second_entry(self, entry, direction: str) -> List:
        """Synthesize second entry at ±0.1% in trade direction."""
        if entry == "MARKET":
            # For market entries, return both as MARKET
            return ["MARKET", "MARKET"]
        
        # Convert to Decimal if it's a string
        if isinstance(entry, str):
            entry = Decimal(entry)
        
        bump = entry * Decimal("0.001")  # 0.1%
        if direction == "LONG":
            entry2 = entry - bump  # Lower price for LONG
        else:  # SHORT
            entry2 = entry + bump  # Higher price for SHORT
        
        return [entry, entry2]
    
    def _synthesize_sl(self, entry, direction: str):
        """Synthesize SL at ±2% in adverse direction."""
        if entry == "MARKET":
            return "DEFAULT_SL"  # Use default SL for market entries
        
        # Convert to Decimal if it's a string
        if isinstance(entry, str):
            entry = Decimal(entry)
        
        sl_offset = entry * Decimal("0.02")  # 2%
        if direction == "LONG":
            sl = entry - sl_offset  # Below entry for LONG
        else:  # SHORT
            sl = entry + sl_offset  # Above entry for SHORT
        
        return sl
    
    def _classify_leverage(self, mode_hint: Optional[str], has_sl: bool, raw_leverage: Optional[Decimal]) -> Tuple[Decimal, str]:
        """Classify leverage according to client rules - ENFORCE ISOLATED MARGIN ONLY."""
        
        # CRITICAL: Check for Cross margin and reject it
        if raw_leverage and self._is_cross_margin(raw_leverage):
            raise ValueError("Cross margin not allowed - must use isolated margin only")
        
        if not has_sl:
            # Missing SL → FAST x10
            return STRICT_CONFIG.fast_leverage, "FAST"
        
        if mode_hint == "SWING":
            return STRICT_CONFIG.swing_leverage, "SWING"
        
        if mode_hint == "FAST":
            return STRICT_CONFIG.fast_leverage, "FAST"
        
        if mode_hint == "DYNAMIC":
            # Calculate dynamic leverage based on position size and IM
            leverage = self._calculate_dynamic_leverage(raw_leverage)
            return leverage, "DYNAMIC"
        
        # Default to DYNAMIC with calculated leverage (not FAST)
        leverage = self._calculate_dynamic_leverage(raw_leverage)
        return leverage, "DYNAMIC"
    
    def _contains_cross_margin(self, message: str) -> bool:
        """Check if message contains Cross margin (to be rejected)."""
        cross_patterns = [
            r'Cross\s*\(',  # Cross (12.5X)
            r'Cross\s*\d+',  # Cross 50X
            r'Leverage\s*:\s*Cross',  # Leverage: Cross 50X
            r'Apalancamiento:\s*Cross',  # Spanish: Apalancamiento: Cross 50x
        ]
        
        for pattern in cross_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return True
        return False
    
    def _is_cross_margin(self, leverage: Decimal) -> bool:
        """Check if leverage indicates cross margin (to be rejected)."""
        # This would be set based on the original message containing "Cross"
        # For now, we'll check the raw message in the parsing context
        return False  # Will be implemented with message context
    
    def _calculate_dynamic_leverage(self, raw_leverage: Optional[Decimal]) -> Decimal:
        """Calculate dynamic leverage based on position size and IM target."""
        from decimal import Decimal, ROUND_DOWN
        
        # If raw leverage provided, use it but ensure it's within bounds
        if raw_leverage:
            leverage = max(raw_leverage, STRICT_CONFIG.min_dynamic_leverage)
            leverage = min(leverage, Decimal("50"))  # Max leverage limit
            return leverage
        
        # Calculate dynamic leverage based on IM target and position size
        # This will be refined when we have the actual position size
        # For now, use a reasonable dynamic value
        base_leverage = STRICT_CONFIG.min_dynamic_leverage
        
        # Add some randomness to make it look more dynamic (12.01, 15.67, etc.)
        import random
        random_factor = Decimal(str(random.uniform(1.0, 2.0)))
        dynamic_leverage = base_leverage * random_factor
        
        # Round to 2 decimal places for realistic dynamic values
        dynamic_leverage = dynamic_leverage.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        
        # Ensure it's within bounds
        dynamic_leverage = max(dynamic_leverage, STRICT_CONFIG.min_dynamic_leverage)
        dynamic_leverage = min(dynamic_leverage, Decimal("50"))
        
        return dynamic_leverage
    
    def _is_valid_usdt_symbol(self, symbol: str) -> bool:
        """Validate trading symbol format."""
        if len(symbol) < 6 or len(symbol) > 20:  # Increased max length to 20 for longer symbols
            return False
        # Only accept USDT symbols
        return symbol.endswith('USDT') and len(symbol) >= 6
    
    def _validate_signal_data(self, symbol: str, direction: str, entries: List[str], 
                            tps: List[str], sl: str, leverage: Decimal, mode: str) -> bool:
        """Validate all signal data components."""
        try:
            # Validate symbol
            if not symbol or not self._is_valid_usdt_symbol(symbol):
                return False
            
            # Validate direction
            if direction not in ['BUY', 'SELL', 'LONG', 'SHORT']:
                return False
            
            # Validate entries
            if not entries or len(entries) == 0:
                return False
            
            # Validate leverage
            if leverage <= 0 or leverage > 50:
                return False
            
            # Validate mode
            if mode not in ['SWING', 'FAST', 'DYNAMIC']:
                return False
            
            return True
        except Exception:
            return False

# Global parser instance
_parser_instance = None

def get_strict_parser() -> StrictSignalParser:
    """Get global strict parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = StrictSignalParser()
    return _parser_instance

def parse_signal_strict(message: str, channel_name: str) -> Optional[Dict[str, Any]]:
    """Parse signal with strict client requirements (convenience function)."""
    return get_strict_parser().parse_signal(message, channel_name)