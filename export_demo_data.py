#!/usr/bin/env python3
"""Export demo trading data using bot's working authentication."""

import asyncio
import pandas as pd
from datetime import datetime, timedelta
import pytz
from app.bybit.client import get_bybit_client
from app.core.logging import system_logger

async def export_demo_data():
    """Export demo trading data to Excel."""
    print("📊 EXPORTING DEMO TRADING DATA")
    print("=" * 50)
    
    client = get_bybit_client()
    
    try:
        # Get current positions
        print("📊 Fetching current positions...")
        positions = await client.positions("linear", "")
        
        all_data = {}
        
        if positions and positions.get('retCode') == 0:
            positions_list = positions.get('result', {}).get('list', [])
            print(f"✅ Found {len(positions_list)} positions")
            
            if positions_list:
                df_positions = pd.DataFrame(positions_list)
                
                # Convert timestamps
                if 'updatedTime' in df_positions.columns:
                    df_positions['updatedTime'] = pd.to_datetime(df_positions['updatedTime'], unit='ms')
                    df_positions['updatedTime'] = df_positions['updatedTime'].dt.tz_localize('UTC').dt.tz_convert('Europe/Stockholm')
                    df_positions['updatedTime'] = df_positions['updatedTime'].dt.tz_localize(None)
                
                all_data['Positions'] = df_positions
                
                # Show summary
                print(f"\n📈 POSITION SUMMARY:")
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
                print(f"   Total PnL: ${total_pnl:.2f}")
            else:
                print("ℹ️  No positions found")
                all_data['Positions'] = pd.DataFrame([{"note": "No positions found"}])
        else:
            print(f"❌ Error getting positions: {positions}")
            all_data['Positions'] = pd.DataFrame([{"error": "Failed to fetch positions"}])
        
        # Try to get order history
        print("\n📊 Fetching order history...")
        try:
            # Use a different method to get orders
            orders = await client.get_order_history("linear", "")
            
            if orders and orders.get('retCode') == 0:
                orders_list = orders.get('result', {}).get('list', [])
                print(f"✅ Found {len(orders_list)} orders")
                
                if orders_list:
                    df_orders = pd.DataFrame(orders_list)
                    
                    # Convert timestamps
                    if 'createdTime' in df_orders.columns:
                        df_orders['createdTime'] = pd.to_datetime(df_orders['createdTime'], unit='ms')
                        df_orders['createdTime'] = df_orders['createdTime'].dt.tz_localize('UTC').dt.tz_convert('Europe/Stockholm')
                        df_orders['createdTime'] = df_orders['createdTime'].dt.tz_localize(None)
                    
                    all_data['Orders'] = df_orders
                    
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
                    all_data['Orders'] = pd.DataFrame([{"note": "No orders found"}])
            else:
                print(f"❌ Error getting orders: {orders}")
                all_data['Orders'] = pd.DataFrame([{"error": "Failed to fetch orders"}])
        except Exception as e:
            print(f"❌ Error getting orders: {e}")
            all_data['Orders'] = pd.DataFrame([{"error": f"Failed to fetch orders: {e}"}])
        
        # Export to Excel
        output_file = f"bybit_demo_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        print(f"\n📁 Exporting to: {output_file}")
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            for sheet_name, df in all_data.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                print(f"   ✅ {sheet_name}: {len(df)} rows")
        
        print(f"\n🎉 Export completed: {output_file}")
        
        # Also create a summary report
        summary_data = {
            'Metric': ['Export Time', 'Positions Found', 'Orders Found', 'Total PnL'],
            'Value': [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                len(all_data.get('Positions', pd.DataFrame())),
                len(all_data.get('Orders', pd.DataFrame())),
                f"${total_pnl:.2f}" if 'total_pnl' in locals() else "N/A"
            ]
        }
        
        summary_df = pd.DataFrame(summary_data)
        with pd.ExcelWriter(f"export_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", engine='openpyxl') as writer:
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        print(f"📊 Summary report: export_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        system_logger.error(f"Error exporting demo data: {e}", exc_info=True)
    finally:
        await client.aclose()

if __name__ == "__main__":
    asyncio.run(export_demo_data())
