import asyncio
import sys
import os
import signal
import warnings
from app.telegram.enhanced_client import start_enhanced_telegram
from app.reports.service import start_report_scheduler
from app.reports.cleanup import cleanup_scheduler
from app.runtime.resume import resume_open_trades
from app.bybit.client import BybitClient
from app.trade.manager import get_position_manager

# Fix Windows console encoding for emojis
if sys.platform.startswith("win"):
    # Force UTF-8 encoding for stdout
    import codecs
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    else:
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
    else:
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Windows asyncio configuration for Python 3.10+
if sys.platform.startswith("win"):
    # Use ProactorEventLoop for better performance and subprocess support
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Suppress asyncio warnings that are common on Windows
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="asyncio")
    
    # Configure asyncio for better Windows performance
    if hasattr(asyncio, 'WindowsProactorEventLoopPolicy'):
        # Ensure we're using the most recent policy
        policy = asyncio.WindowsProactorEventLoopPolicy()
        asyncio.set_event_loop_policy(policy)

async def _validate_api(client: BybitClient):
    """Fail-fast API validation like old project"""
    try:
        r = await client.wallet_balance("USDT")
        equity = r["result"]["list"][0].get("totalEquity")
        print(f"[OK] API key validated. Equity: {equity} USDT")
    except Exception as e:
        print("[ERROR] API key/endpoint invalid or timestamp drift. Fix .env / system clock.")
        print(f"   Error: {e}")
        raise

async def main():
    print("Starting Bybit Copybot Pro...")
    print(f"Python {sys.version}")
    print(f"Platform: {sys.platform}")
    
    # Configure asyncio for better performance
    if sys.platform.startswith("win"):
        # Set debug mode for development (remove in production)
        # asyncio.get_event_loop().set_debug(True)
        pass
    
    client = BybitClient()
    try:
        # Validate API keys first (fail-fast like old project)
        await _validate_api(client)
        
        # Start reporting service
        await start_report_scheduler()
        print("[OK] Reporting scheduler started.")
        
        # Start 6-day cleanup scheduler for unfilled orders
        asyncio.create_task(cleanup_scheduler())
        print("[OK] 6-day cleanup scheduler started.")
        
        # Resume open trades: reattach OCO, trailing, hedge monitors
        try:
            await resume_open_trades()
            print("[OK] Open trades resumed.")
        except Exception as e:
            print(f"[WARN] Resume error: {e}")
        
        # Start position manager
        position_manager = await get_position_manager()
        asyncio.create_task(position_manager.start_cleanup_scheduler())
        print("[OK] Position manager started.")
        
        # Start enhanced Telegram client with trade execution
        print("[INFO] Starting enhanced Telegram client with trade execution...")
        await start_enhanced_telegram()
        
    except KeyboardInterrupt:
        print("\n[STOP] Bot stopped by user")
    except Exception as e:
        print(f"[ERROR] Bot error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup on exit
        print("[INFO] Cleaning up...")
        try:
            # Close HTTP client first
            await client.aclose()
            
            # Get all running tasks and cancel them properly
            current_task = asyncio.current_task()
            tasks = [task for task in asyncio.all_tasks() if not task.done() and task is not current_task]
            if tasks:
                print(f"[INFO] Cancelling {len(tasks)} running tasks...")
                for task in tasks:
                    task.cancel()
                # Wait for tasks to complete with timeout to avoid hanging
                await asyncio.wait(tasks, timeout=5.0, return_when=asyncio.ALL_COMPLETED)
        except Exception as e:
            print(f"[WARN] Cleanup error: {e}")
        print("[OK] Cleanup completed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[STOP] Bot stopped")
    except Exception as e:
        print(f"[ERROR] Fatal error: {e}")
        sys.exit(1)

