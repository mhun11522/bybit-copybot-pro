from telethon import TelegramClient, events
from app import settings
from app.signals.idempotency import is_new_signal
from app.signals.normalizer import parse_signal
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
    # Allow-list filter: if not configured, ignore all intake to be safe
    try:
        if not settings.ALLOWED_CHANNEL_IDS:
            # No allow-list configured; ignore all messages
            return
        if int(event.chat_id) not in settings.ALLOWED_CHANNEL_IDS:
            return
    except Exception:
        return

    text = event.raw_text or ""
    if not text.strip():
        return

    # Idempotency
    if not await is_new_signal(int(event.chat_id), text):
        return

    # Parse → FSM
    sig = parse_signal(text)
    if not sig or not sig.get("symbol") or not sig.get("direction"):
        return
    fsm = TradeFSM(sig)
    asyncio.create_task(fsm.run())


async def run():
    await client.start()
    print("✅ Connected to Telegram. Waiting for messages...")
    await client.run_until_disconnected()

