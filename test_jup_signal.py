#!/usr/bin/env python3
"""
Test JUP Signal Parsing
Test the specific JUP signal format you provided
"""
from app.signals.normalizer import parse_signal

def test_jup_signal():
    print("🧪 Testing JUP Signal Parsing")
    print("=" * 50)
    
    # Your actual signal
    jup_signal = """✳ New FREE signal

💎 BUY #JUP/USD at #KRAKEN

📈 SPOT TRADE
🆔 #2882703
⏱ 30-Sep-2025 09:03:46 UTC

🛒 Entry Zone: 0.41464960 - 0.43034368
💵 Current ask: 0.42692000
🎯 Target 1: 0.44423680 (4.06%)
🎯 Target 2: 0.45195520 (5.86%)
🎯 Target 3: 0.45967360 (7.67%)
🚫 Stop loss: 0.40993280 (3.98%)
💰 Volume #JUP: 616660.249410
💰 Volume #USD: 272164.004383

⏳ SHORT/MID TERM (up to 2 weeks)
⚠️ Risk:  - Invest up to 5% of your portfolio
☯️ R/R ratio: 1.5"""
    
    print("Testing signal:")
    print(jup_signal)
    print("\n" + "=" * 50)
    print("Parsing result:")
    
    parsed = parse_signal(jup_signal)
    
    if parsed and parsed.get('symbol') and parsed.get('direction'):
        print(f"✅ SUCCESS: {parsed.get('symbol')} {parsed.get('direction')} {parsed.get('mode')}")
        if parsed.get('entries'):
            print(f"📊 Entries: {parsed.get('entries')}")
        if parsed.get('sl'):
            print(f"🛡️  SL: {parsed.get('sl')}")
        if parsed.get('tps'):
            print(f"🎯 TPs: {parsed.get('tps')}")
        if parsed.get('leverage'):
            print(f"⚡ Leverage: {parsed.get('leverage')}x")
        print(f"📈 Mode: {parsed.get('mode')}")
        print(f"🔢 Trade ID: {parsed.get('trade_id')}")
        print(f"⏰ Time: {parsed.get('time')}")
        print(f"💰 Volume: {parsed.get('volume')}")
        print(f"📊 R/R: {parsed.get('rr_ratio')}")
        print(f"⚠️  Risk: {parsed.get('risk')}")
        print(f"⏳ Duration: {parsed.get('duration')}")
    else:
        print("❌ FAILED: Could not parse signal")
        print("Raw parsed result:", parsed)
    
    print("\n" + "=" * 50)
    print("🎯 CONCLUSION:")
    if parsed and parsed.get('symbol'):
        print("   ✅ The signal CAN be parsed by the bot!")
        print("   ✅ The bot SHOULD detect this signal when connected to Telegram")
        print("   ❌ The issue is that the bot is not connected to Telegram")
    else:
        print("   ❌ The signal format is not supported")
        print("   💡 Need to improve signal parsing for this format")

if __name__ == "__main__":
    test_jup_signal()