#!/usr/bin/env python3
"""
Add native TP/SL to existing BIOUSDT position
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

async def add_native_tpsl():
    """Add native TP/SL to existing BIOUSDT position"""
    try:
        from app.bybit.client import get_bybit_client
        from app.core.intelligent_tpsl_fixed import set_intelligent_tpsl_fixed
        
        print("🎯 Adding Native TP/SL to BIOUSDT Position...")
        print("=" * 50)
        
        client = get_bybit_client()
        
        # Get current position
        positions_response = await client.get_positions('linear', 'BIOUSDT')
        if positions_response and positions_response.get('retCode') == 0:
            positions = positions_response.get('result', {}).get('list', [])
            for position in positions:
                size = float(position.get('size', 0))
                if size > 0:
                    print(f"Found position: {position.get('symbol')} {position.get('side')} {position.get('size')} @ {position.get('avgPrice')}")
                    
                    # Set multiple TP levels and SL using native API
                    tp_levels = [Decimal("2.0"), Decimal("3.0"), Decimal("4.0"), Decimal("5.0")]  # 2%, 3%, 4%, 5%
                    sl_percentage = Decimal("1.5")  # 1.5%
                    
                    print(f"Setting TP levels: {tp_levels}")
                    print(f"Setting SL: {sl_percentage}%")
                    
                    # Use the intelligent TP/SL handler
                    result = await set_intelligent_tpsl_fixed(
                        symbol="BIOUSDT",
                        side=position.get('side', 'Sell'),
                        position_size=Decimal(str(position.get('size', 0))),
                        entry_price=Decimal(str(position.get('avgPrice', 0))),
                        tp_levels=tp_levels,
                        sl_percentage=sl_percentage,
                        trade_id="manual_tpsl_test"
                    )
                    
                    print(f"✅ TP/SL Result: {result}")
                    return
                    
        print("❌ No active BIOUSDT position found")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(add_native_tpsl())
