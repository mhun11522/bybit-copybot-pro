import asyncio
import sys
from app.telegram_client import client
from app.signals.normalizer import parse_signal
from app.trade.fsm import TradeFSM
from app import settings

async def test_signal_detection():
    print("🧪 TESTING SIGNAL DETECTION")
    print("=" * 50)
    
    # Test signal parsing
    test_signals = [
        "🟢 LONG #BTCUSDT Entry: 50000 SL: 48000 TP: 52000 Leverage: 10x",
        "🔴 SHORT #ETHUSDT Entry: 3000 SL: 3200 TP: 2800 Leverage: 5x",
        "📈 #ADAUSDT | LONG • Entry Zone: 0.45-0.47 • SL: 0.42 • TP: 0.52",
        "🟢 Opening LONG 📈 🟢 Symbol: SUIUSDT Entry: 1.25 SL: 1.20 TP: 1.35",
        "🔴 Long CHESSUSDT Entry : 1) 0.08255 2) 0.08007 SL: 0.075 TP: 0.090"
    ]
    
    print("1. Testing Signal Parsing:")
    for i, signal_text in enumerate(test_signals, 1):
        print(f"\nTest {i}: {signal_text}")
        parsed = parse_signal(signal_text)
        if parsed:
            print(f"  ✅ Parsed: {parsed.get('symbol')} {parsed.get('direction')} {parsed.get('mode')}")
        else:
            print(f"  ❌ Failed to parse")
    
    print("\n" + "=" * 50)
    print("2. Testing Telegram Connection:")
    
    try:
        await client.start()
        print(f"  ✅ Telegram connected: {client.is_connected()}")
        
        # Get dialogs to see what channels are available
        dialogs = await client.get_dialogs()
        print(f"  📱 Available dialogs: {len(dialogs)}")
        
        # Check if any of our allowed channels are accessible
        dialog_ids = [d.id for d in dialogs]
        found_channels = [ch_id for ch_id in settings.ALLOWED_CHANNEL_IDS if ch_id in dialog_ids]
        print(f"  🎯 Found {len(found_channels)} allowed channels:")
        for ch_id in found_channels:
            dialog = next((d for d in dialogs if d.id == ch_id), None)
            if dialog:
                print(f"    ✅ {ch_id}: {dialog.title}")
        
        await client.disconnect()
        
    except Exception as e:
        print(f"  ❌ Telegram connection error: {e}")
    
    print("\n" + "=" * 50)
    print("3. Testing FSM Creation:")
    
    # Test creating a trade FSM
    test_signal = {
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "entries": [50000],
        "tps": [52000],
        "sl": 48000,
        "leverage": 10,
        "mode": "DYNAMIC",
        "raw_text": "Test signal",
        "channel_id": -1002951182684,
        "source": "TEST"
    }
    
    try:
        fsm = TradeFSM(test_signal)
        print(f"  ✅ FSM created: {fsm.trade_id}")
        print(f"  📊 Signal: {fsm.signal['symbol']} {fsm.signal['direction']}")
    except Exception as e:
        print(f"  ❌ FSM creation error: {e}")
    
    print("\n" + "=" * 50)
    print("4. Testing Debug Mode:")
    print(f"  Debug Mode: {settings.TELEGRAM_DEBUG}")
    print(f"  Allowed Channels: {len(settings.ALLOWED_CHANNEL_IDS)}")
    print(f"  Channel List: {settings.ALLOWED_CHANNEL_IDS[:3]}...")
    
    print("\n✅ Signal detection test completed!")

if __name__ == "__main__":
    asyncio.run(test_signal_detection())