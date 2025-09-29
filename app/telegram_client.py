from telethon import TelegramClient, events
from app import settings


# Create the client
client = TelegramClient(
    settings.TELEGRAM_SESSION,
    settings.TELEGRAM_API_ID,
    settings.TELEGRAM_API_HASH,
)


@client.on(events.NewMessage)
async def handler(event):
    print(f"📩 New message from {event.chat_id}: {event.raw_text[:80]}")


async def run():
    await client.start()
    print("✅ Connected to Telegram. Waiting for messages...")
    await client.run_until_disconnected()

