#!/usr/bin/env python3
"""Comprehensive test of all bot components."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all critical imports work."""
    print("=== TESTING IMPORTS ===")
    
    try:
        from app.config.settings import CATEGORY, BYBIT_RECV_WINDOW, MAX_CONCURRENT_TRADES, DEDUP_SECONDS
        print("✅ Config settings imported successfully")
        print(f"   CATEGORY: {CATEGORY}")
        print(f"   BYBIT_RECV_WINDOW: {BYBIT_RECV_WINDOW}")
        print(f"   MAX_CONCURRENT_TRADES: {MAX_CONCURRENT_TRADES}")
        print(f"   DEDUP_SECONDS: {DEDUP_SECONDS}")
    except Exception as e:
        print(f"❌ Config import failed: {e}")
        return False
    
    try:
        from app.bybit.client import BybitClient
        print("✅ Bybit client imported successfully")
    except Exception as e:
        print(f"❌ Bybit client import failed: {e}")
        return False
    
    try:
        from app.signals.normalizer import parse_signal
        print("✅ Signal normalizer imported successfully")
    except Exception as e:
        print(f"❌ Signal normalizer import failed: {e}")
        return False
    
    try:
        from app.trade.fsm import TradeFSM
        print("✅ Trade FSM imported successfully")
    except Exception as e:
        print(f"❌ Trade FSM import failed: {e}")
        return False
    
    return True

def test_signal_parsing():
    """Test signal parsing with various formats."""
    print("\n=== TESTING SIGNAL PARSING ===")
    
    from app.signals.normalizer import parse_signal
    
    test_cases = [
        # Simple format
        ("BTCUSDT LONG lev=10 entries=60000,59800 sl=59000 tps=61000,62000,63000", True),
        # JUP format
        ("✳ New FREE signal 💎 BUY #JUP/USD at #KRAKEN 📈 SPOT TRADE 🆔 #2882703 ⏱ 30-Sep-2025 09:03:46 UTC 🛒 Entry Zone: 0.41464960 - 0.43034368 💵 Current ask: 0.42692000 🎯 Target 1: 0.44423680 (4.06%) 🎯 Target 2: 0.45195520 (5.86%) 🎯 Target 3: 0.45967360 (7.67%) 🚫 Stop loss: 0.40993280 (3.98%)", True),
        # FIDDE format
        ("📍Mynt: #CATI/USDT 🟢 LÅNG entries=0.1", True),
        # Invalid format
        ("Random text without signal", False),
    ]
    
    all_passed = True
    for i, (signal, should_parse) in enumerate(test_cases, 1):
        result = parse_signal(signal)
        success = (result is not None) == should_parse
        
        if success:
            print(f"✅ Test {i}: {'PARSED' if result else 'REJECTED'} correctly")
            if result:
                print(f"   Symbol: {result['symbol']}")
                print(f"   Direction: {result['direction']}")
                print(f"   Mode: {result['mode']}")
                print(f"   Leverage: {result['leverage']}")
        else:
            print(f"❌ Test {i}: Expected {'PARSED' if should_parse else 'REJECTED'}, got {'PARSED' if result else 'REJECTED'}")
            all_passed = False
    
    return all_passed

def test_leverage_policy():
    """Test leverage policy enforcement."""
    print("\n=== TESTING LEVERAGE POLICY ===")
    
    from app.signals.normalizer import parse_signal
    
    test_cases = [
        ("BTCUSDT LONG lev=6 entries=60000", "SWING", 6),
        ("BTCUSDT LONG lev=7.5 entries=60000", "DYNAMIC", 7.5),
        ("BTCUSDT LONG lev=10 entries=60000", "FAST", 10),
        ("BTCUSDT LONG lev=7 entries=60000", None, None),  # Should be rejected (forbidden range)
        ("BTCUSDT LONG entries=60000 sl=59000", "DYNAMIC", 7.5),  # Should default to DYNAMIC x7.5 when SL present
        ("BTCUSDT LONG entries=60000", "FAST", 10),  # Should default to FAST x10 when no SL
    ]
    
    all_passed = True
    for i, (signal, expected_mode, expected_lev) in enumerate(test_cases, 1):
        result = parse_signal(signal)
        
        if expected_mode is None:
            # Should be rejected
            if result is None:
                print(f"✅ Test {i}: Correctly rejected forbidden leverage")
            else:
                print(f"❌ Test {i}: Should have been rejected, got {result}")
                all_passed = False
        else:
            # Should be parsed with specific mode/leverage
            if result and result['mode'] == expected_mode and result['leverage'] == expected_lev:
                print(f"✅ Test {i}: Correctly parsed as {expected_mode} x{expected_lev}")
            else:
                print(f"❌ Test {i}: Expected {expected_mode} x{expected_lev}, got {result}")
                all_passed = False
    
    return all_passed

def main():
    """Run all tests."""
    print("🧪 COMPREHENSIVE BOT TESTING")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_signal_parsing,
        test_leverage_policy,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"📊 RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Bot is ready to run.")
        print("\n🚀 Next steps:")
        print("1. Create .env file with your credentials")
        print("2. Run 'python -m app.main' to start the bot")
        print("3. Send test signals to your whitelisted channels")
    else:
        print("❌ Some tests failed. Please fix the issues before running the bot.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)