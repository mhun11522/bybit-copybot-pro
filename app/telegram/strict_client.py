"""Strict compliance Telegram client with all client requirements."""

from telethon import TelegramClient, events
from app.core.strict_config import STRICT_CONFIG
from app.signals.strict_parser import get_strict_parser
from app.core.idempotency import is_duplicate_signal, mark_signal_processed
from app.core.confirmation_gate import get_confirmation_gate
from app.core.strict_fsm import TradeFSM
from app.core.logging import system_logger, telegram_logger
from app.telegram.swedish_templates import get_swedish_templates
from app.telegram.output import send_message
from datetime import datetime
import asyncio

class StrictTelegramClient:
    """Strict compliance Telegram client with exact client requirements."""
    
    def __init__(self):
        self.client = TelegramClient(
            STRICT_CONFIG.telegram_session,
            STRICT_CONFIG.telegram_api_id,
            STRICT_CONFIG.telegram_api_hash
        )
        self.parser = get_strict_parser()
        self.templates = get_swedish_templates()
        self.confirmation_gate = get_confirmation_gate()
        self.active_trades = {}  # Track active trades
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup event handlers."""
        
        @self.client.on(events.NewMessage)
        async def handle_new_message(event):
            await self._handle_message(event)
    
    async def _handle_message(self, event):
        """Handle incoming Telegram messages with strict compliance."""
        try:
            system_logger.info("Received message", {
                'chat_id': event.chat_id,
                'message_length': len(event.raw_text or ''),
                'timestamp': datetime.now().isoformat()
            })
            
            # Check if channel is allowed
            allowed, channel_name = await self._check_channel_allowed(event)
            if not allowed:
                system_logger.debug(f"Channel '{channel_name}' not in whitelist")
                return
            
            # Get message text
            text = (event.raw_text or "").strip()
            if not text:
                system_logger.debug("Empty message, skipping")
                return
            
            # Parse signal with strict requirements
            signal_data = self.parser.parse_signal(text, channel_name)
            if not signal_data:
                system_logger.debug("Signal parsing failed", {
                    'text': text[:100],
                    'channel': channel_name
                })
                return
            
            # Check for duplicates (idempotency)
            if is_duplicate_signal(signal_data):
                system_logger.info("Duplicate signal suppressed", {
                    'symbol': signal_data['symbol'],
                    'channel': channel_name
                })
                return
            
            # Mark signal as processed
            mark_signal_processed(signal_data)
            
            # Send signal received message (Swedish template)
            await self._send_signal_received(signal_data)
            
            # Start trade FSM
            await self._start_trade_fsm(signal_data)
            
        except Exception as e:
            system_logger.error(f"Message handling error: {e}", {
                'chat_id': event.chat_id,
                'text': (event.raw_text or '')[:100]
            }, exc_info=True)
    
    async def _check_channel_allowed(self, event) -> tuple[bool, str]:
        """Check if channel is in whitelist."""
        try:
            # Get channel name
            if hasattr(event.chat, 'title'):
                channel_name = event.chat.title
            elif hasattr(event.chat, 'username'):
                channel_name = f"@{event.chat.username}"
            else:
                channel_name = str(event.chat_id)
            
            # Check whitelist
            allowed = channel_name in STRICT_CONFIG.source_whitelist
            return allowed, channel_name
            
        except Exception as e:
            system_logger.error(f"Channel check error: {e}", exc_info=True)
            return False, "unknown"
    
    async def _send_signal_received(self, signal_data: dict):
        """Send signal received message using Swedish template."""
        try:
            message = self.templates.signal_received(signal_data)
            await send_message(message)
            
            system_logger.info("Signal received message sent", {
                'symbol': signal_data['symbol'],
                'mode': signal_data['mode'],
                'channel': signal_data['channel_name']
            })
            
        except Exception as e:
            system_logger.error(f"Error sending signal received message: {e}", exc_info=True)
    
    async def _start_trade_fsm(self, signal_data: dict):
        """Start trade FSM for signal."""
        try:
            # Create trade FSM
            fsm = TradeFSM(signal_data)
            trade_id = fsm.trade_id
            
            # Store active trade
            self.active_trades[trade_id] = fsm
            
            system_logger.info("Starting trade FSM", {
                'trade_id': trade_id,
                'symbol': signal_data['symbol'],
                'direction': signal_data['direction'],
                'mode': signal_data['mode']
            })
            
            # Run FSM in background
            asyncio.create_task(self._run_trade_fsm(fsm))
            
        except Exception as e:
            system_logger.error(f"Error starting trade FSM: {e}", {
                'symbol': signal_data.get('symbol', 'unknown')
            }, exc_info=True)
    
    async def _run_trade_fsm(self, fsm: TradeFSM):
        """Run trade FSM and handle completion."""
        try:
            # Run FSM
            success = await fsm.run()
            
            # Remove from active trades
            if fsm.trade_id in self.active_trades:
                del self.active_trades[fsm.trade_id]
            
            if success:
                system_logger.info("Trade FSM completed successfully", {
                    'trade_id': fsm.trade_id,
                    'symbol': fsm.signal_data['symbol']
                })
            else:
                system_logger.error("Trade FSM failed", {
                    'trade_id': fsm.trade_id,
                    'symbol': fsm.signal_data['symbol'],
                    'final_state': fsm.state.value
                })
                
                # Send error message
                await self._send_error_message(fsm.signal_data, "Trade execution failed")
                
        except Exception as e:
            system_logger.error(f"Trade FSM execution error: {e}", {
                'trade_id': fsm.trade_id,
                'symbol': fsm.signal_data.get('symbol', 'unknown')
            }, exc_info=True)
            
            # Send error message
            await self._send_error_message(fsm.signal_data, str(e))
    
    async def _send_error_message(self, signal_data: dict, error_message: str):
        """Send error message using Swedish template."""
        try:
            error_data = {
                'symbol': signal_data['symbol'],
                'error_type': 'Trade Execution',
                'error_message': error_message
            }
            
            message = self.templates.error_occurred(error_data)
            await send_message(message)
            
        except Exception as e:
            system_logger.error(f"Error sending error message: {e}", exc_info=True)
    
    async def start(self):
        """Start the strict Telegram client."""
        try:
            await self.client.start()
            system_logger.info("Strict Telegram client started", {
                'session': STRICT_CONFIG.telegram_session,
                'api_id': STRICT_CONFIG.telegram_api_id
            })
            print("[OK] Strict Telegram client started")
            
        except Exception as e:
            system_logger.error(f"Failed to start Telegram client: {e}", exc_info=True)
            raise
    
    async def stop(self):
        """Stop the strict Telegram client."""
        try:
            await self.client.disconnect()
            system_logger.info("Strict Telegram client stopped")
            print("[OK] Strict Telegram client stopped")
            
        except Exception as e:
            system_logger.error(f"Error stopping Telegram client: {e}", exc_info=True)
    
    def get_active_trades_count(self) -> int:
        """Get count of active trades."""
        return len(self.active_trades)
    
    def get_active_trades_info(self) -> dict:
        """Get information about active trades."""
        return {
            'count': len(self.active_trades),
            'trades': [
                {
                    'trade_id': trade_id,
                    'symbol': fsm.signal_data['symbol'],
                    'direction': fsm.signal_data['direction'],
                    'state': fsm.state.value,
                    'mode': fsm.signal_data['mode']
                }
                for trade_id, fsm in self.active_trades.items()
            ]
        }

# Global strict client instance
_strict_client = None

async def get_strict_telegram_client() -> StrictTelegramClient:
    """Get global strict Telegram client instance."""
    global _strict_client
    if _strict_client is None:
        _strict_client = StrictTelegramClient()
    return _strict_client

async def start_strict_telegram():
    """Start the strict Telegram client."""
    client = await get_strict_telegram_client()
    await client.start()
    
    # Keep running
    try:
        await client.client.run_until_disconnected()
    except KeyboardInterrupt:
        await client.stop()
    except Exception as e:
        system_logger.error(f"Telegram client error: {e}", exc_info=True)
        await client.stop()
        raise