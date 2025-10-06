#!/usr/bin/env python3
"""Improved export script with better error handling."""

import pandas as pd
import sqlite3
from datetime import datetime
import asyncio
from app.bybit.client import get_bybit_client

async def improved_export():
    """Export with improved error handling."""
    print("📊 IMPROVED DATA EXPORT")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"improved_export_{timestamp}.xlsx"
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Export bot database
        try:
            conn = sqlite3.connect('trades.sqlite')
            
            # Trades
            trades_df = pd.read_sql_query("SELECT * FROM trades ORDER BY created_at DESC", conn)
            trades_df.to_excel(writer, sheet_name='Trades', index=False)
            
            # Signal guard
            try:
                signal_guard_df = pd.read_sql_query("SELECT * FROM signal_guard ORDER BY created_at DESC", conn)
                signal_guard_df.to_excel(writer, sheet_name='Signal_Guard', index=False)
            except:
                pd.DataFrame([{"note": "Signal guard table not available"}]).to_excel(writer, sheet_name='Signal_Guard', index=False)
            
            conn.close()
            
        except Exception as e:
            pd.DataFrame([{"error": f"Database export failed: {e}"}]).to_excel(writer, sheet_name='Trades', index=False)
        
        # Export Bybit data with better error handling
        try:
            client = get_bybit_client()
            
            # Positions
            positions = await client.positions("linear", "")
            if positions and positions.get('retCode') == 0:
                positions_list = positions.get('result', {}).get('list', [])
                if positions_list:
                    pos_df = pd.DataFrame(positions_list)
                    pos_df.to_excel(writer, sheet_name='Bybit_Positions', index=False)
                else:
                    pd.DataFrame([{"note": "No positions found"}]).to_excel(writer, sheet_name='Bybit_Positions', index=False)
            else:
                pd.DataFrame([{"note": "API error - no positions data"}]).to_excel(writer, sheet_name='Bybit_Positions', index=False)
            
            await client.aclose()
            
        except Exception as e:
            pd.DataFrame([{"error": f"Bybit export failed: {e}"}]).to_excel(writer, sheet_name='Bybit_Positions', index=False)
    
    print(f"✅ Export completed: {output_file}")

if __name__ == "__main__":
    asyncio.run(improved_export())
