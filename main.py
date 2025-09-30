import asyncio
import sys
from app.telegram.client import start_telegram
from app.reports.service import start_report_scheduler
from app.runtime.resume import resume_open_trades

if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass

async def main():
    print("🚀 Starting Bybit Copybot Pro...")
    
    # Start reporting service
    await start_report_scheduler()
    print("📊 Reporting scheduler started.")
    
    # Resume open trades: reattach OCO, trailing, hedge monitors
    try:
        await resume_open_trades()
        print("🔄 Open trades resumed.")
    except Exception as e:
        print(f"⚠️ Resume error: {e}")
    
    # Start Telegram client
    await start_telegram()

if __name__ == "__main__":
    asyncio.run(main())

