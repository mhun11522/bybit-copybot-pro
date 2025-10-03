import asyncio

async def send_message(text: str, target_chat_id: int = None):
    """
    Send message to Telegram output channel.
    Uses OUTPUT_CHANNEL_ID from settings if target_chat_id not specified.
    """
    try:
        # Import here to avoid circular import
        from app.telegram.strict_client import get_strict_telegram_client
        from app.config.settings import OUTPUT_CHANNEL_ID
        
        # Get the strict client
        client = await get_strict_telegram_client()
        
        # Use OUTPUT_CHANNEL_ID as default if configured
        chat_id = target_chat_id or OUTPUT_CHANNEL_ID
        
        if chat_id and client.client.is_connected():
            await client.client.send_message(chat_id, text)
        else:
            # Fallback to printing if no target is configured or not connected
            print(f"[TELEGRAM] {text}")
    except Exception as e:
        print(f"[TELEGRAM ERROR] Failed to send message: {e}")
        print(f"[FALLBACK] {text}")