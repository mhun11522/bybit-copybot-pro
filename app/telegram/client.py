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
    allowed, chan_name = await _allowed_by_name(event)
    if not allowed:
        return

    text = (event.raw_text or "").strip()
    if not text:
        return

    # Idempotency (chat_id + text hash)
    if not await is_new_signal(event.chat_id, text):
        return

    sig = parse_signal(text)
    if not sig:
        return

    # Attach source channel *name* for templates
    sig["channel_name"] = chan_name

    # The *only* pre-ACK message allowed per client spec:
    await client.send_message(event.chat_id, signal_received(sig))

    # Start the trade FSM (ACK-gated internal steps will trigger messages)
    await TradeFSM(sig).run()

async def start_telegram():
    await client.start()
    print("Telegram client started (listening for signals).")
    await client.run_until_disconnected()