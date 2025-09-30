"""Reporting service with Stockholm timezone scheduling."""

import asyncio
import aiosqlite
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.config.settings import TIMEZONE
from app.telegram.output import send_message

DB_PATH = "trades.sqlite"
TZ = ZoneInfo(TIMEZONE)

async def _get_trade_summary():
    """Get trade summary for reports."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Create tables if not exist
        await db.execute("""
            CREATE TABLE IF NOT EXISTS trades(
                trade_id TEXT PRIMARY KEY,
                symbol TEXT,
                direction TEXT,
                channel_name TEXT,
                leverage REAL,
                mode TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                closed_at DATETIME,
                status TEXT DEFAULT 'ACTIVE',
                realized_pnl REAL DEFAULT 0,
                max_pyramid_step INTEGER DEFAULT 0,
                reentry_count INTEGER DEFAULT 0,
                hedge_count INTEGER DEFAULT 0
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats(
                date TEXT PRIMARY KEY,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                losing_trades INTEGER DEFAULT 0,
                realized_pnl REAL DEFAULT 0,
                total_reentries INTEGER DEFAULT 0,
                total_hedges INTEGER DEFAULT 0,
                max_pyramid_step INTEGER DEFAULT 0
            )
        """)
        
        await db.commit()
        
        # Get today's stats
        today = datetime.now(TZ).strftime("%Y-%m-%d")
        
        # Get completed trades for today
        async with db.execute("""
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN realized_pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                COALESCE(SUM(realized_pnl), 0) as realized_pnl,
                SUM(reentry_count) as total_reentries,
                SUM(hedge_count) as total_hedges,
                MAX(max_pyramid_step) as max_pyramid_step
            FROM trades 
            WHERE DATE(closed_at) = ? AND status = 'CLOSED'
        """, (today,)) as cur:
            row = await cur.fetchone()
            
        return {
            "total_trades": row[0] or 0,
            "winning_trades": row[1] or 0,
            "losing_trades": row[2] or 0,
            "realized_pnl": row[3] or 0.0,
            "total_reentries": row[4] or 0,
            "total_hedges": row[5] or 0,
            "max_pyramid_step": row[6] or 0
        }

async def _get_weekly_summary():
    """Get weekly trade summary."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Get this week's stats (Monday to Sunday)
        now = datetime.now(TZ)
        week_start = now - timedelta(days=now.weekday())
        week_start_str = week_start.strftime("%Y-%m-%d")
        week_end_str = (week_start + timedelta(days=6)).strftime("%Y-%m-%d")
        
        async with db.execute("""
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN realized_pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                COALESCE(SUM(realized_pnl), 0) as realized_pnl,
                SUM(reentry_count) as total_reentries,
                SUM(hedge_count) as total_hedges,
                MAX(max_pyramid_step) as max_pyramid_step
            FROM trades 
            WHERE DATE(closed_at) BETWEEN ? AND ? AND status = 'CLOSED'
        """, (week_start_str, week_end_str)) as cur:
            row = await cur.fetchone()
            
        return {
            "total_trades": row[0] or 0,
            "winning_trades": row[1] or 0,
            "losing_trades": row[2] or 0,
            "realized_pnl": row[3] or 0.0,
            "total_reentries": row[4] or 0,
            "total_hedges": row[5] or 0,
            "max_pyramid_step": row[6] or 0,
            "week_start": week_start_str,
            "week_end": week_end_str
        }

async def send_daily_report():
    """Send daily report at 22:00 Stockholm time."""
    try:
        stats = await _get_trade_summary()
        now = datetime.now(TZ)
        timestamp = now.strftime("%Y-%m-%d %H:%M")
        
        win_rate = (stats["winning_trades"] / stats["total_trades"] * 100) if stats["total_trades"] > 0 else 0
        
        report = f"""📊 Daglig rapport ({timestamp})
═══════════════════════════════════════
📈 Affärer: {stats['total_trades']}
✅ Vinnande: {stats['winning_trades']} ({win_rate:.1f}%)
❌ Förlorande: {stats['losing_trades']}
💰 Realiserad PnL: {stats['realized_pnl']:.2f} USDT
🔄 Ominvesterade: {stats['total_reentries']}
♻️ Hedges: {stats['total_hedges']}
📈 Max pyramid: {stats['max_pyramid_step']}
═══════════════════════════════════════

📊 Daily Report ({timestamp})
═══════════════════════════════════════
📈 Trades: {stats['total_trades']}
✅ Winning: {stats['winning_trades']} ({win_rate:.1f}%)
❌ Losing: {stats['losing_trades']}
💰 Realized PnL: {stats['realized_pnl']:.2f} USDT
🔄 Re-entries: {stats['total_reentries']}
♻️ Hedges: {stats['total_hedges']}
📈 Max pyramid: {stats['max_pyramid_step']}
═══════════════════════════════════════"""
        
        await send_message(report)
        print(f"📊 Daily report sent at {timestamp}")
        
    except Exception as e:
        print(f"❌ Failed to send daily report: {e}")

async def send_weekly_report():
    """Send weekly report on Sunday at 22:00 Stockholm time."""
    try:
        stats = await _get_weekly_summary()
        now = datetime.now(TZ)
        timestamp = now.strftime("%Y-%m-%d %H:%M")
        
        win_rate = (stats["winning_trades"] / stats["total_trades"] * 100) if stats["total_trades"] > 0 else 0
        
        report = f"""📊 Veckorapport ({timestamp})
═══════════════════════════════════════
📅 Period: {stats['week_start']} - {stats['week_end']}
📈 Affärer: {stats['total_trades']}
✅ Vinnande: {stats['winning_trades']} ({win_rate:.1f}%)
❌ Förlorande: {stats['losing_trades']}
💰 Realiserad PnL: {stats['realized_pnl']:.2f} USDT
🔄 Ominvesterade: {stats['total_reentries']}
♻️ Hedges: {stats['total_hedges']}
📈 Max pyramid: {stats['max_pyramid_step']}
═══════════════════════════════════════

📊 Weekly Report ({timestamp})
═══════════════════════════════════════
📅 Period: {stats['week_start']} - {stats['week_end']}
📈 Trades: {stats['total_trades']}
✅ Winning: {stats['winning_trades']} ({win_rate:.1f}%)
❌ Losing: {stats['losing_trades']}
💰 Realized PnL: {stats['realized_pnl']:.2f} USDT
🔄 Re-entries: {stats['total_reentries']}
♻️ Hedges: {stats['total_hedges']}
📈 Max pyramid: {stats['max_pyramid_step']}
═══════════════════════════════════════"""
        
        await send_message(report)
        print(f"📊 Weekly report sent at {timestamp}")
        
    except Exception as e:
        print(f"❌ Failed to send weekly report: {e}")

def _next_occurrence(hour: int, minute: int, weekday: int = None):
    """Calculate next occurrence of scheduled time."""
    now = datetime.now(TZ)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    if weekday is None:
        # Daily at specified time
        if target <= now:
            target += timedelta(days=1)
        return target
    else:
        # Weekly on specified weekday
        days_ahead = (weekday - target.weekday()) % 7
        if days_ahead == 0 and target <= now:
            days_ahead = 7
        return target + timedelta(days=days_ahead)

async def _report_scheduler():
    """Main report scheduler loop."""
    while True:
        try:
            now = datetime.now(TZ)
            
            # Calculate next daily report (22:00)
            next_daily = _next_occurrence(22, 0)
            
            # Calculate next weekly report (Sunday 22:00)
            next_weekly = _next_occurrence(22, 0, 6)  # Sunday = 6
            
            # Wait until next report time
            next_report = min(next_daily, next_weekly)
            wait_seconds = (next_report - now).total_seconds()
            
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            
            # Check if it's time for daily report
            now = datetime.now(TZ)
            if now.hour == 22 and now.minute == 0:
                await send_daily_report()
                
                # Check if it's also Sunday for weekly report
                if now.weekday() == 6:  # Sunday
                    await send_weekly_report()
            
        except Exception as e:
            print(f"❌ Report scheduler error: {e}")
            await asyncio.sleep(60)  # Wait 1 minute on error

async def start_report_scheduler():
    """Start the report scheduler."""
    print(f"📊 Starting report scheduler (Stockholm timezone: {TIMEZONE})")
    asyncio.create_task(_report_scheduler())