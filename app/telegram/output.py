TARGET_CHAT_ID = None  # set to an ops/chat ID if you want duplicates there

async def send_message(text: str):
    print(text)
    # Note: TARGET_CHAT_ID functionality can be added later to avoid circular imports