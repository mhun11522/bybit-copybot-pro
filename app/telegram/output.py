import asyncio

TARGET_CHAT_ID = None  # set to an ops/chat ID if you want duplicates there

async def send_message(text: str, target_chat_id: int = None):
    """
    Send message to Telegram. If target_chat_id is provided, send there.
    Otherwise, send to the source channel if available in context.
    """
    try:
        # Import here to avoid circular import
        from app.telegram.client import client
        
        if target_chat_id:
            await client.send_message(target_chat_id, text)
        elif TARGET_CHAT_ID:
            await client.send_message(TARGET_CHAT_ID, text)
        else:
            # Fallback to printing if no target is configured
            print(f"[TELEGRAM] {text}")
    except Exception as e:
        print(f"[TELEGRAM ERROR] Failed to send message: {e}")
        print(f"[FALLBACK] {text}")