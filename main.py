from app.core import decimal_ctx  # set global Decimal precision early
import asyncio
import sys
from app import settings
from app.telegram_client import client
from app.reports.service import ReportService
from app.storage.db import init_db
from app.runtime.resume import resume_open_trades

if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

async def main():
    print("🚀 Starting Bybit Copybot Pro...")
    await init_db()

    telegram_ready = settings.TELEGRAM_API_ID > 0 and bool(settings.TELEGRAM_API_HASH)

    if telegram_ready:
        print("🔌 Telegram credentials detected. Connecting...")
        await client.start()
    else:
        print("⚠️ TELEGRAM_API_ID/HASH not set. Running in offline mode (no Telegram connection).")

    # Resume open trades: reattach OCO, trailing, hedge monitors
    try:
        await resume_open_trades()
    except Exception as e:
        print("Resume error:", e)

    report = ReportService(db=None, telegram_client=client)
    report.start()
    print("📊 Reporting scheduler started.")

    if telegram_ready:
        print("✅ Bot + reporting running... (waiting for Telegram messages)")
        await client.run_until_disconnected()
    else:
        print("✅ Bot running in offline mode. Press Ctrl+C to exit.")
        # Keep the process alive so scheduler continues to run
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())

