#!/usr/bin/env python3
"""
Check current market prices for unfilled orders
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def check_current_prices():
    """Check current market prices for ARIAUSDT and PYTHUSDT"""
    try:
        from app.bybit.client import get_bybit_client
        
        print("🔍 Checking Current Market Prices...")
        print("=" * 50)
        
        client = get_bybit_client()
        
        # Check ARIAUSDT
        print("\n📊 ARIAUSDT:")
        aria_ticker = await client.get_ticker("ARIAUSDT")
        if aria_ticker and aria_ticker.get('retCode') == 0:
            aria_price = aria_ticker['result']['list'][0]['lastPrice']
            print(f"  Current Price: {aria_price}")
            print(f"  Order Price: 0.13982")
            print(f"  Difference: {float(aria_price) - 0.13982:.6f}")
            if float(aria_price) > 0.13982:
                print(f"  Status: Market above order price - orders should fill when price drops")
            else:
                print(f"  Status: Market below order price - orders should fill when price rises")
        
        # Check PYTHUSDT
        print("\n📊 PYTHUSDT:")
        pyth_ticker = await client.get_ticker("PYTHUSDT")
        if pyth_ticker and pyth_ticker.get('retCode') == 0:
            pyth_price = pyth_ticker['result']['list'][0]['lastPrice']
            print(f"  Current Price: {pyth_price}")
            print(f"  Order Price: 0.1341")
            print(f"  Difference: {float(pyth_price) - 0.1341:.6f}")
            if float(pyth_price) > 0.1341:
                print(f"  Status: Market above order price - orders should fill when price drops")
            else:
                print(f"  Status: Market below order price - orders should fill when price rises")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_current_prices())
