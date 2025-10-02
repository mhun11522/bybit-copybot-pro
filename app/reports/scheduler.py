"""
Daily and Weekly report scheduler for Stockholm timezone.
Daily: 08:00
Weekly: Saturday 22:00
"""

import asyncio
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from app.config.settings import TIMEZONE
from app.telegram.output import send_message
from app.storage.db import aiosqlite, DB_PATH

TZ = ZoneInfo(TIMEZONE)

async def _get_daily_stats(date_str: str):
    """Get trade statistics for a specific date"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Trades completed on this date
        async with db.execute("""
            SELECT symbol, channel_name, realized_pnl, leverage
            FROM trades
            WHERE date(closed_at) = ? AND state='DONE'
        """, (date_str,)) as cur:
            trades = await cur.fetchall()
        
        total_trades = len(trades)
        winning = sum(1 for t in trades if t[2] > 0)
        losing = sum(1 for t in trades if t[2] <= 0)
        total_pnl = sum(t[2] for t in trades)
        win_rate = (winning / total_trades * 100) if total_trades > 0 else 0
        
        # Group by channel
        by_channel = {}
        for symbol, channel, pnl, lev in trades:
            if channel not in by_channel:
                by_channel[channel] = []
            by_channel[channel].append((symbol, pnl, lev))
        
        return {
            "total_trades": total_trades,
            "winning": winning,
            "losing": losing,
            "total_pnl": total_pnl,
            "win_rate": win_rate,
            "by_channel": by_channel
        }

def _format_daily_report(date_str: str, stats: dict, group_name: str = None) -> str:
    """Format daily report according to client spec"""
    
    # If group-specific
    if group_name and group_name in stats["by_channel"]:
        trades_list = stats["by_channel"][group_name]
        
        lines = [f"📑 DAGLIG RAPPORT FRÅN GRUPP: {group_name}\n"]
        lines.append("📊 RESULTAT")
        lines.append("Symbol        %            USDT")
        
        for symbol, pnl, lev in trades_list[:20]:  # Top 20
            pct = (pnl / 20) * lev  # Rough estimate: result% with leverage
            lines.append(f"{symbol:12}  {pct:+6.2f}%      {pnl:+8.2f}")
        
        lines.append("\n" + "-" * 40)
        total_pnl = sum(t[1] for t in trades_list)
        lines.append(f"📈 Antal signaler: {len(trades_list)}")
        lines.append(f"💹 Totalt resultat: {total_pnl:.2f} USDT")
        lines.append(f"📊 Vinst/Förlust: {total_pnl:.2f} USDT")
        
        # English version
        lines.append(f"\n📑 DAILY REPORT FROM GROUP: {group_name}\n")
        lines.append("📊 RESULTS")
        lines.append("Symbol        %            USDT")
        
        for symbol, pnl, lev in trades_list[:20]:
            pct = (pnl / 20) * lev
            lines.append(f"{symbol:12}  {pct:+6.2f}%      {pnl:+8.2f}")
        
        lines.append("\n" + "-" * 40)
        lines.append(f"📈 Number of signals: {len(trades_list)}")
        lines.append(f"💹 Total result: {total_pnl:.2f} USDT")
        lines.append(f"📊 Profit/Loss: {total_pnl:.2f} USDT")
        
        return "\n".join(lines)
    
    # Overall summary
    lines = [f"📑 DAGLIG RAPPORT - ALLA GRUPPER\n"]
    lines.append(f"📅 Datum: {date_str}")
    lines.append(f"📈 Totalt antal signaler: {stats['total_trades']}")
    lines.append(f"✅ Vinnande: {stats['winning']}")
    lines.append(f"❌ Förlorande: {stats['losing']}")
    lines.append(f"💹 Total PnL: {stats['total_pnl']:.2f} USDT")
    lines.append(f"📊 Win-rate: {stats['win_rate']:.1f}%")
    
    return "\n".join(lines)

async def generate_daily_report():
    """Generate and send daily report at 08:00 Sweden time"""
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    stats = await _get_daily_stats(today)
    
    # Send overall report
    overall = _format_daily_report(today, stats)
    await send_message(overall)
    
    # Send per-group reports
    for group_name in stats["by_channel"].keys():
        group_report = _format_daily_report(today, stats, group_name)
        await send_message(group_report)

async def generate_weekly_report():
    """Generate and send weekly report on Saturday 22:00 Sweden time"""
    # Get last 7 days
    end_date = datetime.now(TZ)
    start_date = end_date - timedelta(days=7)
    
    # Aggregate stats from last 7 days
    # Similar to daily but summed across the week
    await send_message("📊 Weekly report (implementation pending)")

async def daily_scheduler():
    """Run daily report at 08:00 Sweden time"""
    while True:
        now = datetime.now(TZ)
        target = now.replace(hour=8, minute=0, second=0, microsecond=0)
        
        if now >= target:
            target += timedelta(days=1)
        
        wait_seconds = (target - now).total_seconds()
        print(f"📅 Next daily report in {wait_seconds/3600:.1f} hours")
        
        await asyncio.sleep(wait_seconds)
        await generate_daily_report()

async def weekly_scheduler():
    """Run weekly report on Saturday 22:00 Sweden time"""
    while True:
        now = datetime.now(TZ)
        # Find next Saturday
        days_until_saturday = (5 - now.weekday()) % 7
        if days_until_saturday == 0 and now.hour >= 22:
            days_until_saturday = 7
        
        target = now + timedelta(days=days_until_saturday)
        target = target.replace(hour=22, minute=0, second=0, microsecond=0)
        
        wait_seconds = (target - now).total_seconds()
        print(f"📅 Next weekly report in {wait_seconds/3600:.1f} hours")
        
        await asyncio.sleep(wait_seconds)
        await generate_weekly_report()
