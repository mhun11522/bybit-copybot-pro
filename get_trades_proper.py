#!/usr/bin/env python3
import os
import sys
import asyncio
import pandas as pd
from datetime import datetime, timedelta, timezone
import pytz
from urllib.parse import urlencode

# Add the app directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.bybit.client import get_bybit_client, _headers_get

async def get_trade_executions():
    """Get actual trade execution history using proper GET request authentication"""
    client = get_bybit_client()
    
    # Get trades from the last 7 days
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=7)
    
    print(f"🚀 Getting REAL Trade Executions from Bybit API")
    print(f"📅 Fetching executions from {start_time} to {end_time}")
    print(f"🔑 Using proper GET request authentication")
    print()
    
    try:
        # Prepare parameters
        params = {
            "category": "linear",
            "startTime": str(int(start_time.timestamp() * 1000)),
            "endTime": str(int(end_time.timestamp() * 1000)),
            "limit": "1000"
        }
        
        # Create query string
        query_string = urlencode(sorted(params.items()))
        print(f"Query string: {query_string}")
        
        # Get headers using the bot's _headers_get function
        headers = _headers_get(query_string)
        print(f"Using timestamp: {headers['X-BAPI-TIMESTAMP']}")
        
        # Make the request
        url = f"{client.http.base_url}/v5/execution/list"
        print(f"Request URL: {url}")
        
        response = await client.http.get(url, params=params, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        print(f"API Response Code: {data.get('retCode')}")
        print(f"API Response Message: {data.get('retMsg', 'OK')}")
        
        if data.get("retCode") == 0:
            result = data.get("result", {})
            trades = result.get("list", [])
            print(f"✅ Found {len(trades)} linear trade executions")
            
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
                output_file = "bybit_REAL_executions.xlsx"
                
                with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
                    # Main executions sheet
                    df.to_excel(writer, index=False, sheet_name="Executions")
                    
                    # Summary sheet
                    summary_data = {
                        "Metric": [
                            "Total Executions",
                            "Unique Symbols", 
                            "Buy Executions",
                            "Sell Executions",
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
                
                print(f"✅ Exported {len(trades)} real trade executions to {output_file}")
                
                # Show summary
                print("\n📊 Real Trade Execution Summary:")
                if "symbol" in df.columns:
                    symbol_counts = df["symbol"].value_counts()
                    print("Executions by Symbol:")
                    for symbol, count in symbol_counts.head(10).items():
                        print(f"  {symbol}: {count} executions")
                
                if "side" in df.columns:
                    side_counts = df["side"].value_counts()
                    print("\nExecutions by Side:")
                    for side, count in side_counts.items():
                        print(f"  {side}: {count} executions")
                
                # Show recent executions
                if "execTime_Stockholm" in df.columns:
                    print("\n🕐 Most Recent Executions:")
                    recent = df.nlargest(5, "execTimeMs")
                    for _, trade in recent.iterrows():
                        symbol = trade.get("symbol", "Unknown")
                        side = trade.get("side", "Unknown")
                        qty = trade.get("execQty", 0)
                        price = trade.get("execPrice", 0)
                        time_str = trade.get("execTime_Stockholm", "Unknown")
                        print(f"  {symbol} {side} {qty} @ {price} - {time_str}")
                        
                return True
                        
            else:
                print("⚠️  No trade executions found in the last 7 days")
                return False
        else:
            print(f"❌ API Error: {data}")
            return False
            
    except Exception as e:
        print(f"❌ Error getting trade executions: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(get_trade_executions())
    if success:
        print("\n🎉 Successfully downloaded real trade executions from Bybit API!")
    else:
        print("\n❌ Failed to get trade executions from API")
