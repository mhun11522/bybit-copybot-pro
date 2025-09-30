#!/usr/bin/env python3
"""Test signal parsing functionality."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.signals.normalizer import parse_signal

def test_signal_parsing():
    """Test various signal formats."""
    
    test_signals = [
        # JUP format
        "✳ New FREE signal 💎 BUY #JUP/USD at #KRAKEN 📈 SPOT TRADE 🆔 #2882703 ⏱ 30-Sep-2025 09:03:46 UTC 🛒 Entry Zone: 0.41464960 - 0.43034368 💵 Current ask: 0.42692000 🎯 Target 1: 0.44423680 (4.06%) 🎯 Target 2: 0.45195520 (5.86%) 🎯 Target 3: 0.45967360 (7.67%) 🚫 Stop loss: 0.40993280 (3.98%) 💰 Volume #JUP: 616660.249410 💰 Volume #USD: 272164.004383 ⏳ SHORT/MID TERM (up to 2 weeks) ⚠️ Risk: - Invest up to 5% of your portfolio ☯️ R/R ratio: 1.5",
        
        # Simple format
        "BTCUSDT LONG lev=10 entries=60000,59800 sl=59000 tps=61000,62000,63000",
        
        # FIDDE format
        "📍Mynt: #CATI/USDT 🟢 LÅNG",
        
        # Lux Leak format
        "🔴 Long CHESSUSDT Entry : 1) 0.08255",
        
        # Basic format
        "ETHUSDT BUY entries=3000 sl=2900 tps=3100,3200",
    ]
    
    print("🧪 Testing Signal Parsing")
    print("=" * 50)
    
    for i, signal in enumerate(test_signals, 1):
        print(f"\n📝 Test {i}: {signal[:50]}...")
        result = parse_signal(signal)
        
        if result:
            print(f"✅ PARSED SUCCESSFULLY:")
            print(f"   Symbol: {result['symbol']}")
            print(f"   Direction: {result['direction']}")
            print(f"   Entries: {result['entries']}")
            print(f"   SL: {result['sl']}")
            print(f"   TPs: {result['tps']}")
            print(f"   Leverage: {result['leverage']}")
            print(f"   Mode: {result['mode']}")
        else:
            print(f"❌ PARSING FAILED")
    
    print("\n" + "=" * 50)
    print("✅ Signal parsing test completed!")

if __name__ == "__main__":
    test_signal_parsing()