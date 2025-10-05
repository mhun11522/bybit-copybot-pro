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

async def get_bot_trade_data():
    """Get trade data using the bot's working methods"""
    client = get_bybit_client()
    
    print(f"🚀 Getting Bot Trade Data from Bybit API")
    print(f"🔑 Using bot's working authentication methods")
    print()
    
    try:
        # Try to get current positions first
        print("📊 Fetching current positions...")
        positions_response = await client._get_auth("/v5/position/list", {
            "category": "linear",
            "settleCoin": "USDT"
        })
        
        if positions_response.get("retCode") == 0:
            positions = positions_response.get("result", {}).get("list", [])
            print(f"✅ Found {len(positions)} current positions")
            
            if positions:
                # Convert to DataFrame
                df = pd.DataFrame(positions)
                
                # Add timezone conversion (convert to naive datetime for Excel)
                tz_se = pytz.timezone("Europe/Stockholm")
                if "updatedTime" in df.columns:
                    df["updatedTimeMs"] = pd.to_numeric(df["updatedTime"], errors="coerce")
                    df["updatedTime_UTC"] = pd.to_datetime(df["updatedTimeMs"], unit="ms", utc=True).dt.tz_localize(None)
                    df["updatedTime_Stockholm"] = pd.to_datetime(df["updatedTimeMs"], unit="ms", utc=True).dt.tz_convert(tz_se).dt.tz_localize(None)
                
                # Convert numeric columns
                for col in ["size","entryPrice","markPrice","unrealisedPnl","realisedPnl","cumRealisedPnl"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                
                # Save to Excel
                output_file = "bybit_current_positions.xlsx"
                
                with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
                    # Main positions sheet
                    df.to_excel(writer, index=False, sheet_name="Current_Positions")
                    
                    # Summary sheet
                    summary_data = {
                        "Metric": [
                            "Total Positions",
                            "Long Positions", 
                            "Short Positions",
                            "Total Size",
                            "Total Unrealized PnL",
                            "Total Realized PnL",
                            "Export Time"
                        ],
                        "Value": [
                            len(positions),
                            len(df[df["side"] == "Buy"]) if "side" in df.columns else 0,
                            len(df[df["side"] == "Sell"]) if "side" in df.columns else 0,
                            f"{df['size'].sum():.2f}" if "size" in df.columns else "0.00",
                            f"{df['unrealisedPnl'].sum():.2f}" if "unrealisedPnl" in df.columns else "0.00",
                            f"{df['realisedPnl'].sum():.2f}" if "realisedPnl" in df.columns else "0.00",
                            datetime.now(tz_se).strftime("%Y-%m-%d %H:%M:%S")
                        ]
                    }
                    
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, index=False, sheet_name="Summary")
                
                print(f"✅ Exported {len(positions)} current positions to {output_file}")
                
                # Show summary
                print("\n📊 Current Positions Summary:")
                if "symbol" in df.columns:
                    for _, pos in df.iterrows():
                        symbol = pos.get("symbol", "Unknown")
                        side = pos.get("side", "Unknown")
                        size = pos.get("size", 0)
                        entry_price = pos.get("entryPrice", 0)
                        mark_price = pos.get("markPrice", 0)
                        pnl = pos.get("unrealisedPnl", 0)
                        print(f"  {symbol} {side} {size} @ {entry_price} (Mark: {mark_price}) PnL: {pnl}")
                
                return True
            else:
                print("⚠️  No current positions found")
        else:
            print(f"❌ API Error getting positions: {positions_response}")
        
        # Try to get order history
        print("\n📊 Fetching recent order history...")
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
                    recent = df.nlargest(5, "createdTimeMs")
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
        else:
            print(f"❌ API Error getting orders: {orders_response}")
            
        return False
            
    except Exception as e:
        print(f"❌ Error getting bot trade data: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(get_bot_trade_data())
    if success:
        print("\n🎉 Successfully downloaded bot trade data from Bybit API!")
    else:
        print("\n❌ Failed to get bot trade data from API")
