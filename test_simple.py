#!/usr/bin/env python3
"""Simple signal parsing test."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_parsing():
    try:
        from app.signals.normalizer import parse_signal
        
        # Test simple signal
        signal = "BTCUSDT LONG lev=10 entries=60000,59800 sl=59000 tps=61000,62000,63000"
        result = parse_signal(signal)
        
        print("=== SIGNAL PARSING TEST ===")
        print(f"Input: {signal}")
        print(f"Result: {result}")
        
        if result:
            print("✅ PARSING SUCCESS!")
            print(f"   Symbol: {result['symbol']}")
            print(f"   Direction: {result['direction']}")
            print(f"   Entries: {result['entries']}")
            print(f"   SL: {result['sl']}")
            print(f"   TPs: {result['tps']}")
            print(f"   Leverage: {result['leverage']}")
            print(f"   Mode: {result['mode']}")
        else:
            print("❌ PARSING FAILED!")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_parsing()