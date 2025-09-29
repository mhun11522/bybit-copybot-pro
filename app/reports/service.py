import datetime
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler


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
        text = self._build_report("Morning")
        await self.tg.send_message(text)

    async def daily_summary(self):
        text = self._build_report("Evening")
        await self.tg.send_message(text)

    async def weekly_report(self):
        text = self._build_report("Weekly")
        await self.tg.send_message(text)

    def _build_report(self, label: str) -> str:
        now = datetime.datetime.now(self.tz)
        # Placeholder values; replace with DB aggregates when available
        return (
            f"📊 {label} report {now.strftime('%Y-%m-%d %H:%M')}\n"
            f"- Trades: 0\n"
            f"- PnL: 0 USDT"
        )

