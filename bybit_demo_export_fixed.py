#!/usr/bin/env python3
import os, time, hmac, hashlib, requests
from urllib.parse import urlencode
from datetime import datetime, timedelta, timezone
import pandas as pd, pytz
from dateutil import parser as dtparser

API_BASE = "https://api-demo.bybit.com"   # DEMO (not testnet)
ENDPOINT  = "/v5/execution/list"
API_KEY   = os.getenv("BYBIT_API_KEY")
API_SECRET= os.getenv("BYBIT_API_SECRET")
RECV_WINDOW = "10000"  # Increased window

if not API_KEY or not API_SECRET:
    raise SystemExit("Missing BYBIT_API_KEY/BYBIT_API_SECRET in environment.")

def get_server_time():
    """Get server time to sync timestamps"""
    try:
        r = requests.get(f"{API_BASE}/v5/market/time", timeout=10)
        r.raise_for_status()
        j = r.json()
        if j.get("retCode") == 0:
            return int(j["result"]["timeSecond"]) * 1000
    except:
        pass
    return int(time.time() * 1000)

def sign_v5(params: dict) -> dict:
    """v5 signature: timestamp + api_key + recv_window + queryString (sorted)"""
    # Use server time for better sync
    server_time = get_server_time()
    ts = str(server_time)
    q = urlencode(sorted(params.items()))
    prehash = f"{ts}{API_KEY}{RECV_WINDOW}{q}"
    sig = hmac.new(API_SECRET.encode(), prehash.encode(), hashlib.sha256).hexdigest()
    return {
        "X-BAPI-API-KEY": API_KEY,
        "X-BAPI-TIMESTAMP": ts,
        "X-BAPI-RECV-WINDOW": RECV_WINDOW,
        "X-BAPI-SIGN": sig,
    }

def fetch_execs(category: str, start_ms: int, end_ms: int):
    """Fetch all executions for a category within [start_ms, end_ms], handling pagination."""
    out, cursor = [], None
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            while True:
                p = {"category": category, "startTime": str(start_ms), "endTime": str(end_ms), "limit": "100"}
                if cursor: p["cursor"] = cursor
                r = requests.get(API_BASE+ENDPOINT, params=p, headers=sign_v5(p), timeout=30)
                r.raise_for_status()
                j = r.json()
                
                if j.get("retCode") == 0:
                    res = (j.get("result") or {}) 
                    out.extend(res.get("list") or [])
                    cursor = res.get("nextPageCursor")
                    if not cursor:
                        break
                elif j.get("retCode") == 10002:  # Timestamp error
                    print(f"Timestamp sync error, retrying... (attempt {attempt + 1})")
                    time.sleep(1)
                    break
                else:
                    print(f"API Error: {j}")
                    return out
            break
        except Exception as e:
            print(f"Request error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                print(f"Failed to fetch {category} after {max_retries} attempts")
                return out
    
    return out

def main(start_iso: str=None, end_iso: str=None, outfile="bybit_demo_trades.xlsx"):
    # Demo retention is ~7 days — clamp the requested window accordingly
    utcnow = datetime.now(timezone.utc)
    last7  = utcnow - timedelta(days=7)
    sdt = dtparser.parse(start_iso).astimezone(timezone.utc) if start_iso else last7
    edt = dtparser.parse(end_iso).astimezone(timezone.utc) if end_iso else utcnow
    if sdt < last7:
        sdt = last7
    if edt <= sdt:
        raise SystemExit("end <= start")
    sm, em = int(sdt.timestamp()*1000), int(edt.timestamp()*1000)

    print(f"Fetching trades from {sdt} to {edt}")
    print(f"Time range: {sm} to {em}")

    cats = ["linear","inverse","spot","option"]
    tz_se = pytz.timezone("Europe/Stockholm")
    frames = []
    all_data = []

    for c in cats:
        print(f"Fetching {c} trades...")
        rows = fetch_execs(c, sm, em)
        print(f"Found {len(rows)} {c} trades")
        
        if rows:
            df = pd.DataFrame(rows)
            all_data.append(df.assign(category=c))

            # Timestamps
            if "execTime" in df.columns:
                df["execTimeMs"] = pd.to_numeric(df["execTime"], errors="coerce")
                df["execTime_UTC"] = pd.to_datetime(df["execTimeMs"], unit="ms", utc=True)
                df["execTime_Stockholm"] = df["execTime_UTC"].dt.tz_convert(tz_se)

            # Numeric columns
            for col in ["orderPrice","orderQty","execPrice","execQty","execValue","execFee","feeRate","leavesQty"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            # Sorting
            sort_cols = [c for c in ["execTimeMs","execId","orderId"] if c in df.columns]
            if sort_cols:
                df = df.sort_values(sort_cols, ascending=True).reset_index(drop=True)

            frames.append(df)

    # Create Excel file
    if all_data:
        with pd.ExcelWriter(outfile, engine="openpyxl") as xlw:
            # Write individual category sheets
            for i, df in enumerate(frames):
                df.to_excel(xlw, index=False, sheet_name=cats[i])
            
            # Summary sheet with all data
            combined_df = pd.concat(all_data, ignore_index=True)
            combined_df.to_excel(xlw, index=False, sheet_name="ALL")
            
        print(f"✅ Created: {outfile}")
        print(f"📊 Total trades exported: {len(combined_df)}")
        
        # Show summary
        if "category" in combined_df.columns:
            print("\n📈 Trade Summary by Category:")
            summary = combined_df.groupby("category").size()
            for cat, count in summary.items():
                print(f"  {cat}: {count} trades")
                
    else:
        # Create empty Excel file with message
        with pd.ExcelWriter(outfile, engine="openpyxl") as xlw:
            empty_df = pd.DataFrame({"Message": ["No demo trades found in the last 7 days"]})
            empty_df.to_excel(xlw, index=False, sheet_name="No_Data")
        print(f"⚠️  No trades found. Created empty file: {outfile}")

if __name__ == "__main__":
    import sys
    # Example: default to last 7 days if no dates passed
    if len(sys.argv) == 1:
        main()
    elif len(sys.argv) == 3:
        main(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python bybit_demo_export_fixed.py [<start ISO> <end ISO>]")
