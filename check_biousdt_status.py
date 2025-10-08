#!/usr/bin/env python3
"""
Check BIOUSDT order and position status
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def check_biousdt_status():
    """Check BIOUSDT orders and positions"""
    try:
        from app.bybit.client import get_bybit_client
        
        client = get_bybit_client()
        
        print("🔍 Checking BIOUSDT Status...")
        print("=" * 50)
        
        # Check open orders
        print("\n📋 OPEN ORDERS:")
        orders_response = await client.query_open('linear', 'BIOUSDT')
        if orders_response and orders_response.get('retCode') == 0:
            orders = orders_response.get('result', {}).get('list', [])
            if orders:
                for order in orders:
                    print(f"  Order ID: {order.get('orderId')}")
                    print(f"  Symbol: {order.get('symbol')}")
                    print(f"  Side: {order.get('side')}")
                    print(f"  Price: {order.get('price')}")
                    print(f"  Qty: {order.get('qty')}")
                    print(f"  Filled: {order.get('cumExecQty')}/{order.get('qty')}")
                    print(f"  Status: {order.get('orderStatus')}")
                    print(f"  Time: {order.get('createdTime')}")
                    print("  " + "-" * 30)
            else:
                print("  No open orders found")
        else:
            print(f"  Error getting orders: {orders_response}")
        
        # Check positions
        print("\n📊 POSITIONS:")
        positions_response = await client.get_positions('linear', 'BIOUSDT')
        if positions_response and positions_response.get('retCode') == 0:
            positions = positions_response.get('result', {}).get('list', [])
            if positions:
                for position in positions:
                    size = float(position.get('size', 0))
                    if size > 0:
                        print(f"  Symbol: {position.get('symbol')}")
                        print(f"  Side: {position.get('side')}")
                        print(f"  Size: {position.get('size')}")
                        print(f"  Avg Price: {position.get('avgPrice')}")
                        print(f"  Unrealized PnL: {position.get('unrealisedPnl')}")
                        print(f"  Position Value: {position.get('positionValue')}")
                        print("  " + "-" * 30)
            else:
                print("  No active positions found")
        else:
            print(f"  Error getting positions: {positions_response}")
        
        # Check TP/SL orders
        print("\n🎯 TP/SL ORDERS:")
        tpsl_response = await client.query_open('linear', 'BIOUSDT')
        if tpsl_response and tpsl_response.get('retCode') == 0:
            tpsl_orders = tpsl_response.get('result', {}).get('list', [])
            tpsl_count = 0
            for order in tpsl_orders:
                if order.get('orderType') == 'Stop' or 'tp' in order.get('orderLinkId', '').lower() or 'sl' in order.get('orderLinkId', '').lower():
                    tpsl_count += 1
                    print(f"  TP/SL Order ID: {order.get('orderId')}")
                    print(f"  Type: {order.get('orderType')}")
                    print(f"  Trigger Price: {order.get('triggerPrice')}")
                    print(f"  Qty: {order.get('qty')}")
                    print(f"  Status: {order.get('orderStatus')}")
                    print("  " + "-" * 30)
            if tpsl_count == 0:
                print("  No TP/SL orders found")
        else:
            print(f"  Error getting TP/SL orders: {tpsl_response}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_biousdt_status())
