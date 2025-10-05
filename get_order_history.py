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

async def get_order_history():
    """Get order history using the bot's working methods"""
    client = get_bybit_client()
    
    print(f"🚀 Getting Order History from Bybit API")
    print(f"🔑 Using bot's working authentication methods")
    print()
    
    try:
        # Try to get order history
        print("📊 Fetching recent order history...")
        orders_response = await client._get_auth("/v5/order/history", {
            "category": "linear",
            "limit": "100"
        })
        
        if orders_response.get("retCode") == 0:
            orders = orders_response.get("result", {}).get("list", [])
            print(f"✅ Found {len(orders)} recent orders")
            
            if orders:
                # Convert to DataFrame
                df = pd.DataFrame(orders)
                
                # Add timezone conversion (convert to naive datetime for Excel)
                tz_se = pytz.timezone("Europe/Stockholm")
                if "createdTime" in df.columns:
                    df["createdTimeMs"] = pd.to_numeric(df["createdTime"], errors="coerce")
                    df["createdTime_UTC"] = pd.to_datetime(df["createdTimeMs"], unit="ms", utc=True).dt.tz_localize(None)
                    df["createdTime_Stockholm"] = pd.to_datetime(df["createdTimeMs"], unit="ms", utc=True).dt.tz_convert(tz_se).dt.tz_localize(None)
                
                # Convert numeric columns
                for col in ["qty","price","avgPrice","cumExecQty","cumExecValue","cumExecFee"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                
                # Save to Excel
                output_file = "bybit_order_history.xlsx"
                
                with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
                    # Main orders sheet
                    df.to_excel(writer, index=False, sheet_name="Order_History")
                    
                    # Summary sheet
                    summary_data = {
                        "Metric": [
                            "Total Orders",
                            "Filled Orders", 
                            "Cancelled Orders",
                            "Total Volume",
                            "Total Fees",
                            "Export Time"
                        ],
                        "Value": [
                            len(orders),
                            len(df[df["orderStatus"] == "Filled"]) if "orderStatus" in df.columns else 0,
                            len(df[df["orderStatus"] == "Cancelled"]) if "orderStatus" in df.columns else 0,
                            f"{df['cumExecValue'].sum():.2f}" if "cumExecValue" in df.columns else "0.00",
                            f"{df['cumExecFee'].sum():.2f}" if "cumExecFee" in df.columns else "0.00",
                            datetime.now(tz_se).strftime("%Y-%m-%d %H:%M:%S")
                        ]
                    }
                    
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, index=False, sheet_name="Summary")
                
                print(f"✅ Exported {len(orders)} orders to {output_file}")
                
                # Show recent orders
                print("\n📊 Recent Orders:")
                if "createdTime_Stockholm" in df.columns:
                    recent = df.nlargest(10, "createdTimeMs")
                    for _, order in recent.iterrows():
                        symbol = order.get("symbol", "Unknown")
                        side = order.get("side", "Unknown")
                        qty = order.get("qty", 0)
                        price = order.get("price", 0)
                        status = order.get("orderStatus", "Unknown")
                        time_str = order.get("createdTime_Stockholm", "Unknown")
                        print(f"  {symbol} {side} {qty} @ {price} ({status}) - {time_str}")
                
                return True
            else:
                print("⚠️  No recent orders found")
                return False
        else:
            print(f"❌ API Error getting orders: {orders_response}")
            return False
            
    except Exception as e:
        print(f"❌ Error getting order history: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(get_order_history())
    if success:
        print("\n🎉 Successfully downloaded order history from Bybit API!")
    else:
        print("\n❌ Failed to get order history from API")
