from telethon import TelegramClient, events
from app.config import settings
from app.telegram.templates import signal_received
from app.signals.idempotency import is_new_signal
from app.signals.normalizer import parse_signal
from app.trade.fsm import TradeFSM

client = TelegramClient(
    settings.TELEGRAM_SESSION,
    settings.TELEGRAM_API_ID,
    settings.TELEGRAM_API_HASH
)

async def _allowed_by_name(event) -> tuple[bool, str]:
    """
    Enforce allow-list by channel ID and name mapping.
    Returns (allowed, resolved_name).
    """
    try:
        ent = await event.get_chat()
        name = getattr(ent, "title", "") or getattr(ent, "username", "") or str(event.chat_id)
        
        # Check if channel ID is in allowed list
        if settings.ALLOWED_CHANNEL_IDS and event.chat_id not in settings.ALLOWED_CHANNEL_IDS:
            return False, name
            
        # If we have a mapping, use the mapped name, otherwise use the resolved name
        if settings.CHANNEL_ID_NAME_MAP and event.chat_id in settings.CHANNEL_ID_NAME_MAP:
            mapped_name = settings.CHANNEL_ID_NAME_MAP[event.chat_id]
            return True, mapped_name
            
        # Fallback to name-based filtering if no ID mapping
        if settings.SRC_CHANNEL_NAMES:
            return (name in settings.SRC_CHANNEL_NAMES), name
            
        # If no filters configured, allow all
        return True, name
        
    except Exception:
        return False, "?"

@client.on(events.NewMessage)
async def _rx(event):
    print(f"📩 Received message from chat {event.chat_id}")
    
    allowed, chan_name = await _allowed_by_name(event)
    print(f"🔍 Channel check: allowed={allowed}, name='{chan_name}'")
    
    if not allowed:
        print(f"❌ Channel '{chan_name}' not in whitelist: {settings.SRC_CHANNEL_NAMES}")
        return

    text = (event.raw_text or "").strip()
    print(f"📝 Message text: '{text[:100]}...'")
    
    if not text:
        print("❌ Empty message, skipping")
        return

    # Idempotency (chat_id + text hash)
    if not await is_new_signal(event.chat_id, text):
        print("❌ Duplicate signal detected, skipping")
        return

    sig = parse_signal(text)
    print(f"🔍 Parsed signal: {sig}")
    
    if not sig:
        print("❌ Signal parsing failed, skipping")
        return

    # Attach source channel *name* for templates
    sig["channel_name"] = chan_name
    sig["channel_id"] = int(event.chat_id)

    print(f"✅ Processing signal: {sig['symbol']} {sig['direction']} from {chan_name}")

    # The *only* pre-ACK message allowed per client spec:
    await client.send_message(event.chat_id, signal_received(sig))

    # Start the trade FSM (ACK-gated internal steps will trigger messages)
    await TradeFSM(sig).run()

async def start_telegram():
    print("🔌 Starting Telegram client...")
    print(f"📋 Whitelisted channels: {settings.SRC_CHANNEL_NAMES}")
    print(f"🔑 API ID: {settings.TELEGRAM_API_ID}")
    print(f"🔑 API Hash: {'*' * len(settings.TELEGRAM_API_HASH) if settings.TELEGRAM_API_HASH else 'NOT SET'}")
    
    try:
        print("🔄 Connecting to Telegram...")
        await client.start()
        print("✅ Telegram client started successfully!")
        print("📡 Listening for signals from whitelisted channels...")
        print("🎯 Bot is ready! Send test signals to your channels.")
        
        # Keep the bot running
        await client.run_until_disconnected()
        
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