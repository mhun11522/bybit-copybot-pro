#!/usr/bin/env python3
"""Comprehensive export of all trading data."""

import asyncio
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import pytz
from app.bybit.client import get_bybit_client
from app.core.logging import system_logger

async def comprehensive_export():
    """Export all available trading data."""
    print("📊 COMPREHENSIVE TRADING DATA EXPORT")
    print("=" * 60)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"comprehensive_trading_data_{timestamp}.xlsx"
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        
        # 1. Export bot database trades
        print("📊 Exporting bot database trades...")
        try:
            conn = sqlite3.connect('trades.sqlite')
            
            # Get all trades
            trades_df = pd.read_sql_query("SELECT * FROM trades ORDER BY created_at DESC", conn)
            if not trades_df.empty:
                # Convert timestamps
                if 'created_at' in trades_df.columns:
                    trades_df['created_at'] = pd.to_datetime(trades_df['created_at'])
                if 'closed_at' in trades_df.columns:
                    trades_df['closed_at'] = pd.to_datetime(trades_df['closed_at'])
                
                trades_df.to_excel(writer, sheet_name='Bot_Trades', index=False)
                print(f"   ✅ Bot trades: {len(trades_df)} records")
            else:
                pd.DataFrame([{"note": "No trades in bot database"}]).to_excel(writer, sheet_name='Bot_Trades', index=False)
                print("   ℹ️  No trades in bot database")
            
            # Get signal guard data
            try:
                signal_guard_df = pd.read_sql_query("SELECT * FROM signal_guard ORDER BY created_at DESC", conn)
                if not signal_guard_df.empty:
                    signal_guard_df.to_excel(writer, sheet_name='Signal_Guard', index=False)
                    print(f"   ✅ Signal guard: {len(signal_guard_df)} records")
                else:
                    pd.DataFrame([{"note": "No signal guard data"}]).to_excel(writer, sheet_name='Signal_Guard', index=False)
            except:
                pd.DataFrame([{"note": "Signal guard table not found"}]).to_excel(writer, sheet_name='Signal_Guard', index=False)
            
            # Get symbol direction blocks
            try:
                symbol_blocks_df = pd.read_sql_query("SELECT * FROM symbol_dir_block ORDER BY created_at DESC", conn)
                if not symbol_blocks_df.empty:
                    symbol_blocks_df.to_excel(writer, sheet_name='Symbol_Blocks', index=False)
                    print(f"   ✅ Symbol blocks: {len(symbol_blocks_df)} records")
                else:
                    pd.DataFrame([{"note": "No symbol blocks"}]).to_excel(writer, sheet_name='Symbol_Blocks', index=False)
            except:
                pd.DataFrame([{"note": "Symbol blocks table not found"}]).to_excel(writer, sheet_name='Symbol_Blocks', index=False)
            
            conn.close()
            
        except Exception as e:
            print(f"   ❌ Error exporting bot database: {e}")
            pd.DataFrame([{"error": f"Database export failed: {e}"}]).to_excel(writer, sheet_name='Bot_Trades', index=False)
        
        # 2. Export Bybit demo data
        print("\n📊 Exporting Bybit demo data...")
        try:
            client = get_bybit_client()
            
            # Get positions
            positions = await client.positions("linear", "")
            if positions and positions.get('retCode') == 0:
                positions_list = positions.get('result', {}).get('list', [])
                if positions_list:
                    pos_df = pd.DataFrame(positions_list)
                    # Convert timestamps
                    if 'updatedTime' in pos_df.columns:
                        pos_df['updatedTime'] = pd.to_datetime(pos_df['updatedTime'], unit='ms')
                        pos_df['updatedTime'] = pos_df['updatedTime'].dt.tz_localize('UTC').dt.tz_convert('Europe/Stockholm')
                        pos_df['updatedTime'] = pos_df['updatedTime'].dt.tz_localize(None)
                    
                    pos_df.to_excel(writer, sheet_name='Bybit_Positions', index=False)
                    print(f"   ✅ Bybit positions: {len(positions_list)} records")
                else:
                    pd.DataFrame([{"note": "No positions in demo account"}]).to_excel(writer, sheet_name='Bybit_Positions', index=False)
                    print("   ℹ️  No positions in demo account")
            else:
                pd.DataFrame([{"error": f"Failed to get positions: {positions}"}]).to_excel(writer, sheet_name='Bybit_Positions', index=False)
                print(f"   ❌ Error getting positions: {positions}")
            
            # Try to get orders using different methods
            try:
                # Try query_open method
                orders = await client.query_open("linear", "")
                if orders and orders.get('retCode') == 0:
                    orders_list = orders.get('result', {}).get('list', [])
                    if orders_list:
                        orders_df = pd.DataFrame(orders_list)
                        # Convert timestamps
                        if 'createdTime' in orders_df.columns:
                            orders_df['createdTime'] = pd.to_datetime(orders_df['createdTime'], unit='ms')
                            orders_df['createdTime'] = orders_df['createdTime'].dt.tz_localize('UTC').dt.tz_convert('Europe/Stockholm')
                            orders_df['createdTime'] = orders_df['createdTime'].dt.tz_localize(None)
                        
                        orders_df.to_excel(writer, sheet_name='Bybit_Orders', index=False)
                        print(f"   ✅ Bybit orders: {len(orders_list)} records")
                    else:
                        pd.DataFrame([{"note": "No orders in demo account"}]).to_excel(writer, sheet_name='Bybit_Orders', index=False)
                        print("   ℹ️  No orders in demo account")
                else:
                    pd.DataFrame([{"error": f"Failed to get orders: {orders}"}]).to_excel(writer, sheet_name='Bybit_Orders', index=False)
                    print(f"   ❌ Error getting orders: {orders}")
            except Exception as e:
                pd.DataFrame([{"error": f"Failed to get orders: {e}"}]).to_excel(writer, sheet_name='Bybit_Orders', index=False)
                print(f"   ❌ Error getting orders: {e}")
            
            await client.aclose()
            
        except Exception as e:
            print(f"   ❌ Error exporting Bybit data: {e}")
            pd.DataFrame([{"error": f"Bybit export failed: {e}"}]).to_excel(writer, sheet_name='Bybit_Positions', index=False)
            pd.DataFrame([{"error": f"Bybit export failed: {e}"}]).to_excel(writer, sheet_name='Bybit_Orders', index=False)
        
        # 3. Create summary sheet
        print("\n📊 Creating summary...")
        summary_data = {
            'Metric': [
                'Export Time',
                'Bot Trades Count',
                'Signal Guard Count', 
                'Symbol Blocks Count',
                'Bybit Positions Count',
                'Bybit Orders Count',
                'Status'
            ],
            'Value': [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                len(trades_df) if 'trades_df' in locals() else 0,
                len(signal_guard_df) if 'signal_guard_df' in locals() else 0,
                len(symbol_blocks_df) if 'symbol_blocks_df' in locals() else 0,
                len(positions_list) if 'positions_list' in locals() else 0,
                len(orders_list) if 'orders_list' in locals() else 0,
                'Export completed successfully'
            ]
        }
        
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        print("   ✅ Summary created")
    
    print(f"\n🎉 COMPREHENSIVE EXPORT COMPLETED: {output_file}")
    print("=" * 60)
    print("📋 EXPORT SUMMARY:")
    print(f"   • Bot database trades: {len(trades_df) if 'trades_df' in locals() else 0}")
    print(f"   • Signal guard records: {len(signal_guard_df) if 'signal_guard_df' in locals() else 0}")
    print(f"   • Symbol blocks: {len(symbol_blocks_df) if 'symbol_blocks_df' in locals() else 0}")
    print(f"   • Bybit positions: {len(positions_list) if 'positions_list' in locals() else 0}")
    print(f"   • Bybit orders: {len(orders_list) if 'orders_list' in locals() else 0}")
    print(f"\n📁 File saved as: {output_file}")

if __name__ == "__main__":
    asyncio.run(comprehensive_export())
