#!/usr/bin/env python3
"""
Test Telegram Connection Independently
This script tests Telegram connection without the main bot
"""
import asyncio
import sys
from telethon import TelegramClient
from app import settings

if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass

async def test_telegram():
    print("🔌 Testing Telegram Connection...")
    
    try:
        # Create client
        client = TelegramClient(
            settings.TELEGRAM_SESSION,
            settings.TELEGRAM_API_ID,
            settings.TELEGRAM_API_HASH,
        )
        
        print("   Connecting...")
        await client.connect()
        
        if not await client.is_user_authorized():
            print("❌ User not authorized. Please run telegram_auth.py first.")
            return False
        
        print("✅ Connected successfully!")
        print(f"   Connected: {client.is_connected()}")
        
        # Get user info
        me = await client.get_me()
        print(f"   User: {me.first_name} (@{me.username})")
        
        # Get dialogs
        dialogs = await client.get_dialogs()
        print(f"   Dialogs: {len(dialogs)}")
        
        # Check allowed channels
        dialog_ids = [d.id for d in dialogs]
        found_channels = [ch_id for ch_id in settings.ALLOWED_CHANNEL_IDS if ch_id in dialog_ids]
        print(f"   Allowed channels found: {len(found_channels)}/{len(settings.ALLOWED_CHANNEL_IDS)}")
        
        await client.disconnect()
        print("✅ Disconnected successfully!")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_telegram())
    if success:
        print("\n🎉 Telegram connection test PASSED!")
        print("   The bot should now be able to connect to Telegram.")
    else:
        print("\n💥 Telegram connection test FAILED!")
        print("   Please run 'python telegram_auth.py' to authenticate first.")