"""
Show Filtered Symbols

Display which symbols are available/unavailable on Bybit (useful for demo environment).

Usage:
    python scripts/show_filtered_symbols.py
    python scripts/show_filtered_symbols.py --test SAFEUSDT BTCUSDT ETHUSDT
"""

import asyncio
import sys
import argparse
from pathlib import Path
from typing import List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.symbol_filter import get_symbol_filter, is_symbol_available
from app.core.symbol_registry import get_symbol_registry
from app.core.strict_config import STRICT_CONFIG


async def show_all_symbols():
    """Show all available symbols."""
    print("\n" + "="*80)
    print("AVAILABLE SYMBOLS ON BYBIT")
    print("="*80)
    print(f"Environment: {STRICT_CONFIG.bybit_endpoint}")
    print("="*80 + "\n")
    
    # Get symbol filter
    filter_instance = get_symbol_filter()
    
    # Initialize (loads all symbols)
    print("Loading symbols from Bybit...")
    registry = get_symbol_registry()
    all_symbols = await registry.get_all_symbols()
    
    if not all_symbols:
        print("❌ No symbols found!")
        return
    
    # Sort alphabetically
    all_symbols.sort()
    
    # Group by category
    btc_symbols = [s for s in all_symbols if s.startswith('BTC')]
    eth_symbols = [s for s in all_symbols if s.startswith('ETH')]
    other_symbols = [s for s in all_symbols if not s.startswith('BTC') and not s.startswith('ETH')]
    
    print(f"\n✅ Total Available Symbols: {len(all_symbols)}\n")
    
    print(f"📊 BTC Pairs ({len(btc_symbols)}):")
    for symbol in btc_symbols[:20]:  # Show first 20
        print(f"   • {symbol}")
    if len(btc_symbols) > 20:
        print(f"   ... and {len(btc_symbols) - 20} more")
    
    print(f"\n📊 ETH Pairs ({len(eth_symbols)}):")
    for symbol in eth_symbols[:20]:
        print(f"   • {symbol}")
    if len(eth_symbols) > 20:
        print(f"   ... and {len(eth_symbols) - 20} more")
    
    print(f"\n📊 Other Pairs ({len(other_symbols)}):")
    for symbol in other_symbols[:30]:
        print(f"   • {symbol}")
    if len(other_symbols) > 30:
        print(f"   ... and {len(other_symbols) - 30} more")
    
    # Show filter stats
    stats = filter_instance.get_stats()
    print(f"\n📈 Filter Statistics:")
    print(f"   Cached symbols: {stats['available_symbols']}")
    print(f"   Last refresh: {stats['last_refresh']}")
    print(f"   Cache age: {stats['cache_age_hours']:.1f} hours" if stats['cache_age_hours'] else "   Cache age: N/A")


async def test_symbols(symbols: List[str]):
    """Test specific symbols."""
    print("\n" + "="*80)
    print("SYMBOL AVAILABILITY TEST")
    print("="*80)
    print(f"Environment: {STRICT_CONFIG.bybit_endpoint}")
    print("="*80 + "\n")
    
    print(f"Testing {len(symbols)} symbol(s)...\n")
    
    for symbol in symbols:
        # Ensure uppercase
        symbol = symbol.upper()
        
        # Test availability
        is_available = await is_symbol_available(symbol)
        
        if is_available:
            # Get details
            registry = get_symbol_registry()
            symbol_info = await registry.get_symbol_info(symbol)
            
            print(f"✅ {symbol}: AVAILABLE")
            if symbol_info:
                print(f"   Status: {symbol_info.status}")
                print(f"   Tick Size: {symbol_info.tick_size}")
                print(f"   Min Qty: {symbol_info.min_qty}")
                print(f"   Max Leverage: {symbol_info.max_leverage}x")
            print()
        else:
            print(f"❌ {symbol}: NOT AVAILABLE (will be filtered)")
            print(f"   This symbol cannot be traded on {STRICT_CONFIG.bybit_endpoint}")
            print(f"   Signals for this symbol will be automatically filtered\n")


async def show_filter_stats():
    """Show current filter statistics."""
    print("\n" + "="*80)
    print("SYMBOL FILTER STATISTICS")
    print("="*80 + "\n")
    
    filter_instance = get_symbol_filter()
    
    # Initialize if needed
    await filter_instance.is_symbol_available("BTCUSDT")  # Dummy call to init
    
    stats = filter_instance.get_stats()
    
    print(f"Filter Status:")
    print(f"  Initialized: {'✅ Yes' if stats['initialized'] else '❌ No'}")
    print(f"  Available Symbols: {stats['available_symbols']}")
    print(f"  Unavailable Symbols: {stats['unavailable_symbols']}")
    print(f"  Last Refresh: {stats['last_refresh'] if stats['last_refresh'] else 'Never'}")
    print(f"  Cache Age: {stats['cache_age_hours']:.1f} hours" if stats['cache_age_hours'] else "  Cache Age: N/A")
    
    # Show unavailable symbols if any
    unavailable = filter_instance.get_unavailable_symbols()
    if unavailable:
        print(f"\n❌ Recently Filtered Symbols ({len(unavailable)}):")
        for symbol in sorted(unavailable)[:20]:
            print(f"   • {symbol}")
        if len(unavailable) > 20:
            print(f"   ... and {len(unavailable) - 20} more")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Show available/filtered symbols on Bybit')
    parser.add_argument('--test', nargs='+', help='Test specific symbols (e.g., SAFEUSDT BTCUSDT)')
    parser.add_argument('--stats', action='store_true', help='Show filter statistics only')
    
    args = parser.parse_args()
    
    try:
        if args.stats:
            await show_filter_stats()
        elif args.test:
            await test_symbols(args.test)
        else:
            await show_all_symbols()
    
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

