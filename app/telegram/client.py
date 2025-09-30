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
    Enforce allow-list by *channel name* (not ID), as per client requirement.
    Returns (allowed, resolved_name).
    """
    if not settings.SRC_CHANNEL_NAMES:
        # If empty, allow all (useful for debugging)
        ent = await event.get_chat()
        name = getattr(ent, "title", "") or getattr(ent, "username", "") or str(event.chat_id)
        return True, name

    try:
        ent = await event.get_chat()
        name = getattr(ent, "title", "") or getattr(ent, "username", "") or str(event.chat_id)
        return (name in settings.SRC_CHANNEL_NAMES), name
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
        await client.start()
        print("✅ Telegram client started successfully!")
        print("📡 Listening for signals from whitelisted channels...")
        await client.run_until_disconnected()
    except Exception as e:
        print(f"❌ Telegram connection failed: {e}")
        print("💡 Make sure to:")
        print("   1. Create .env file with correct credentials")
        print("   2. Run 'python telegram_auth.py' for first-time setup")
        raise