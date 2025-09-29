from app import settings
from app.telegram_client import client


async def send_message(text: str):
    await client.send_message(settings.TELEGRAM_OUTPUT_CHANNEL, text)

