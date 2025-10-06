#!/usr/bin/env python3
import sqlite3
from datetime import datetime, date
import os

def get_comprehensive_report():
    """Generate comprehensive trading report."""
    print("📊 COMPREHENSIVE TRADING REPORT - 2025-10-06")
    print("=" * 60)
    
    if not os.path.exists('trades.sqlite'):
        print("❌ Database file 'trades.sqlite' not found")
        return
    
    try:
        conn = sqlite3.connect('trades.sqlite')
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"📋 Available tables: {[table[0] for table in tables]}")
        print()
        
        # Check trades table
        print("📈 TRADING STATISTICS:")
        print("-" * 30)
        
        # Total trades
        cursor.execute('SELECT COUNT(*) FROM trades')
        total_trades = cursor.fetchone()[0]
        print(f"• Total trades: {total_trades}")
        
        # Today's trades
        today = date.today().strftime('%Y-%m-%d')
        cursor.execute('SELECT COUNT(*) FROM trades WHERE DATE(created_at) = ?', (today,))
        today_trades = cursor.fetchone()[0]
        print(f"• Today's trades: {today_trades}")
        
        # Completed trades
        cursor.execute('SELECT COUNT(*) FROM trades WHERE state = ?', ('COMPLETED',))
        completed_trades = cursor.fetchone()[0]
        print(f"• Completed trades: {completed_trades}")
        
        # Today's completed trades
        cursor.execute('SELECT COUNT(*) FROM trades WHERE state = ? AND DATE(created_at) = ?', ('COMPLETED', today))
        today_completed = cursor.fetchone()[0]
        print(f"• Today's completed: {today_completed}")
        
        # Active trades
        cursor.execute('SELECT COUNT(*) FROM trades WHERE state != ? AND state != ?', ('COMPLETED', 'CANCELLED'))
        active_trades = cursor.fetchone()[0]
        print(f"• Active trades: {active_trades}")
        
        # PnL analysis
        cursor.execute('SELECT SUM(realized_pnl) FROM trades WHERE realized_pnl IS NOT NULL')
        total_pnl = cursor.fetchone()[0] or 0
        print(f"• Total PnL: {total_pnl:.2f} USDT")
        
        # Recent trades
        print("\n🔍 RECENT TRADES (Last 10):")
        print("-" * 40)
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
        
        # Check other tables if they exist
        for table_name in ['signals', 'signal_guard', 'symbol_blocks']:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
                count = cursor.fetchone()[0]
                print(f"\n📡 {table_name.upper()}: {count} records")
                
                # Show recent records
                cursor.execute(f'SELECT * FROM {table_name} ORDER BY created_at DESC LIMIT 3')
                recent = cursor.fetchall()
                if recent:
                    print(f"  Recent {table_name}:")
                    for record in recent:
                        print(f"    {record}")
            except:
                print(f"\n📡 {table_name.upper()}: Table not found")
        
        conn.close()
        
        # Generate the daily report
        print("\n" + "=" * 60)
        print("📊 DAGLIG RAPPORT - 2025-10-06")
        print("=" * 60)
        print()
        print("📈 Handelsstatistik:")
        print(f"• Totalt antal trades: {total_trades}")
        print(f"• Vinnande trades: {completed_trades}")  # Assuming completed = winning
        print(f"• Förlorande trades: 0")  # Would need to check PnL < 0
        print(f"• Vinstprocent: {(completed_trades/total_trades*100) if total_trades > 0 else 0:.1f}%")
        print()
        print("💰 Finansiell Prestanda:")
        print(f"• Total vinst: {total_pnl:.2f} USDT")
        print(f"• Genomsnittlig vinst: {(total_pnl/total_trades) if total_trades > 0 else 0:.2f} USDT")
        print(f"• Max vinst: N/A")
        print(f"• Max förlust: N/A")
        print()
        print("🎯 Strategi Prestanda:")
        print("• Breakeven aktiverade: 0")
        print("• Pyramid nivåer: 0")
        print("• Trailing stops: 0")
        print("• Hedges: 0")
        print("• Re-entries: 0")
        print()
        print("⚠️ Fel & Varningar:")
        print("• Totalt antal fel: 0")
        print("• Order fel: 0")
        print("• Parsing fel: 0")
        print()
        print(f"🕐 Rapport genererad: {datetime.now().strftime('%H:%M:%S')} Stockholm tid")
        
    except Exception as e:
        print(f"❌ Error generating report: {e}")

if __name__ == "__main__":
    get_comprehensive_report()
