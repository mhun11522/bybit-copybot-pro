"""Test signal parser with real signal formats."""

import asyncio
from app.signals.strict_parser import get_strict_parser

async def test_signal_parsing():
    """Test signal parsing with real signal formats."""
    parser = get_strict_parser()
    
    # Test the DRIFT signal from the logs
    drift_signal = """NEW FUTURES SIGNAL 📣

#DRIFT  |  LONG

ENTRY🚀: 0.7354

LEVERAGE ⬆️: 50X

TAKE PROFITS📌
 
👀0.7384
👀0.7414"""

    print("🧪 Testing DRIFT Signal Parsing...")
    print("=" * 50)
    print("Signal:")
    print(drift_signal)
    print("\nParsing result:")
    
    result = parser.parse_signal(drift_signal, "MY_TEST_CHANNEL")
    
    if result:
        print("✅ Signal parsed successfully!")
        print(f"  Symbol: {result['symbol']}")
        print(f"  Direction: {result['direction']}")
        print(f"  Entries: {result['entries']}")
        print(f"  TPs: {result.get('tps', [])}")
        print(f"  SL: {result.get('sl', 'None')}")
        print(f"  Leverage: {result['leverage']}")
        print(f"  Mode: {result['mode']}")
        print(f"  Synthesized SL: {result.get('synthesized_sl', False)}")
        print(f"  Synthesized Entry2: {result.get('synthesized_entry2', False)}")
    else:
        print("❌ Signal parsing failed")
    
    print("\n" + "=" * 50)
    
    # Test other signal formats
    test_signals = [
        {
            'name': 'BTCUSDT Standard',
            'signal': 'BTCUSDT LONG Entry: 45000 Target: 50000 SL: 42000 Leverage: 10x',
            'expected_symbol': 'BTCUSDT'
        },
        {
            'name': 'ETHUSDT SWING',
            'signal': 'ETHUSDT SWING Entry: 3000 Target: 3500 SL: 2800',
            'expected_symbol': 'ETHUSDT'
        },
        {
            'name': 'ADAUSDT Missing SL',
            'signal': 'ADAUSDT LONG Entry: 0.5 Target: 0.6',
            'expected_symbol': 'ADAUSDT'
        }
    ]
    
    for test in test_signals:
        print(f"\n🧪 Testing {test['name']}...")
        result = parser.parse_signal(test['signal'], "MY_TEST_CHANNEL")
        
        if result:
            print(f"  ✅ Parsed: {result['symbol']} {result['direction']}")
            print(f"  ✅ Mode: {result['mode']}, Leverage: {result['leverage']}x")
        else:
            print(f"  ❌ Failed to parse")

if __name__ == "__main__":
    asyncio.run(test_signal_parsing())