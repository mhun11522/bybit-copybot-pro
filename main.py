import asyncio
import sys
from app.telegram_client import client
from app.reports.service import ReportService

if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

async def main():
    await client.start()
    report = ReportService(db=None, telegram_client=client)
    report.start()
    print("✅ Bot + reporting running...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())

