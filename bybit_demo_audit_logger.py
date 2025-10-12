#!/usr/bin/env python3
"""
Bybit Demo Audit Logger - Complete trade/order history tracker
Purpose: Track all Bybit Demo activity since Demo has no export function
"""

import os, hmac, time, json, sqlite3, threading, gzip, csv, signal
from hashlib import sha256
from datetime import datetime, timezone
from pathlib import Path
import websocket  # pip install websocket-client

# Configuration
DEMO_WSS = "wss://stream-demo.bybit.com/v5/private"
PING_INTERVAL_SEC = 20
CSV_ROTATE_ROWS = 50_000
DB_PATH = Path("bybit_demo_audit.sqlite3")
CSV_DIR = Path("audit_csv")
CSV_DIR.mkdir(exist_ok=True)

# API Credentials
API_KEY = os.environ.get("BYBIT_API_KEY", "")
API_SECRET = os.environ.get("BYBIT_API_SECRET", "")

# Database Schema
SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS orders(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    data JSON NOT NULL
);

CREATE TABLE IF NOT EXISTS executions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    data JSON NOT NULL
);

CREATE TABLE IF NOT EXISTS positions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    data JSON NOT NULL
);

CREATE TABLE IF NOT EXISTS wallets(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    data JSON NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_ts ON orders(ts);
CREATE INDEX IF NOT EXISTS idx_executions_ts ON executions(ts);
CREATE INDEX IF NOT EXISTS idx_positions_ts ON positions(ts);
CREATE INDEX IF NOT EXISTS idx_wallets_ts ON wallets(ts);
"""

class AuditStore:
    """Dual storage: SQLite + compressed CSV"""
    
    def __init__(self, db_path=DB_PATH):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.executescript(SCHEMA)
        self.lock = threading.Lock()
        
        # CSV writers
        self.csv_files = {
            "orders": self._open_csv("orders"),
            "executions": self._open_csv("executions"),
            "positions": self._open_csv("positions"),
            "wallets": self._open_csv("wallets"),
        }
        self.csv_rows = {k: 0 for k in self.csv_files}
        
        print(f"✅ Audit store initialized")
        print(f"   Database: {db_path}")
        print(f"   CSV directory: {CSV_DIR}")
    
    def _open_csv(self, name):
        """Open new compressed CSV file"""
        fname = CSV_DIR / f"{name}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.csv.gz"
        f = gzip.open(fname, mode="at", newline="", encoding="utf-8")
        writer = csv.writer(f)
        writer.writerow(["ts_ms", "json"])
        return (f, writer)
    
    def _rotate_if_needed(self, name):
        """Rotate CSV if row limit reached"""
        if self.csv_rows[name] >= CSV_ROTATE_ROWS:
            f, _ = self.csv_files[name]
            f.close()
            self.csv_files[name] = self._open_csv(name)
            self.csv_rows[name] = 0
            print(f"🔄 Rotated CSV: {name}")
    
    def insert(self, table, payload: dict):
        """Insert data into both SQLite and CSV"""
        ts = int(time.time() * 1000)
        row = (ts, json.dumps(payload, separators=(",", ":")))
        
        with self.lock:
            # Insert to database
            self.conn.execute(f"INSERT INTO {table}(ts, data) VALUES(?, ?)", row)
            
            # Write to CSV
            f, writer = self.csv_files[table]
            writer.writerow([ts, row[1]])
            self.csv_rows[table] += 1
            self._rotate_if_needed(table)
            
            # Commit important events immediately
            if table in ("executions", "orders"):
                self.conn.commit()
    
    def flush(self):
        """Flush all pending writes"""
        with self.lock:
            self.conn.commit()
    
    def close(self):
        """Close all connections"""
        with self.lock:
            self.conn.commit()
            for f, _ in self.csv_files.values():
                f.close()
            self.conn.close()
        print("✅ Audit store closed")


def sign_ws(api_key: str, api_secret: str):
    """
    Bybit private WebSocket authentication
    
    op: "auth"
    args: [api_key, expires_ms, signature]
    signature = HMAC_SHA256(secret, "GET/realtime" + expires)
    """
    expires = int((time.time() + 60) * 1000)
    msg = f"GET/realtime{expires}".encode()
    sig = hmac.new(api_secret.encode(), msg, sha256).hexdigest()
    return {"op": "auth", "args": [api_key, expires, sig]}


class BybitDemoAuditLogger:
    """WebSocket logger for complete Bybit Demo audit trail"""
    
    def __init__(self, store: AuditStore, url=DEMO_WSS):
        self.store = store
        self.url = url
        self.ws = None
        self._stop = threading.Event()
        print(f"✅ Audit logger initialized")
        print(f"   WebSocket: {url}")
    
    def _on_open(self, ws):
        """Handle WebSocket connection"""
        print("✅ WebSocket connected - Authenticating...")
        
        # Authenticate
        ws.send(json.dumps(sign_ws(API_KEY, API_SECRET)))
        
        # Subscribe to all private topics
        subs = {
            "op": "subscribe",
            "args": ["order", "execution", "position", "wallet"]
        }
        ws.send(json.dumps(subs))
        print("✅ Subscribed to: order, execution, position, wallet")
    
    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            msg = json.loads(message)
        except json.JSONDecodeError:
            return
        
        # Skip control messages
        if "op" in msg and msg.get("op") in ("pong", "ping", "subscribe", "auth"):
            if msg.get("op") == "auth" and msg.get("success"):
                print("✅ Authenticated to Bybit Demo WebSocket")
            return
        
        # Route to appropriate table
        topic = msg.get("topic")
        if not topic:
            return
        
        if topic.startswith("order"):
            self.store.insert("orders", msg)
            print(f"📝 Order: {msg.get('data', [{}])[0].get('symbol', 'N/A')} - {msg.get('data', [{}])[0].get('orderStatus', 'N/A')}")
        
        elif topic.startswith("execution"):
            self.store.insert("executions", msg)
            exec_data = msg.get('data', [{}])[0]
            print(f"💰 Execution: {exec_data.get('symbol', 'N/A')} @ {exec_data.get('execPrice', 'N/A')}")
        
        elif topic.startswith("position"):
            self.store.insert("positions", msg)
            pos_data = msg.get('data', [{}])[0]
            print(f"📊 Position: {pos_data.get('symbol', 'N/A')} Size: {pos_data.get('size', '0')}")
        
        elif topic.startswith("wallet"):
            self.store.insert("wallets", msg)
            print(f"💵 Wallet update")
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f"⚠️  WebSocket error: {error}")
        self.store.insert("wallets", {"type": "ws_error", "err": str(error)})
    
    def _on_close(self, ws, code, reason):
        """Handle WebSocket close"""
        print(f"⚠️  WebSocket closed: code={code}, reason={reason}")
        self.store.insert("wallets", {"type": "ws_close", "code": code, "reason": str(reason)})
    
    def _heartbeat_loop(self):
        """Send periodic ping to keep connection alive"""
        while not self._stop.wait(PING_INTERVAL_SEC):
            try:
                self.ws.send(json.dumps({"op": "ping", "req_id": "hb"}))
            except Exception:
                pass
    
    def start(self):
        """Start WebSocket connection"""
        print("🚀 Starting Bybit Demo Audit Logger...")
        websocket.enableTrace(False)
        
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        
        # Start heartbeat thread
        t = threading.Thread(target=self._heartbeat_loop, daemon=True)
        t.start()
        
        # Run WebSocket (blocks until stopped)
        while not self._stop.is_set():
            try:
                self.ws.run_forever(ping_interval=0)
            except Exception as e:
                self._on_error(self.ws, e)
                time.sleep(2)  # Wait before reconnect
    
    def stop(self):
        """Stop WebSocket connection"""
        self._stop.set()
        try:
            self.ws.close()
        except Exception:
            pass
        self.store.flush()
        print("✅ Audit logger stopped")


def main():
    """Main entry point"""
    print("=" * 70)
    print("BYBIT DEMO AUDIT LOGGER")
    print("=" * 70)
    print(f"API Key: {API_KEY[:10]}...")
    print()
    
    if not API_KEY or not API_SECRET:
        print("❌ Error: API credentials not found")
        print("   Set BYBIT_API_KEY and BYBIT_API_SECRET environment variables")
        return
    
    store = AuditStore()
    logger = BybitDemoAuditLogger(store)
    
    def _shutdown(*_a):
        print("\n🛑 Shutting down...")
        logger.stop()
        store.close()
        raise SystemExit(0)
    
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    
    logger.start()


if __name__ == "__main__":
    main()

