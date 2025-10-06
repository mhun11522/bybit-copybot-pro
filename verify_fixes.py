#!/usr/bin/env python3
"""Verify all fixes are working correctly."""

import sqlite3
import pandas as pd
from datetime import datetime

def verify_all_fixes():
    """Verify all fixes are working correctly."""
    print("🔍 VERIFYING ALL FIXES")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect('trades.sqlite')
        cursor = conn.cursor()
        
        # 1. Check stuck trades
        cursor.execute('SELECT COUNT(*) FROM trades WHERE state = "OPENING"')
        stuck_count = cursor.fetchone()[0]
        
        # 2. Check PnL data
        cursor.execute('SELECT COUNT(*) FROM trades WHERE realized_pnl IS NOT NULL AND realized_pnl != 0')
        pnl_count = cursor.fetchone()[0]
        
        # 3. Check total trades
        cursor.execute('SELECT COUNT(*) FROM trades')
        total_trades = cursor.fetchone()[0]
        
        # 4. Check DONE trades
        cursor.execute('SELECT COUNT(*) FROM trades WHERE state = "DONE"')
        done_count = cursor.fetchone()[0]
        
        # 5. Get PnL summary
        cursor.execute('SELECT SUM(realized_pnl) FROM trades WHERE realized_pnl IS NOT NULL')
        total_pnl = cursor.fetchone()[0] or 0
        
        # 6. Get recent trades
        cursor.execute('''
            SELECT trade_id, symbol, direction, state, realized_pnl, created_at
            FROM trades 
            ORDER BY created_at DESC 
            LIMIT 5
        ''')
        recent_trades = cursor.fetchall()
        
        print(f"📊 VERIFICATION RESULTS:")
        print(f"   • Total trades: {total_trades}")
        print(f"   • DONE trades: {done_count}")
        print(f"   • Stuck trades: {stuck_count}")
        print(f"   • Trades with PnL: {pnl_count}")
        print(f"   • Total PnL: ${total_pnl:.2f}")
        
        print(f"\n📋 RECENT TRADES:")
        for trade in recent_trades:
            trade_id, symbol, direction, state, pnl, created_at = trade
            pnl_str = f"${pnl:.2f}" if pnl else "N/A"
            print(f"   • {trade_id}: {symbol} {direction} - {state} - PnL: {pnl_str}")
        
        # Status check
        print(f"\n✅ STATUS CHECK:")
        
        if stuck_count == 0:
            print("   ✅ Stuck trades: FIXED")
        else:
            print(f"   ❌ Stuck trades: {stuck_count} still stuck")
        
        if pnl_count > 0:
            print("   ✅ PnL calculation: WORKING")
        else:
            print("   ❌ PnL calculation: NOT WORKING")
        
        if done_count > 0:
            print("   ✅ Trade completion: WORKING")
        else:
            print("   ❌ Trade completion: NOT WORKING")
        
        # Overall status
        if stuck_count == 0 and pnl_count > 0 and done_count > 0:
            print(f"\n🎉 ALL FIXES SUCCESSFUL!")
            print(f"   • {done_count}/{total_trades} trades completed")
            print(f"   • Total PnL: ${total_pnl:.2f}")
            print(f"   • No stuck trades")
        else:
            print(f"\n⚠️  SOME ISSUES REMAIN")
            print(f"   • Stuck trades: {stuck_count}")
            print(f"   • PnL working: {pnl_count > 0}")
            print(f"   • Completion rate: {done_count}/{total_trades}")
        
        conn.close()
        
        return {
            'total_trades': total_trades,
            'done_trades': done_count,
            'stuck_trades': stuck_count,
            'pnl_trades': pnl_count,
            'total_pnl': total_pnl,
            'success': stuck_count == 0 and pnl_count > 0 and done_count > 0
        }
        
    except Exception as e:
        print(f"❌ Error verifying fixes: {e}")
        return None

if __name__ == "__main__":
    verify_all_fixes()
