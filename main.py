import asyncio
import sys
import signal
from app.telegram.client import start_telegram
from app.reports.service import start_report_scheduler
from app.runtime.resume import resume_open_trades

# Windows asyncio fix
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

async def main():
    print("🚀 Starting Bybit Copybot Pro...")
    
    try:
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
        print("🔌 Starting Telegram client...")
        await start_telegram()
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Bot error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)

