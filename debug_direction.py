#!/usr/bin/env python3
"""
Debug Direction Extraction
"""
import re

def debug_direction(text):
    print("Debugging direction extraction:")
    print(f"Text: {text}")
    print()
    
    # Check each pattern
    print("1. Swedish formats:")
    swedish_words = ["LÅNG", "LONG", "🟢", "🔴 Long"]
    for word in swedish_words:
        if word in text:
            print(f"   Found '{word}' -> BUY")
        else:
            print(f"   '{word}' not found")
    
    print("\n2. JUP signal format:")
    if "💎 BUY" in text:
        print("   Found '💎 BUY' -> BUY")
    else:
        print("   '💎 BUY' not found")
    
    if "BUY #" in text:
        print("   Found 'BUY #' -> BUY")
    else:
        print("   'BUY #' not found")
    
    print("\n3. BUY/SELL with #:")
    if "BUY" in text and "#" in text:
        print("   Found 'BUY' and '#' -> BUY")
    else:
        print("   'BUY' and '#' not found together")
    
    print("\n4. Explicit LONG/SHORT:")
    if "LONG" in text:
        print("   Found 'LONG' -> BUY")
    else:
        print("   'LONG' not found")
    
    if "SHORT" in text:
        print("   Found 'SHORT' -> SELL")
    else:
        print("   'SHORT' not found")

if __name__ == "__main__":
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
    
    debug_direction(jup_signal)