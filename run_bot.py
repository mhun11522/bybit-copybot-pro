#!/usr/bin/env python3
"""
Bybit Copybot Pro - Main Runner
This script runs the bot with proper error handling and fallback modes
"""
import asyncio
import sys
import signal
from app.telegram_client import client
from app.bybit_client import BybitClient
from app.storage.db import init_db
from app.margin_mode import MarginModeManager
from app.order_cleanup import start_order_cleanup
from app.reports.service import ReportService
# from app.trade.resume import resume_open_trades  # Not available
from app.logging_system import log_system_event, logger
from app import settings

if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass

# Global flag for graceful shutdown
shutdown_requested = False

def signal_handler(signum, frame):
    global shutdown_requested
    print(f"\n🛑 Shutdown signal received ({signum})")
    shutdown_requested = True

async def main():
    global shutdown_requested
    
    print("🚀 Starting Bybit Copybot Pro...")
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize logging
    log_system_event("SYSTEM_START", {"version": "1.0.0", "python_version": sys.version})
    
    # Initialize database
    await init_db()
    log_system_event("DATABASE_INITIALIZED", {})
    
    # Initialize Bybit client
    bybit_client = BybitClient(
        api_key=settings.BYBIT_API_KEY,
        api_secret=settings.BYBIT_API_SECRET,
        endpoint=settings.BYBIT_ENDPOINT
    )
    log_system_event("BYBIT_CLIENT_INITIALIZED", {})
    
    # Initialize margin mode manager
    margin_manager = MarginModeManager(bybit_client)
    await margin_manager.ensure_isolated_margin()
    log_system_event("MARGIN_MODE_MANAGER_INITIALIZED", {"mode": "isolated"})
    
    # Start order cleanup system
    await start_order_cleanup(bybit_client)
    log_system_event("ORDER_CLEANUP_STARTED", {"cleanup_days": settings.ORDER_CLEANUP_DAYS})
    
    # Try Telegram connection
    telegram_connected = False
    if settings.TELEGRAM_API_ID > 0 and bool(settings.TELEGRAM_API_HASH):
        print("🔌 Attempting Telegram connection...")
        try:
            await client.connect()
            if await client.is_user_authorized():
                print("✅ Connected to Telegram. Monitoring for signals...")
                telegram_connected = True
                log_system_event("TELEGRAM_CONNECTED", {})
            else:
                print("❌ User not authorized. Please run 'python telegram_auth.py' first.")
                log_system_event("TELEGRAM_NOT_AUTHORIZED", {})
        except Exception as e:
            print(f"❌ Telegram connection failed: {e}")
            log_system_event("TELEGRAM_CONNECTION_ERROR", {"error": str(e)})
    
    if not telegram_connected:
        print("⚠️ Running in offline mode (no Telegram connection)")
        log_system_event("TELEGRAM_OFFLINE_MODE", {})
    
    # Resume open trades (if available)
    # try:
    #     await resume_open_trades()
    #     logger.info("OPEN_TRADES_RESUMED", {})
    # except Exception as e:
    #     print(f"Resume error: {e}")
    #     logger.info("RESUME_ERROR", {"error": str(e)})
    
    # Start reporting service
    report = ReportService(db=None, telegram_client=client if telegram_connected else None)
    report.start()
    print("📊 Reporting scheduler started.")
    log_system_event("REPORTING_STARTED", {})
    
    # Main loop
    if telegram_connected:
        print("✅ Bot running with Telegram connection. Waiting for signals...")
        print("   Press Ctrl+C to stop")
        log_system_event("BOT_RUNNING", {"mode": "telegram"})
        
        try:
            # Keep the bot running until shutdown
            while not shutdown_requested:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Shutdown requested by user")
        finally:
            await client.disconnect()
            print("✅ Disconnected from Telegram")
    else:
        print("✅ Bot running in offline mode. Press Ctrl+C to stop")
        print("💡 To enable Telegram: Run 'python telegram_auth.py' then restart")
        log_system_event("BOT_RUNNING", {"mode": "offline"})
        
        try:
            # Keep the bot running until shutdown
            while not shutdown_requested:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Shutdown requested by user")
    
    print("👋 Bybit Copybot Pro stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)