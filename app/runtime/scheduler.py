"""Simple scheduler for daily and weekly reports."""
import asyncio
from datetime import datetime, timedelta, time
import zoneinfo

TZ = zoneinfo.ZoneInfo("Europe/Stockholm")

async def run_at_local(hh: int, mm: int, coro):
    """Run a coroutine daily at specified local time (HH:MM)"""
    while True:
        now = datetime.now(TZ)
        target = datetime.combine(now.date(), time(hh, mm, tzinfo=TZ))
        if target <= now:
            target += timedelta(days=1)
        seconds_until = (target - now).total_seconds()
        print(f"📅 Next daily run scheduled for {target} ({seconds_until/3600:.1f}h from now)")
        await asyncio.sleep(seconds_until)
        try:
            await coro()
        except Exception as e:
            print(f"❌ Scheduled task failed: {e}")

async def run_weekly_at_local(weekday: int, hh: int, mm: int, coro):
    """Run a coroutine weekly at specified weekday and time.
    weekday: Monday=0 ... Sunday=6
    """
    while True:
        now = datetime.now(TZ)
        days_ahead = (weekday - now.weekday()) % 7
        if days_ahead == 0 and now.time() >= time(hh, mm):
            days_ahead = 7
        target_date = now.date() + timedelta(days=days_ahead)
        target = datetime.combine(target_date, time(hh, mm, tzinfo=TZ))
        seconds_until = (target - now).total_seconds()
        print(f"📅 Next weekly run scheduled for {target} ({seconds_until/3600:.1f}h from now)")
        await asyncio.sleep(seconds_until)
        try:
            await coro()
        except Exception as e:
            print(f"❌ Scheduled task failed: {e}")
