"""Enhanced Telegram client with integrated trade execution."""

from telethon import TelegramClient, events
from app.config import settings
from app.signals.processor import get_signal_processor
from app.core.logging import system_logger, telegram_logger
from app.telegram.output import send_message
from app.telegram import templates_v2
from datetime import datetime


class EnhancedTelegramClient:
    """Enhanced Telegram client with integrated signal processing and trade execution."""
    
    def __init__(self):
        self.client = TelegramClient(
            settings.TELEGRAM_SESSION,
            settings.TELEGRAM_API_ID,
            settings.TELEGRAM_API_HASH
        )
        self.signal_processor = None
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup event handlers."""
        
        @self.client.on(events.NewMessage)
        async def handle_new_message(event):
            await self._handle_message(event)
    
    async def _handle_message(self, event):
        """Handle incoming Telegram messages."""
        try:
            print(f"📩 Received message from chat {event.chat_id}")
            
            # Check if channel is allowed
            allowed, channel_name = await self._check_channel_allowed(event)
            print(f"🔍 Channel check: allowed={allowed}, name='{channel_name}'")
            
            if not allowed:
                print(f"❌ Channel '{channel_name}' not in whitelist: {settings.SRC_CHANNEL_NAMES}")
                return
            
            # Get message text
            text = (event.raw_text or "").strip()
            print(f"📝 Message text: '{text[:100]}...'")
            
            if not text:
                print("❌ Empty message, skipping")
                return
            
            # Process and execute signal
            result = await self._process_and_execute_signal(text, event.chat_id, channel_name)
            
            if result['success']:
                print(f"✅ Signal processed and executed: {result.get('symbol', 'unknown')}")
            else:
                print(f"❌ Signal processing failed: {result.get('reason', 'Unknown error')}")
                
        except Exception as e:
            system_logger.error(f"Message handling failed: {e}", {
                'chat_id': event.chat_id,
                'message': str(event.raw_text)[:100] if event.raw_text else None
            }, exc_info=True)
    
    async def _check_channel_allowed(self, event) -> tuple[bool, str]:
        """Check if channel is allowed and get channel name."""
        try:
            ent = await event.get_chat()
            name = getattr(ent, "title", "") or getattr(ent, "username", "") or str(event.chat_id)
            
            # Check if channel ID is in allowed list
            if settings.ALLOWED_CHANNEL_IDS and event.chat_id not in settings.ALLOWED_CHANNEL_IDS:
                return False, name
                
            # If we have a mapping, use the mapped name
            if settings.CHANNEL_ID_NAME_MAP and event.chat_id in settings.CHANNEL_ID_NAME_MAP:
                mapped_name = settings.CHANNEL_ID_NAME_MAP[event.chat_id]
                return True, mapped_name
                
            # Fallback to name-based filtering
            if settings.SRC_CHANNEL_NAMES:
                return (name in settings.SRC_CHANNEL_NAMES), name
                
            # If no filters configured, allow all
            return True, name
            
        except Exception as e:
            system_logger.error(f"Channel check failed: {e}")
            return False, "?"
    
    async def _process_and_execute_signal(self, message: str, chat_id: int, channel_name: str) -> dict:
        """Process signal and execute if valid."""
        try:
            # Get signal processor
            if not self.signal_processor:
                self.signal_processor = await get_signal_processor()
            
            # Process and execute signal
            result = await self.signal_processor.process_and_execute(message, chat_id, channel_name)
            
            # Send notification to output channel
            if result['success']:
                await self._send_success_notification(result, channel_name)
            else:
                await self._send_failure_notification(result, channel_name)
            
            return result
            
        except Exception as e:
            system_logger.error(f"Signal processing failed: {e}", exc_info=True)
            return {
                'success': False,
                'reason': f'Processing error: {str(e)}'
            }
    
    async def _send_success_notification(self, result: dict, channel_name: str):
        """Send success notification to output channel."""
        try:
            symbol = result.get('symbol', 'Unknown')
            direction = result.get('direction', 'Unknown')
            size = result.get('position_size', 0)
            leverage = result.get('leverage', 1)
            
            message = f"""
🎯 **Trade Executed Successfully**

📊 **Symbol:** {symbol}
📈 **Direction:** {direction}
💰 **Size:** {size}
⚡ **Leverage:** {leverage}x
📺 **Source:** {channel_name}
⏰ **Time:** {datetime.now().strftime('%H:%M:%S')}

✅ Position opened and being monitored
            """.strip()
            
            await send_message(message)
            
        except Exception as e:
            telegram_logger.error(f"Failed to send success notification: {e}")
    
    async def _send_failure_notification(self, result: dict, channel_name: str):
        """Send failure notification to output channel."""
        try:
            reason = result.get('reason', 'Unknown error')
            symbol = result.get('symbol', 'Unknown')
            
            message = f"""
❌ **Trade Execution Failed**

📊 **Symbol:** {symbol}
📺 **Source:** {channel_name}
⚠️ **Reason:** {reason}
⏰ **Time:** {datetime.now().strftime('%H:%M:%S')}

🔄 Signal was processed but trade could not be executed
            """.strip()
            
            await send_message(message)
            
        except Exception as e:
            telegram_logger.error(f"Failed to send failure notification: {e}")
    
    async def start(self):
        """Start the Telegram client."""
        print("🔌 Starting Enhanced Telegram client...")
        print(f"📋 Whitelisted channels: {settings.SRC_CHANNEL_NAMES}")
        print(f"🔑 API ID: {settings.TELEGRAM_API_ID}")
        print(f"🔑 API Hash: {'*' * len(settings.TELEGRAM_API_HASH) if settings.TELEGRAM_API_HASH else 'NOT SET'}")
        
        try:
            print("🔄 Connecting to Telegram...")
            await self.client.start()
            print("✅ Enhanced Telegram client started successfully!")
            print("📡 Listening for signals from whitelisted channels...")
            print("🎯 Bot is ready! Send test signals to your channels.")
            
            # Initialize signal processor
            self.signal_processor = await get_signal_processor()
            print("🔧 Signal processor initialized")
            
            # Keep the bot running
            await self.client.run_until_disconnected()
            
        except Exception as e:
            print(f"❌ Telegram connection failed: {e}")
            print("💡 Troubleshooting:")
            print("   1. Check if .env file has correct TELEGRAM_API_ID and TELEGRAM_API_HASH")
            print("   2. Run 'python telegram_auth.py' for first-time authentication")
            print("   3. Make sure you have internet connection")
            print("   4. Check if Telegram API credentials are valid")
            
            # Don't raise the exception, just log it and continue
            print("🔄 Continuing without Telegram connection...")
            return
    
    async def stop(self):
        """Stop the Telegram client."""
        try:
            await self.client.disconnect()
            print("✅ Telegram client stopped")
        except Exception as e:
            print(f"⚠️ Error stopping Telegram client: {e}")


# Global client instance
_client_instance = None

async def get_enhanced_client() -> EnhancedTelegramClient:
    """Get or create enhanced Telegram client instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = EnhancedTelegramClient()
    return _client_instance

async def start_enhanced_telegram():
    """Start the enhanced Telegram client."""
    client = await get_enhanced_client()
    await client.start()