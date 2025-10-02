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
        # Symbol patterns (USDT perps only)
        self.symbol_patterns = [
            r'([A-Z]{2,10}USDT)',  # Standard USDT pairs
        ]
        
        # Direction patterns (exact client requirements)
        self.direction_patterns = {
            'LONG': [r'\b(LONG|BUY|🟢|📈|🚀)\b'],
            'SHORT': [r'\b(SHORT|SELL|🔴|📉|🔻)\b']
        }
        
        # Price patterns
        self.price_patterns = [
            r'(\d+\.?\d*)\s*USDT',
            r'Entry[:\s]*(\d+\.?\d*)',
            r'Price[:\s]*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*\$',
            r'@\s*(\d+\.?\d*)',  # @45000 format
        ]
        
        # TP patterns (up to 4 TPs)
        self.tp_patterns = [
            r'TP[1-4]?[:\s]*(\d+\.?\d*)',
            r'Target[:\s]*(\d+\.?\d*)',
            r'Take[:\s]*(\d+\.?\d*)',
        ]
        
        # SL patterns
        self.sl_patterns = [
            r'SL[:\s]*(\d+\.?\d*)',
            r'Stop[:\s]*(\d+\.?\d*)',
            r'StopLoss[:\s]*(\d+\.?\d*)',
        ]
        
        # Leverage patterns
        self.leverage_patterns = [
            r'(\d+)x',
            r'Leverage[:\s]*(\d+)',
            r'Lev[:\s]*(\d+)',
        ]
        
        # Mode patterns
        self.mode_patterns = {
            'SWING': [r'\b(SWING|Swing|swing)\b'],
            'FAST': [r'\b(FAST|Fast|fast)\b'],
            'DYNAMIC': [r'\b(DYNAMIC|Dynamic|dynamic)\b']
        }
    
    def parse_signal(self, message: str, channel_name: str) -> Optional[Dict[str, Any]]:
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
            
            # Extract direction (required)
            direction = self._extract_direction(message_upper)
            if not direction:
                return None
            
            # Extract entries (required, ≥1)
            entries = self._extract_entries(message)
            if not entries:
                return None
            
            # Synthesize second entry if only one provided
            if len(entries) == 1:
                entries = self._synthesize_second_entry(entries[0], direction)
            
            # Extract TPs and SL
            tps = self._extract_tps(message)
            sl = self._extract_sl(message)
            
            # Check if we have at least one TP or SL (required)
            if not tps and not sl:
                return None
            
            # Extract leverage and mode
            raw_leverage = self._extract_leverage(message)
            mode_hint = self._extract_mode(message_upper)
            
            # Apply leverage policy
            leverage, mode = self._classify_leverage(mode_hint, bool(sl), raw_leverage)
            
            # Handle missing SL case
            if not sl:
                sl = self._synthesize_sl(entries[0], direction)
                leverage = STRICT_CONFIG.fast_leverage  # Force FAST x10
                mode = "FAST"
            
            # Validate leverage gap
            if STRICT_CONFIG.is_leverage_in_forbidden_gap(leverage):
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
                symbol = matches[0]
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
        for pattern in self.price_patterns:
            matches = re.findall(pattern, message)
            for match in matches:
                try:
                    price = to_decimal(match)
                    if Decimal("0.001") <= price <= Decimal("1000000"):  # Reasonable range
                        entries.append(price)
                except (ValueError, TypeError):
                    continue
        
        # Remove duplicates and sort
        entries = sorted(list(set(entries)))
        return entries[:2]  # Max 2 entries
    
    def _extract_tps(self, message: str) -> List[Decimal]:
        """Extract take profit levels (up to 4)."""
        tps = []
        for pattern in self.tp_patterns:
            matches = re.findall(pattern, message)
            for match in matches:
                try:
                    tp = to_decimal(match)
                    if Decimal("0.001") <= tp <= Decimal("1000000"):
                        tps.append(tp)
                except (ValueError, TypeError):
                    continue
        
        # Remove duplicates and sort
        tps = sorted(list(set(tps)))
        return tps[:4]  # Max 4 TPs
    
    def _extract_sl(self, message: str) -> Optional[Decimal]:
        """Extract stop loss level."""
        for pattern in self.sl_patterns:
            matches = re.findall(pattern, message)
            if matches:
                try:
                    sl = to_decimal(matches[0])
                    if Decimal("0.001") <= sl <= Decimal("1000000"):
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
    
    def _synthesize_second_entry(self, entry: Decimal, direction: str) -> List[Decimal]:
        """Synthesize second entry at ±0.1% in trade direction."""
        bump = entry * Decimal("0.001")  # 0.1%
        if direction == "LONG":
            entry2 = entry - bump  # Lower price for LONG
        else:  # SHORT
            entry2 = entry + bump  # Higher price for SHORT
        
        return [entry, entry2]
    
    def _synthesize_sl(self, entry: Decimal, direction: str) -> Decimal:
        """Synthesize SL at ±2% in adverse direction."""
        sl_offset = entry * Decimal("0.02")  # 2%
        if direction == "LONG":
            sl = entry - sl_offset  # Below entry for LONG
        else:  # SHORT
            sl = entry + sl_offset  # Above entry for SHORT
        
        return sl
    
    def _classify_leverage(self, mode_hint: Optional[str], has_sl: bool, raw_leverage: Optional[Decimal]) -> Tuple[Decimal, str]:
        """Classify leverage according to client rules."""
        if not has_sl:
            # Missing SL → FAST x10
            return STRICT_CONFIG.fast_leverage, "FAST"
        
        if mode_hint == "SWING":
            return STRICT_CONFIG.swing_leverage, "SWING"
        
        if mode_hint == "FAST":
            return STRICT_CONFIG.fast_leverage, "FAST"
        
        if mode_hint == "DYNAMIC":
            leverage = raw_leverage or STRICT_CONFIG.min_dynamic_leverage
            leverage = max(leverage, STRICT_CONFIG.min_dynamic_leverage)
            return leverage, "DYNAMIC"
        
        # Default to DYNAMIC with minimum leverage
        leverage = raw_leverage or STRICT_CONFIG.min_dynamic_leverage
        leverage = max(leverage, STRICT_CONFIG.min_dynamic_leverage)
        return leverage, "DYNAMIC"
    
    def _is_valid_usdt_symbol(self, symbol: str) -> bool:
        """Validate USDT symbol format."""
        if len(symbol) < 6 or len(symbol) > 12:
            return False
        return symbol.endswith("USDT") and len(symbol) >= 6

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