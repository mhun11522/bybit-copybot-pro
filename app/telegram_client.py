from telethon import TelegramClient, events
from app import settings
from app.signals.idempotency import is_new_signal
from app.signals.normalizer import parse_signal, is_similar_signal_blocked
from app.trade.fsm import TradeFSM
import asyncio


# Create the client
client = TelegramClient(
    settings.TELEGRAM_SESSION,
    settings.TELEGRAM_API_ID,
    settings.TELEGRAM_API_HASH,
)


@client.on(events.NewMessage)
async def handler(event):
    # Intake trace
    try:
        chat = await event.get_chat()
        title = getattr(chat, "title", None) or getattr(chat, "username", None) or str(event.chat_id)
    except Exception:
        title = str(event.chat_id)
    
    if settings.TELEGRAM_DEBUG:
        print(f"📩 RX from {event.chat_id} • {title}")

    # Allow-list filter with optional debug bypass
    try:
        if not settings.ALLOWED_CHANNEL_IDS:
            if settings.TELEGRAM_DEBUG:
                print("⛔ No ALLOWED_CHANNEL_IDS configured; ignoring all messages (unless TELEGRAM_DEBUG=1)")
            if not settings.TELEGRAM_DEBUG:
                return
        if (not settings.TELEGRAM_DEBUG) and int(event.chat_id) not in settings.ALLOWED_CHANNEL_IDS:
            if settings.TELEGRAM_DEBUG:
                print(f"⛔ Chat {event.chat_id} not in allow-list; skipping (set TELEGRAM_DEBUG=1 to bypass)")
            return
        if settings.TELEGRAM_DEBUG:
            print(f"🧪 DEBUG MODE: allowed={settings.ALLOWED_CHANNEL_IDS}")
    except Exception as e:
        print("Allow-list check error:", e)
        return

    text = event.raw_text or ""
    if not text.strip():
        if settings.TELEGRAM_DEBUG:
            print("⛔ Empty message; skipping")
        return

    # Parse signal first to check for cross-group blocking
    sig = parse_signal(text)
    if not sig or not sig.get("symbol") or not sig.get("direction"):
        if settings.TELEGRAM_DEBUG:
            print("⛔ Parse failed; skipping")
        return

    # Check for cross-group signal blocking
    if await is_similar_signal_blocked(sig, int(event.chat_id)):
        if settings.TELEGRAM_DEBUG:
            print("⛔ Similar signal blocked from other channel; skipping")
        return

    # Idempotency check
    if not await is_new_signal(int(event.chat_id), text):
        if settings.TELEGRAM_DEBUG:
            print("↩️ Duplicate signal detected; skipping")
        return

    # Attach source metadata for downstream templates
    try:
        # Prefer configured mapping if available
        mapped = settings.CHANNEL_ID_TO_NAME.get(int(event.chat_id)) if hasattr(settings, "CHANNEL_ID_TO_NAME") else None
        if mapped:
            channel_name = mapped
        else:
            chat = event.chat
            channel_name = getattr(chat, "title", None) or getattr(chat, "username", None) or str(event.chat_id)
    except Exception:
        channel_name = str(event.chat_id)
    
    sig["channel_id"] = int(event.chat_id)
    sig["source"] = channel_name
    
    if settings.TELEGRAM_DEBUG:
        print(f"🚦 Starting FSM for {sig.get('symbol')} {sig.get('direction')} from {channel_name}")
    
    fsm = TradeFSM(sig)
    asyncio.create_task(fsm.run())


async def run():
    await client.start()
    print("✅ Connected to Telegram. Waiting for messages...")
    await client.run_until_disconnected()

