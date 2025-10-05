#!/usr/bin/env python3
import os
import sys
import asyncio
import pandas as pd
from datetime import datetime, timedelta, timezone
import pytz

# Add the app directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.bybit.client import get_bybit_client

async def export_trades():
    """Export trades using the existing Bybit client"""
    client = get_bybit_client()
    
    # Get trades from the last 7 days
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=7)
    
    print(f"🚀 Bybit Demo Trade Export (Using Bot's Client)")
    print(f"📅 Exporting trades from {start_time} to {end_time}")
    print()
    
    # Try to get execution list for linear trades
    try:
        print("📊 Fetching linear trades...")
        response = await client._get_auth("/v5/execution/list", {
            "category": "linear",
            "startTime": str(int(start_time.timestamp() * 1000)),
            "endTime": str(int(end_time.timestamp() * 1000)),
            "limit": "1000"
        })
        
        if response.get("retCode") == 0:
            trades = response.get("result", {}).get("list", [])
            print(f"✅ Found {len(trades)} linear trades")
            
            if trades:
                # Convert to DataFrame
                df = pd.DataFrame(trades)
                
                # Add timezone conversion
                tz_se = pytz.timezone("Europe/Stockholm")
                if "execTime" in df.columns:
                    df["execTimeMs"] = pd.to_numeric(df["execTime"], errors="coerce")
                    df["execTime_UTC"] = pd.to_datetime(df["execTimeMs"], unit="ms", utc=True)
                    df["execTime_Stockholm"] = df["execTime_UTC"].dt.tz_convert(tz_se)
                
                # Convert numeric columns
                for col in ["orderPrice","orderQty","execPrice","execQty","execValue","execFee","feeRate","leavesQty"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                
                # Save to Excel
                output_file = "bybit_demo_trades_real.xlsx"
                
                with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
                    # Main trades sheet
                    df.to_excel(writer, index=False, sheet_name="Linear_Trades")
                    
                    # Summary sheet
                    summary_data = {
                        "Metric": [
                            "Total Trades",
                            "Unique Symbols", 
                            "Buy Orders",
                            "Sell Orders",
                            "Total Volume (USDT)",
                            "Total Fees (USDT)",
                            "Date Range",
                            "Export Time"
                        ],
                        "Value": [
                            len(trades),
                            df["symbol"].nunique() if "symbol" in df.columns else 0,
                            len(df[df["side"] == "Buy"]) if "side" in df.columns else 0,
                            len(df[df["side"] == "Sell"]) if "side" in df.columns else 0,
                            f"{df['execValue'].sum():.2f}" if "execValue" in df.columns else "0.00",
                            f"{df['execFee'].sum():.2f}" if "execFee" in df.columns else "0.00",
                            f"{start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}",
                            datetime.now(tz_se).strftime("%Y-%m-%d %H:%M:%S")
                        ]
                    }
                    
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, index=False, sheet_name="Summary")
                
                print(f"✅ Exported {len(trades)} trades to {output_file}")
                
                # Show summary
                print("\n📊 Trade Summary:")
                if "symbol" in df.columns:
                    symbol_counts = df["symbol"].value_counts()
                    print("Trades by Symbol:")
                    for symbol, count in symbol_counts.head(10).items():
                        print(f"  {symbol}: {count} trades")
                
                if "side" in df.columns:
                    side_counts = df["side"].value_counts()
                    print("\nTrades by Side:")
                    for side, count in side_counts.items():
                        print(f"  {side}: {count} trades")
                
                # Show recent trades
                if "execTime_Stockholm" in df.columns:
                    print("\n🕐 Most Recent Trades:")
                    recent = df.nlargest(5, "execTimeMs")
                    for _, trade in recent.iterrows():
                        symbol = trade.get("symbol", "Unknown")
                        side = trade.get("side", "Unknown")
                        qty = trade.get("execQty", 0)
                        price = trade.get("execPrice", 0)
                        time_str = trade.get("execTime_Stockholm", "Unknown")
                        print(f"  {symbol} {side} {qty} @ {price} - {time_str}")
                        
            else:
                print("⚠️  No trades found in the last 7 days")
                # Create empty file
                empty_df = pd.DataFrame({"Message": ["No trades found in the last 7 days"]})
                empty_df.to_excel("bybit_demo_trades_real.xlsx", index=False, sheet_name="No_Data")
                print("📄 Created empty Excel file: bybit_demo_trades_real.xlsx")
        else:
            print(f"❌ API Error: {response}")
            
    except Exception as e:
        print(f"❌ Error exporting trades: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(export_trades())
