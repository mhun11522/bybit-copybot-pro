#!/usr/bin/env python3
import sqlite3
from datetime import datetime, date
import os

def check_daily_stats():
    """Check daily trading statistics from database."""
    print("📊 DAILY TRADING STATISTICS CHECK")
    print("=" * 50)
    
    if not os.path.exists('trades.sqlite'):
        print("❌ Database file 'trades.sqlite' not found")
        return
    
    try:
        conn = sqlite3.connect('trades.sqlite')
        cursor = conn.cursor()
        
        # Get today's date
        today = date.today().strftime('%Y-%m-%d')
        print(f"📅 Checking statistics for: {today}")
        print()
        
        # Check total trades
        cursor.execute('SELECT COUNT(*) FROM trades')
        total_trades = cursor.fetchone()[0]
        print(f"📈 Total trades in database: {total_trades}")
        
        # Check today's trades
        cursor.execute('SELECT COUNT(*) FROM trades WHERE DATE(created_at) = ?', (today,))
        today_trades = cursor.fetchone()[0]
        print(f"📈 Today's trades: {today_trades}")
        
        # Check completed trades (using 'state' column)
        cursor.execute('SELECT COUNT(*) FROM trades WHERE state = ?', ('COMPLETED',))
        completed_trades = cursor.fetchone()[0]
        print(f"✅ Completed trades: {completed_trades}")
        
        # Check today's completed trades
        cursor.execute('SELECT COUNT(*) FROM trades WHERE state = ? AND DATE(created_at) = ?', ('COMPLETED', today))
        today_completed = cursor.fetchone()[0]
        print(f"✅ Today's completed trades: {today_completed}")
        
        # Check signals
        cursor.execute('SELECT COUNT(*) FROM signals')
        total_signals = cursor.fetchone()[0]
        print(f"📡 Total signals: {total_signals}")
        
        # Check today's signals
        cursor.execute('SELECT COUNT(*) FROM signals WHERE DATE(created_at) = ?', (today,))
        today_signals = cursor.fetchone()[0]
        print(f"📡 Today's signals: {today_signals}")
        
        # Check recent trades with details
        print("\n🔍 RECENT TRADES (Last 10):")
        cursor.execute('''
            SELECT trade_id, symbol, direction, state, created_at, realized_pnl
            FROM trades 
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        recent_trades = cursor.fetchall()
        
        if recent_trades:
            for trade in recent_trades:
                trade_id, symbol, direction, state, created_at, realized_pnl = trade
                pnl_str = f"{realized_pnl:.2f} USDT" if realized_pnl else "N/A"
                print(f"  • {trade_id}: {symbol} {direction} - {state} - PnL: {pnl_str} - {created_at}")
        else:
            print("  • No trades found")
        
        # Check recent signals
        print("\n📡 RECENT SIGNALS (Last 5):")
        cursor.execute('''
            SELECT signal_id, symbol, direction, channel_name, created_at
            FROM signals 
            ORDER BY created_at DESC 
            LIMIT 5
        ''')
        recent_signals = cursor.fetchall()
        
        if recent_signals:
            for signal in recent_signals:
                signal_id, symbol, direction, channel_name, created_at = signal
                print(f"  • {signal_id}: {symbol} {direction} from {channel_name} - {created_at}")
        else:
            print("  • No signals found")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")

if __name__ == "__main__":
    check_daily_stats()
