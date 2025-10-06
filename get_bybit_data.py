#!/usr/bin/env python3
"""Get Bybit data using the bot's working authentication."""

import asyncio
import pandas as pd
from datetime import datetime, timedelta
import pytz
from app.bybit.client import get_bybit_client
from app.core.logging import system_logger

async def get_bybit_data():
    """Get order history and positions from Bybit using bot's working auth."""
    print("🔧 BybitClient singleton created")
    client = get_bybit_client()
    
    print("🚀 Getting Bybit Data")
    print("🔑 Using bot's working authentication methods")
    
    try:
        # Try to get positions using the bot's working method
        print("\n📊 Fetching current positions...")
        positions = await client.positions("linear", "")
        
        if positions and positions.get('retCode') == 0:
            positions_list = positions.get('result', {}).get('list', [])
            print(f"✅ Found {len(positions_list)} positions")
            
            if positions_list:
                # Create DataFrame
                df_positions = pd.DataFrame(positions_list)
                
                # Convert timestamps to readable format
                if 'updatedTime' in df_positions.columns:
                    df_positions['updatedTime'] = pd.to_datetime(df_positions['updatedTime'], unit='ms')
                    df_positions['updatedTime'] = df_positions['updatedTime'].dt.tz_localize('UTC').dt.tz_convert('Europe/Stockholm')
                    df_positions['updatedTime'] = df_positions['updatedTime'].dt.tz_localize(None)  # Remove timezone for Excel
                
                # Export to Excel
                with pd.ExcelWriter('bybit_positions_live.xlsx', engine='openpyxl') as writer:
                    df_positions.to_excel(writer, sheet_name='Positions', index=False)
                
                print(f"✅ Positions exported to bybit_positions_live.xlsx")
                
                # Show summary
                print(f"\n📈 POSITION SUMMARY:")
                print(f"   Total positions: {len(positions_list)}")
                
                total_notional = 0
                total_pnl = 0
                for pos in positions_list:
                    size = float(pos.get('size', 0))
                    mark_price = float(pos.get('markPrice', 0))
                    pnl = float(pos.get('unrealisedPnl', 0))
                    symbol = pos.get('symbol', 'Unknown')
                    
                    notional = size * mark_price
                    total_notional += notional
                    total_pnl += pnl
                    
                    print(f"   {symbol}: {size:,.0f} @ {mark_price} = ${notional:,.2f} (PnL: ${pnl:.2f})")
                
                print(f"\n   Total Notional: ${total_notional:,.2f}")
                print(f"   Total PnL: ${total_pnl:,.2f}")
            else:
                print("ℹ️  No positions found")
        else:
            print(f"❌ Error getting positions: {positions}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        system_logger.error(f"Error getting Bybit data: {e}", exc_info=True)
    
    try:
        # Try to get orders using the bot's working method
        print("\n📊 Fetching recent orders...")
        orders = await client.query_open("linear", "")
        
        if orders and orders.get('retCode') == 0:
            orders_list = orders.get('result', {}).get('list', [])
            print(f"✅ Found {len(orders_list)} orders")
            
            if orders_list:
                # Create DataFrame
                df_orders = pd.DataFrame(orders_list)
                
                # Convert timestamps to readable format
                if 'createdTime' in df_orders.columns:
                    df_orders['createdTime'] = pd.to_datetime(df_orders['createdTime'], unit='ms')
                    df_orders['createdTime'] = df_orders['createdTime'].dt.tz_localize('UTC').dt.tz_convert('Europe/Stockholm')
                    df_orders['createdTime'] = df_orders['createdTime'].dt.tz_localize(None)  # Remove timezone for Excel
                
                # Export to Excel
                with pd.ExcelWriter('bybit_orders_live.xlsx', engine='openpyxl') as writer:
                    df_orders.to_excel(writer, sheet_name='Orders', index=False)
                
                print(f"✅ Orders exported to bybit_orders_live.xlsx")
                
                # Show summary
                print(f"\n📋 ORDER SUMMARY:")
                print(f"   Total orders: {len(orders_list)}")
                
                # Group by status
                status_counts = {}
                for order in orders_list:
                    status = order.get('orderStatus', 'Unknown')
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                for status, count in status_counts.items():
                    print(f"   {status}: {count}")
                    
            else:
                print("ℹ️  No orders found")
        else:
            print(f"❌ Error getting orders: {orders}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        system_logger.error(f"Error getting orders: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(get_bybit_data())
