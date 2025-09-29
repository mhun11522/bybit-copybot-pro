import datetime
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.storage.db import aiosqlite, DB_PATH
from app.telegram.templates import daily_report, weekly_report


class ReportService:
    def __init__(self, db, telegram_client, tz: str = "Europe/Stockholm"):
        self.db = db
        self.tg = telegram_client
        self.tz = pytz.timezone(tz)
        self.scheduler = AsyncIOScheduler(timezone=self.tz)

    def start(self):
        self.scheduler.add_job(self.daily_report, "cron", hour=8, minute=0)
        self.scheduler.add_job(self.daily_summary, "cron", hour=22, minute=0)
        self.scheduler.add_job(self.weekly_report, "cron", day_of_week="sun", hour=22, minute=0)
        self.scheduler.start()

    async def daily_report(self):
        text = await self._build_report_text(label="Morning")
        await self.tg.send_message(text)

    async def daily_summary(self):
        text = await self._build_report_text(label="Evening")
        await self.tg.send_message(text)

    async def weekly_report(self):
        text = await self._build_report_text(label="Weekly")
        await self.tg.send_message(text)

    async def _build_report_text(self, label: str) -> str:
        now = datetime.datetime.now(self.tz)
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*), COALESCE(SUM(realized_pnl),0) FROM trades WHERE state='DONE'") as c2:
                r2 = await c2.fetchone()
                closed_trades = r2[0] if r2 else 0
                total_pnl = float(r2[1]) if r2 else 0.0
        ts = now.strftime('%Y-%m-%d %H:%M')
        if label == "Weekly":
            return weekly_report(ts, closed_trades, total_pnl)
        return daily_report(ts, closed_trades, total_pnl)

