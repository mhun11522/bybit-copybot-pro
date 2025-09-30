#!/usr/bin/env python3
"""
Test Telegram Connection
Simple test to verify Telegram connection works
"""
import asyncio
import sys
from telethon import TelegramClient

if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass

async def test_connection():
    print("🔌 Testing Telegram Connection...")
    
    # Use the same credentials
    api_id = 27590479
    api_hash = "6e60321cbb996b499b6a370af62342de"
    session_name = "test_session"
    
    try:
        client = TelegramClient(session_name, api_id, api_hash)
        
        print("⏰ Starting connection with 10 second timeout...")
        await asyncio.wait_for(client.start(), timeout=10.0)
        
        print("✅ Connected successfully!")
        print(f"   Connected: {client.is_connected()}")
        
        # Get some basic info
        me = await client.get_me()
        print(f"   User: {me.first_name} (@{me.username})")
        
        # Get dialogs count
        dialogs = await client.get_dialogs()
        print(f"   Dialogs: {len(dialogs)}")
        
        await client.disconnect()
        print("✅ Disconnected successfully!")
        
        return True
        
    except asyncio.TimeoutError:
        print("⏰ Connection timeout!")
        return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_connection())
    if success:
        print("\n🎉 Telegram connection test PASSED!")
    else:
        print("\n💥 Telegram connection test FAILED!")