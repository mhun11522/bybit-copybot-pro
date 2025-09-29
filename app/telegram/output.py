from app import settings


async def send_message(text: str):
    # Lazy import to avoid circular dependency during startup
    try:
        from app.telegram_client import client  # imported here to break cycle
    except Exception:
        client = None
    if settings.TELEGRAM_OUTPUT_CHANNEL and client is not None:
        try:
            await client.send_message(settings.TELEGRAM_OUTPUT_CHANNEL, text)
        except Exception:
            pass
    else:
        # Fallback to stdout if no channel or client not ready
        print(f"[TG OUT] {text}")

