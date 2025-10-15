"""Strict compliance Telegram client with all client requirements."""

from telethon import TelegramClient, events
from telethon.sessions import SQLiteSession
from app.core.strict_config import STRICT_CONFIG
from app.signals.strict_parser import get_strict_parser
from app.core.idempotency import is_duplicate_signal, mark_signal_processed
from app.core.signal_blocking import is_signal_blocked
from app.core.confirmation_gate import get_confirmation_gate
from app.core.strict_fsm import TradeFSM
from app.core.logging import system_logger, telegram_logger
# CLIENT FIX: Migrated to use engine.py instead of swedish_templates_v2
from app.telegram.engine import render_template
from app.telegram.output import send_message
from datetime import datetime
import asyncio
import sqlite3

class StrictTelegramClient:
    """Strict compliance Telegram client with exact client requirements."""
    
    def __init__(self):
        # AUDIT FIX: Create fresh session without WAL mode complications
        # WAL mode was causing connection hangs
        session_path = STRICT_CONFIG.telegram_session
        
        system_logger.info(f"Creating Telegram client with session: {session_path}")
        
        # FIX: Use StringSession instead of SQLiteSession to avoid database locking
        # The SQLiteSession was causing "database is locked" errors on Windows
        self.client = TelegramClient(
            session_path,  # Use string path
            STRICT_CONFIG.telegram_api_id,
            STRICT_CONFIG.telegram_api_hash,
            timeout=30,  # Add timeout to prevent hanging
            connection_retries=3,  # Limit retries
            retry_delay=1  # Delay between retries
        )
        self.parser = get_strict_parser()
        # CLIENT FIX: Removed self.templates - using render_template() instead
        self.confirmation_gate = get_confirmation_gate()
        self.active_trades = {}  # Track active trades
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup event handlers."""
        # Register handler directly - decorator in method can be problematic
        self.client.add_event_handler(
            self._handle_message,
            events.NewMessage()
        )
        system_logger.info("Message handler registered for all new messages")
        
        # Add test handler to verify events are being received AT ALL
        @self.client.on(events.Raw)
        async def raw_handler(update):
            system_logger.debug(f"🔔 RAW EVENT RECEIVED: {type(update).__name__}")
        
        system_logger.info("🧪 Debug: Raw event handler also registered")
    
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
            signal_data = await self.parser.parse_signal(text, channel_name)
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
            
            # Check for signal blocking (3-hour window, 5% tolerance)
            is_blocked, block_reason = is_signal_blocked(signal_data)
            if is_blocked:
                system_logger.info("Signal blocked by 3-hour rule", {
                    'symbol': signal_data['symbol'],
                    'direction': signal_data['direction'],
                    'channel': channel_name,
                    'reason': block_reason
                })
                # Send blocking message to user
                await self._send_signal_blocked(signal_data, block_reason)
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
            # Get channel ID
            channel_id = str(event.chat_id)
            
            # Check if channel ID is whitelisted
            allowed = STRICT_CONFIG.is_channel_whitelisted(channel_id)
            
            # Get channel name for logging
            channel_name = STRICT_CONFIG.get_channel_name(channel_id)
            
            # DEBUG: Log test channel checks
            if channel_id == "-1003027029201":
                system_logger.info(f"🧪 TEST CHANNEL CHECK: allowed={allowed}, name={channel_name}, whitelist_size={len(STRICT_CONFIG.source_whitelist)}")
            
            return allowed, channel_name
            
        except Exception as e:
            system_logger.error(f"Channel check error: {e}", exc_info=True)
            return False, "unknown"
    
    async def _send_signal_received(self, signal_data: dict):
        """Send signal received message using Engine."""
        try:
            # CLIENT FIX: Pass ALL signal data including TP/SL (Phase 4 integration)
            from decimal import Decimal, InvalidOperation
            
            # Helper function to normalize Swedish format for Decimal conversion
            def to_decimal_safe(value):
                """Convert value to Decimal, handling Swedish number format (comma as decimal separator)."""
                if value is None or value == "" or value == 0:
                    return None
                if isinstance(value, Decimal):
                    return value
                try:
                    # Normalize: replace comma with dot for Swedish format
                    val_str = str(value).replace(",", ".")
                    return Decimal(val_str)
                except (ValueError, InvalidOperation):
                    return None
            
            # Prepare complete data for new template format
            entry_val = signal_data.get('entry', signal_data.get('entries', [0])[0] if signal_data.get('entries') else 0)
            
            template_data = {
                'symbol': signal_data['symbol'],
                'source_name': signal_data['channel_name'],
                'side': signal_data.get('side', signal_data.get('direction', 'LONG')),
                'trade_id': signal_data.get('trade_id', ''),
                # Entry and TP/SL data (from signal) - using safe conversion
                'entry': to_decimal_safe(entry_val),
                'tp1': to_decimal_safe(signal_data['tps'][0]) if signal_data.get('tps') and len(signal_data['tps']) > 0 else None,
                'tp2': to_decimal_safe(signal_data['tps'][1]) if signal_data.get('tps') and len(signal_data['tps']) > 1 else None,
                'tp3': to_decimal_safe(signal_data['tps'][2]) if signal_data.get('tps') and len(signal_data['tps']) > 2 else None,
                'tp4': to_decimal_safe(signal_data['tps'][3]) if signal_data.get('tps') and len(signal_data['tps']) > 3 else None,
                'sl': to_decimal_safe(signal_data.get('sl')),
                # Leverage (calculated by bot initially, will be updated from Bybit later)
                'leverage': to_decimal_safe(signal_data.get('leverage', 6.00)) or Decimal("6.00"),
                # IM (estimated initially)
                'im': to_decimal_safe(signal_data.get('im', 20.00)) or Decimal("20.00"),
                # Order IDs (empty initially)
                'bot_order_id': '',
                'bybit_order_id': ''
            }
            
            rendered = render_template("SIGNAL_RECEIVED", template_data)
            
            # Send with metadata
            await send_message(
                rendered["text"],
                template_name=rendered["template_name"],
                trade_id=rendered["trade_id"],
                symbol=rendered["symbol"],
                hashtags=rendered["hashtags"]
            )
            
            system_logger.info("Signal received message sent", {
                'symbol': signal_data['symbol'],
                'mode': signal_data.get('mode', 'N/A'),
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
        """Send error message using Engine."""
        try:
            # Parse specific error types for better user understanding
            error_type, specific_message = self._parse_error_message(error_message)
            
            # CLIENT FIX: Use Engine for error messages
            rendered = render_template("ERROR_MESSAGE", {
                'symbol': signal_data['symbol'],
                'error': specific_message,
                'source_name': signal_data.get('channel_name', 'Unknown'),
                'trade_id': signal_data.get('trade_id', '')
            })
            
            # Send with metadata
            await send_message(
                rendered["text"],
                template_name=rendered["template_name"],
                trade_id=rendered["trade_id"],
                symbol=rendered["symbol"],
                hashtags=rendered["hashtags"]
            )
            
        except Exception as e:
            system_logger.error(f"Error sending error message: {e}", exc_info=True)
    
    def _parse_error_message(self, error_message: str) -> tuple[str, str]:
        """Parse error message to provide specific, actionable information."""
        error_lower = error_message.lower()
        
        if "qty invalid" in error_lower:
            return (
                "Ogiltig Position Storlek",
                "Position storlek uppfyller inte Bybit's krav. Kontrollera min/max kvantitet och notional värde."
            )
        elif "side invalid" in error_lower:
            return (
                "Ogiltig Riktning",
                "Handelsriktning är ogiltig. Använd 'Buy' för LONG eller 'Sell' för SHORT."
            )
        elif "insufficient balance" in error_lower:
            return (
                "Otillräckligt Saldo",
                "Kontot har inte tillräckligt saldo för att placera ordern. Kontrollera tillgängligt kapital."
            )
        elif "symbol not found" in error_lower or "closed symbol" in error_lower:
            return (
                "Symbol Inte Tillgänglig",
                "Symbolen är inte tillgänglig för handel på Bybit. Kontrollera symbol status."
            )
        elif "leverage invalid" in error_lower:
            return (
                "Ogiltig Hävstång",
                "Hävstången är ogiltig för denna symbol. Kontrollera tillåten hävstångsgräns."
            )
        elif "price invalid" in error_lower:
            return (
                "Ogiltigt Pris",
                "Priset uppfyller inte Bybit's tick size krav. Kontrollera pris precision."
            )
        elif "timeout" in error_lower:
            return (
                "Tidsgräns Överskriden",
                "Bybit API svarade inte inom tillåten tid. Försök igen senare."
            )
        elif "network" in error_lower or "connection" in error_lower:
            return (
                "Nätverksfel",
                "Problem med nätverksanslutning till Bybit. Kontrollera internetanslutning."
            )
        else:
            return (
                "Trade Execution",
                f"Okänt fel: {error_message}"
            )
    
    async def start(self):
        """Start the strict Telegram client."""
        try:
            # CRITICAL FIX: client.start() hangs waiting for user input
            # Use connect() for authenticated sessions to avoid interactive prompts
            system_logger.info("🔌 TELEGRAM: Connecting with authenticated session...")
            print("🔌 Connecting Telegram client...")
            
            # First connect
            await self.client.connect()
            system_logger.info("✅ TELEGRAM: Connected")
            print("✅ Connected")
            
            # Check if authorized
            is_auth = await self.client.is_user_authorized()
            system_logger.info(f"🔑 TELEGRAM: Authorization status: {is_auth}")
            print(f"🔑 Authorization: {is_auth}")
            
            if not is_auth:
                system_logger.error("❌ TELEGRAM: Session not authorized! Run: python authenticate_telegram.py")
                print("❌ Session not authorized! Run: python authenticate_telegram.py")
                raise RuntimeError("Telegram session not authorized - run authenticate_telegram.py first")
            
            # Verify connection status
            is_connected = self.client.is_connected()
            system_logger.info(f"🔍 TELEGRAM: Connection status: {is_connected}")
            print(f"🔍 Connection status: {is_connected}")
            
            system_logger.info("👤 TELEGRAM: Fetching user info...")
            print("👤 Getting user info...")
            
            me = await self.client.get_me()
            system_logger.info(f"✅ TELEGRAM: Logged in as {me.first_name} (ID: {me.id})")
            print(f"✅ Logged in as {me.first_name}")
            
            system_logger.info("Strict Telegram client started", {
                'session': STRICT_CONFIG.telegram_session,
                'api_id': STRICT_CONFIG.telegram_api_id,
                'user_id': me.id,
                'user_name': me.first_name
            })
            print("[OK] Strict Telegram client started")
            
            # Start connection monitoring
            asyncio.create_task(self._monitor_connection())
            
        except Exception as e:
            system_logger.error(f"Failed to start Telegram client: {e}", exc_info=True)
            raise
    
    async def _monitor_connection(self):
        """Monitor Telegram connection and reconnect if needed."""
        while True:
            try:
                if not self.client.is_connected():
                    system_logger.warning("Telegram connection lost, attempting to reconnect...")
                    await self.client.connect()
                    system_logger.info("Telegram connection restored")
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                system_logger.error(f"Connection monitoring error: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def stop(self):
        """Stop the strict Telegram client."""
        try:
            await self.client.disconnect()
            system_logger.info("Strict Telegram client stopped")
            print("[OK] Strict Telegram client stopped")
            
        except Exception as e:
            system_logger.error(f"Error stopping Telegram client: {e}", exc_info=True)
    
    async def _send_signal_blocked(self, signal_data: dict, block_reason: str):
        """
        Send signal blocked message.
        
        CLIENT FIX (DEEP_ANALYSIS): Use template engine instead of direct f-string.
        CLIENT SPEC: doc/10_12_3.md Lines 2521-2526
        """
        try:
            from app.telegram.engine import render_template
            from app.telegram.output import send_message
            import re
            
            # Extract diff percentage from block_reason if available
            # Format: "Blocked (≤5% diff: 1.51%, 2h window)"
            diff_match = re.search(r'(\d+\.?\d*)%', block_reason)
            diff_pct = diff_match.group(1) if diff_match else "0"
            
            # Use template engine (CLIENT SPEC compliance)
            rendered = render_template("SIGNAL_BLOCKED", {
                'symbol': signal_data.get('symbol', ''),
                'source_name': signal_data.get('channel_name', 'Unknown'),
                'side': signal_data.get('direction', 'UNKNOWN'),
                'reason': block_reason,
                'diff_pct': diff_pct,
                'trade_id': signal_data.get('trade_id', '')
            })
            
            # Send with full metadata
            await send_message(
                rendered["text"],
                template_name=rendered["template_name"],
                trade_id=rendered["trade_id"],
                symbol=rendered["symbol"],
                hashtags=rendered["hashtags"]
            )
            
        except Exception as e:
            system_logger.error(f"Error sending signal blocked message: {e}", exc_info=True)
    
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