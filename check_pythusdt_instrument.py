#!/usr/bin/env python3
"""
Check PYTHUSDT instrument info to understand qty requirements
"""
import asyncio
import sys
import os
from dotenv import load_dotenv
from decimal import Decimal

# Load environment variables
load_dotenv()

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def check_pythusdt_instrument():
    """Check PYTHUSDT instrument info"""
    try:
        from app.bybit.client import get_bybit_client
        
        print("🔍 Checking PYTHUSDT Instrument Info...")
        print("=" * 50)
        
        client = get_bybit_client()
        
        # Get instrument info
        instrument_info = await client.get_instrument_info("PYTHUSDT", "linear")
        if instrument_info and instrument_info.get('retCode') == 0:
            result = instrument_info.get('result', {})
            if 'list' in result and result['list']:
                info = result['list'][0]
                print(f"Symbol: {info.get('symbol')}")
                print(f"Min Order Qty: {info.get('lotSizeFilter', {}).get('minOrderQty')}")
                print(f"Max Order Qty: {info.get('lotSizeFilter', {}).get('maxOrderQty')}")
                print(f"Qty Step: {info.get('lotSizeFilter', {}).get('qtyStep')}")
                print(f"Min Notional: {info.get('priceFilter', {}).get('minPrice')}")
                print(f"Max Notional: {info.get('priceFilter', {}).get('maxPrice')}")
                print(f"Tick Size: {info.get('priceFilter', {}).get('tickSize')}")
                
                # Calculate TP quantities
                position_size = Decimal("12626")
                tp_portion = position_size / 4  # 4 TP levels
                print(f"\nPosition Size: {position_size}")
                print(f"TP Portion (per level): {tp_portion}")
                print(f"TP Portion (rounded): {tp_portion.quantize(Decimal('1'))}")
                
                # Check if TP portion meets minimum
                min_qty = Decimal(str(info.get('lotSizeFilter', {}).get('minOrderQty', '1')))
                print(f"Min Qty Required: {min_qty}")
                print(f"TP Portion >= Min Qty: {tp_portion >= min_qty}")
                
        else:
            print(f"Error getting instrument info: {instrument_info}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_pythusdt_instrument())
