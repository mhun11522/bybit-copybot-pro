#!/usr/bin/env python3
"""Create a comprehensive bot status summary from database and logs."""

import sqlite3
import pandas as pd
from datetime import datetime, timezone
import pytz
import os

def create_bot_status_summary():
    """Create a comprehensive summary of bot status and activity."""
    
    db_path = "trades.sqlite"
    if not os.path.exists(db_path):
        print(f"❌ Database file {db_path} not found")
        return False
    
    print(f"📊 Creating Bot Status Summary")
    print(f"🔍 Analyzing database: {db_path}")
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        
        # Create summary data
        summary_data = []
        
        # 1. Signal Analysis
        print("\n📡 Analyzing Signal Activity...")
        signal_df = pd.read_sql_query("SELECT * FROM signal_seen ORDER BY timestamp DESC LIMIT 10", conn)
        if len(signal_df) > 0:
            print(f"  ✅ Found {len(signal_df)} recent signals")
            summary_data.append({
                "Category": "Signals",
                "Metric": "Recent Signals",
                "Value": len(signal_df),
                "Details": f"Latest: {signal_df.iloc[0]['symbol'] if 'symbol' in signal_df.columns else 'Unknown'}"
            })
        
        # 2. Trade Analysis
        print("\n💰 Analyzing Trade Activity...")
        trades_df = pd.read_sql_query("SELECT * FROM trades ORDER BY created_at DESC", conn)
        if len(trades_df) > 0:
            print(f"  ✅ Found {len(trades_df)} total trades")
            
            # Count by status
            if 'status' in trades_df.columns:
                status_counts = trades_df['status'].value_counts()
                for status, count in status_counts.items():
                    summary_data.append({
                        "Category": "Trades",
                        "Metric": f"Status: {status}",
                        "Value": count,
                        "Details": f"{count} trades in {status} state"
                    })
            
            # Count by symbol
            if 'symbol' in trades_df.columns:
                symbol_counts = trades_df['symbol'].value_counts()
                summary_data.append({
                    "Category": "Trades",
                    "Metric": "Unique Symbols",
                    "Value": len(symbol_counts),
                    "Details": f"Traded symbols: {', '.join(symbol_counts.head(5).index.tolist())}"
                })
        
        # 3. Active Trades
        print("\n🔄 Analyzing Active Trades...")
        active_df = pd.read_sql_query("SELECT * FROM active_trades", conn)
        if len(active_df) > 0:
            print(f"  ✅ Found {len(active_df)} active trades")
            summary_data.append({
                "Category": "Active Trades",
                "Metric": "Currently Active",
                "Value": len(active_df),
                "Details": f"Active trades: {', '.join(active_df['symbol'].tolist()) if 'symbol' in active_df.columns else 'Unknown'}"
            })
        else:
            print("  ℹ️  No active trades found")
            summary_data.append({
                "Category": "Active Trades",
                "Metric": "Currently Active",
                "Value": 0,
                "Details": "No active trades"
            })
        
        # 4. Signal Guard Analysis
        print("\n🛡️ Analyzing Signal Guard...")
        guard_df = pd.read_sql_query("SELECT * FROM signal_guard", conn)
        if len(guard_df) > 0:
            print(f"  ✅ Found {len(guard_df)} signal guard records")
            summary_data.append({
                "Category": "Signal Guard",
                "Metric": "Protected Signals",
                "Value": len(guard_df),
                "Details": f"Signals protected from duplication"
            })
        
        # 5. Symbol Direction Block Analysis
        print("\n🚫 Analyzing Symbol Direction Blocks...")
        block_df = pd.read_sql_query("SELECT * FROM symbol_dir_block", conn)
        if len(block_df) > 0:
            print(f"  ✅ Found {len(block_df)} symbol direction blocks")
            summary_data.append({
                "Category": "Symbol Blocks",
                "Metric": "Blocked Directions",
                "Value": len(block_df),
                "Details": f"Symbols with blocked directions"
            })
        
        # Create summary DataFrame
        summary_df = pd.DataFrame(summary_data)
        
        # Add timestamp
        tz_se = pytz.timezone("Europe/Stockholm")
        current_time = datetime.now(tz_se)
        
        # Create Excel report
        output_file = "bot_status_summary.xlsx"
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Summary sheet
            summary_df.to_excel(writer, sheet_name='Status_Summary', index=False)
            
            # Recent signals sheet
            if len(signal_df) > 0:
                signal_df.to_excel(writer, sheet_name='Recent_Signals', index=False)
            
            # Recent trades sheet
            if len(trades_df) > 0:
                trades_df.to_excel(writer, sheet_name='All_Trades', index=False)
            
            # Active trades sheet
            if len(active_df) > 0:
                active_df.to_excel(writer, sheet_name='Active_Trades', index=False)
        
        conn.close()
        
        print(f"\n🎉 Bot status summary created: {output_file}")
        
        # Print summary to console
        print(f"\n📊 BOT STATUS SUMMARY ({current_time.strftime('%Y-%m-%d %H:%M:%S')} Stockholm)")
        print("=" * 60)
        
        for category in summary_df['Category'].unique():
            print(f"\n{category}:")
            category_data = summary_df[summary_df['Category'] == category]
            for _, row in category_data.iterrows():
                print(f"  {row['Metric']}: {row['Value']} - {row['Details']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating summary: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = create_bot_status_summary()
    if success:
        print("\n✅ Bot status summary completed successfully!")
    else:
        print("\n❌ Bot status summary failed")
