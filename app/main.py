import asyncio
from app.telegram.client import start_telegram
from app.reports.service import start_report_scheduler
from app.runtime.resume import resume_open_trades

async def main():
    await start_report_scheduler()
    await resume_open_trades()
    await start_telegram()

if __name__ == "__main__":
    asyncio.run(main())