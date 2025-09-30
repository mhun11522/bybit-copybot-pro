import asyncio
from app.telegram_client import client
from app import settings

async def test_telegram():
    print("=== TELEGRAM CONNECTION TEST ===")
    print(f"API ID: {settings.TELEGRAM_API_ID}")
    print(f"API Hash: {settings.TELEGRAM_API_HASH[:10]}...")
    print(f"Debug Mode: {settings.TELEGRAM_DEBUG}")
    print(f"Allowed Channels: {len(settings.ALLOWED_CHANNEL_IDS)}")
    
    try:
        await client.start()
        print(f"✅ Connected: {client.is_connected()}")
        
        # Get dialogs
        dialogs = await client.get_dialogs()
        print(f"📱 Total dialogs: {len(dialogs)}")
        
        # Show first 10 dialogs
        print("\n📋 Available dialogs:")
        for i, d in enumerate(dialogs[:10]):
            print(f"  {i+1}. {d.id}: {d.title}")
        
        # Check if any of our allowed channels are in the dialogs
        dialog_ids = [d.id for d in dialogs]
        found_channels = [ch_id for ch_id in settings.ALLOWED_CHANNEL_IDS if ch_id in dialog_ids]
        print(f"\n🎯 Found {len(found_channels)} allowed channels in dialogs:")
        for ch_id in found_channels:
            dialog = next((d for d in dialogs if d.id == ch_id), None)
            if dialog:
                print(f"  ✅ {ch_id}: {dialog.title}")
        
        await client.disconnect()
        print("\n✅ Test completed successfully")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_telegram())