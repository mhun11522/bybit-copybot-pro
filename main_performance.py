"""
High-performance version of main.py with winloop support for Windows.
Use this if you want maximum performance on Windows.

Install requirements: pip install -r requirements-performance.txt
"""

import asyncio
import sys
import signal
import warnings
from app.telegram.client import start_telegram
from app.reports.service import start_report_scheduler
from app.runtime.resume import resume_open_trades

# High-performance asyncio configuration
if sys.platform.startswith("win"):
    try:
        # Try to use winloop for maximum performance (5x faster than default)
        import winloop
        winloop.install()
        print("🚀 Using winloop for maximum performance")
    except ImportError:
        # Fallback to ProactorEventLoop
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        print("📊 Using ProactorEventLoop (install winloop for better performance)")
    
    # Suppress asyncio warnings that are common on Windows
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="asyncio")
    
elif sys.platform.startswith(("linux", "darwin")):
    try:
        # Use uvloop on Unix systems for better performance
        import uvloop
        uvloop.install()
        print("🚀 Using uvloop for maximum performance")
    except ImportError:
        print("📊 Using default event loop (install uvloop for better performance)")

async def main():
    print("🚀 Starting Bybit Copybot Pro (Performance Mode)...")
    print(f"🐍 Python {sys.version}")
    print(f"🪟 Platform: {sys.platform}")
    
    # Configure asyncio for better performance
    if sys.platform.startswith("win"):
        # Set debug mode for development (remove in production)
        # asyncio.get_event_loop().set_debug(True)
        pass
    
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
    finally:
        # Cleanup on exit
        print("🧹 Cleaning up...")
        try:
            # Get all running tasks and cancel them
            tasks = [task for task in asyncio.all_tasks() if not task.done()]
            if tasks:
                print(f"🔄 Cancelling {len(tasks)} running tasks...")
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")
        print("✅ Cleanup completed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)