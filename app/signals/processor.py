"""Enhanced signal processing with trade execution integration."""

import re
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from app.core.logging import trade_logger, system_logger
from app.trade.executor import get_trade_executor
from app.storage.db import get_db_connection


class SignalProcessor:
    """Processes Telegram signals and converts them to tradeable signals."""
    
    def __init__(self):
        self.symbol_patterns = [
            r'([A-Z]{2,10}USDT)',  # Standard USDT pairs
            r'([A-Z]{2,10}BTC)',   # BTC pairs
            r'([A-Z]{2,10}ETH)',   # ETH pairs
        ]
        self.direction_patterns = [
            r'\b(BUY|LONG|🟢|📈|🚀)\b',
            r'\b(SELL|SHORT|🔴|📉|🔻)\b'
        ]
        self.price_patterns = [
            r'(\d+\.?\d*)\s*USDT',
            r'Entry[:\s]*(\d+\.?\d*)',
            r'Price[:\s]*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*\$'
        ]
        self.leverage_patterns = [
            r'(\d+)x',
            r'Leverage[:\s]*(\d+)',
            r'Lev[:\s]*(\d+)'
        ]
    
    async def process_signal(self, message: str, chat_id: int, channel_name: str) -> Optional[Dict[str, Any]]:
        """
        Process a Telegram message and extract trading signal.
        
        Args:
            message: Raw message text
            chat_id: Telegram chat ID
            channel_name: Channel name
            
        Returns:
            Processed signal data or None if not a valid signal
        """
        try:
            # Extract signal components
            symbol = self._extract_symbol(message)
            if not symbol:
                return None
            
            direction = self._extract_direction(message)
            if not direction:
                return None
            
            entries = self._extract_entries(message)
            if not entries:
                return None
            
            leverage = self._extract_leverage(message)
            risk_percent = self._extract_risk_percent(message)
            
            # Create signal data
            signal_data = {
                'symbol': symbol,
                'direction': direction,
                'entries': entries,
                'channel_name': channel_name,
                'chat_id': chat_id,
                'leverage': leverage,
                'risk_percent': risk_percent,
                'timestamp': datetime.now().isoformat(),
                'raw_message': message
            }
            
            # Log signal parsing
            trade_logger.signal_parsed(symbol, direction, channel_name, {
                'entries': entries,
                'leverage': leverage,
                'risk_percent': risk_percent
            })
            
            return signal_data
            
        except Exception as e:
            system_logger.error(f"Signal processing failed: {e}", {
                'message': message[:100],
                'channel': channel_name
            }, exc_info=True)
            return None
    
    def _extract_symbol(self, message: str) -> Optional[str]:
        """Extract trading symbol from message."""
        message_upper = message.upper()
        
        for pattern in self.symbol_patterns:
            matches = re.findall(pattern, message_upper)
            if matches:
                symbol = matches[0]
                # Validate symbol format
                if self._is_valid_symbol(symbol):
                    return symbol
        
        return None
    
    def _extract_direction(self, message: str) -> Optional[str]:
        """Extract trade direction from message."""
        message_upper = message.upper()
        
        # Check for BUY signals
        for pattern in self.direction_patterns[:1]:
            if re.search(pattern, message_upper):
                return "BUY"
        
        # Check for SELL signals
        for pattern in self.direction_patterns[1:]:
            if re.search(pattern, message_upper):
                return "SELL"
        
        return None
    
    def _extract_entries(self, message: str) -> List[str]:
        """Extract entry prices from message."""
        entries = []
        
        for pattern in self.price_patterns:
            matches = re.findall(pattern, message)
            for match in matches:
                try:
                    price = float(match)
                    if 0.001 <= price <= 1000000:  # Reasonable price range
                        entries.append(str(price))
                except ValueError:
                    continue
        
        # Remove duplicates and sort
        entries = list(set(entries))
        entries.sort(key=float)
        
        return entries[:2]  # Max 2 entries for dual entry strategy
    
    def _extract_leverage(self, message: str) -> Optional[int]:
        """Extract leverage from message."""
        message_upper = message.upper()
        
        for pattern in self.leverage_patterns:
            matches = re.findall(pattern, message_upper)
            if matches:
                try:
                    leverage = int(matches[0])
                    if 1 <= leverage <= 100:  # Reasonable leverage range
                        return leverage
                except ValueError:
                    continue
        
        return None
    
    def _extract_risk_percent(self, message: str) -> Optional[float]:
        """Extract risk percentage from message."""
        # Look for percentage patterns
        percent_patterns = [
            r'(\d+\.?\d*)\s*%',
            r'Risk[:\s]*(\d+\.?\d*)',
            r'Size[:\s]*(\d+\.?\d*)'
        ]
        
        for pattern in percent_patterns:
            matches = re.findall(pattern, message)
            if matches:
                try:
                    percent = float(matches[0])
                    if 0.1 <= percent <= 50:  # Reasonable risk range
                        return percent / 100  # Convert to decimal
                except ValueError:
                    continue
        
        return None
    
    def _is_valid_symbol(self, symbol: str) -> bool:
        """Validate if symbol is likely a valid trading pair."""
        if len(symbol) < 4 or len(symbol) > 12:
            return False
        
        # Must contain USDT, BTC, or ETH
        valid_suffixes = ['USDT', 'BTC', 'ETH']
        if not any(symbol.endswith(suffix) for suffix in valid_suffixes):
            return False
        
        # Must have at least 2 characters before suffix
        for suffix in valid_suffixes:
            if symbol.endswith(suffix) and len(symbol) >= len(suffix) + 2:
                return True
        
        return False
    
    async def execute_signal(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a processed signal."""
        try:
            executor = await get_trade_executor()
            result = await executor.execute_signal(signal_data)
            
            if result['success']:
                system_logger.info(f"Signal executed successfully", {
                    'symbol': signal_data['symbol'],
                    'direction': signal_data['direction'],
                    'channel': signal_data['channel_name']
                })
            else:
                system_logger.warning(f"Signal execution failed", {
                    'symbol': signal_data['symbol'],
                    'reason': result.get('reason', 'Unknown'),
                    'channel': signal_data['channel_name']
                })
            
            return result
            
        except Exception as e:
            system_logger.error(f"Signal execution failed: {e}", {
                'symbol': signal_data.get('symbol', 'unknown')
            }, exc_info=True)
            return {
                'success': False,
                'reason': f'Execution error: {str(e)}'
            }
    
    async def process_and_execute(self, message: str, chat_id: int, channel_name: str) -> Dict[str, Any]:
        """Process signal and execute if valid."""
        # First process the signal
        signal_data = await self.process_signal(message, chat_id, channel_name)
        
        if not signal_data:
            return {
                'success': False,
                'reason': 'Invalid signal format'
            }
        
        # Check if signal was already processed (deduplication)
        if await self._is_duplicate_signal(signal_data):
            return {
                'success': False,
                'reason': 'Duplicate signal'
            }
        
        # Record signal as seen
        await self._record_signal_seen(signal_data)
        
        # Execute the signal
        return await self.execute_signal(signal_data)
    
    async def _is_duplicate_signal(self, signal_data: Dict[str, Any]) -> bool:
        """Check if signal was already processed recently."""
        try:
            # Create a simple hash of the signal
            signal_hash = self._create_signal_hash(signal_data)
            
            async with get_db_connection() as db:
                cursor = await db.execute("""
                    SELECT 1 FROM signal_seen 
                    WHERE signal_hash = ? AND timestamp > ?
                """, (signal_hash, int(datetime.now().timestamp()) - 3600))  # 1 hour window
                
                return await cursor.fetchone() is not None
                
        except Exception:
            return False
    
    async def _record_signal_seen(self, signal_data: Dict[str, Any]):
        """Record signal as seen to prevent duplicates."""
        try:
            signal_hash = self._create_signal_hash(signal_data)
            
            async with get_db_connection() as db:
                await db.execute("""
                    INSERT OR REPLACE INTO signal_seen 
                    (chat_id, signal_hash, timestamp) 
                    VALUES (?, ?, ?)
                """, (
                    signal_data['chat_id'],
                    signal_hash,
                    int(datetime.now().timestamp())
                ))
                await db.commit()
                
        except Exception as e:
            system_logger.error(f"Failed to record signal: {e}")
    
    def _create_signal_hash(self, signal_data: Dict[str, Any]) -> str:
        """Create a hash for signal deduplication."""
        import hashlib
        
        # Create hash from key signal components
        hash_string = f"{signal_data['symbol']}_{signal_data['direction']}_{signal_data['entries'][0]}"
        return hashlib.md5(hash_string.encode()).hexdigest()


# Global processor instance
_processor_instance = None

async def get_signal_processor() -> SignalProcessor:
    """Get or create signal processor instance."""
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = SignalProcessor()
    return _processor_instance