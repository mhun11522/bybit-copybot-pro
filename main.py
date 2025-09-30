from app.core import decimal_ctx  # set global Decimal precision early
import asyncio
import sys
from app import settings
from app.telegram_client import client
from app.reports.service import ReportService
from app.storage.db import init_db
from app.runtime.resume import resume_open_trades
from app.order_cleanup import start_order_cleanup
from app.margin_mode import MarginModeManager
from app.logging_system import log_system_event, logger
from app.bybit_client import BybitClient

if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

async def main():
    print("🚀 Starting Bybit Copybot Pro...")
    
    # Initialize logging
    log_system_event("SYSTEM_START", {"version": "1.0.0", "python_version": sys.version})
    
    # Initialize database
    await init_db()
    log_system_event("DATABASE_INITIALIZED", {})

    # Initialize Bybit client
    bybit_client = BybitClient()
    
    # Initialize margin mode manager
    margin_manager = MarginModeManager(bybit_client)
    log_system_event("MARGIN_MODE_MANAGER_INITIALIZED", {"mode": settings.MARGIN_MODE})

    # Start order cleanup system
    await start_order_cleanup(bybit_client)
    log_system_event("ORDER_CLEANUP_STARTED", {"cleanup_days": settings.ORDER_CLEANUP_DAYS})

    telegram_ready = settings.TELEGRAM_API_ID > 0 and bool(settings.TELEGRAM_API_HASH)

    if telegram_ready:
        print("🔌 Telegram credentials detected. Connecting...")
        await client.start()
        print("✅ Connected to Telegram. Waiting for messages…")
        log_system_event("TELEGRAM_CONNECTED", {})
    else:
        print("⚠️ TELEGRAM_API_ID/HASH not set. Running in offline mode (no Telegram connection).")
        log_system_event("TELEGRAM_OFFLINE_MODE", {})

    # Resume open trades: reattach OCO, trailing, hedge monitors
    try:
        await resume_open_trades()
        log_system_event("OPEN_TRADES_RESUMED", {})
    except Exception as e:
        print("Resume error:", e)
        log_system_event("RESUME_ERROR", {"error": str(e)})

    # Start reporting service
    report = ReportService(db=None, telegram_client=client)
    report.start()
    print("📊 Reporting scheduler started.")
    log_system_event("REPORTING_STARTED", {})

    if telegram_ready:
        print("✅ Bot + reporting running... (waiting for Telegram messages)")
        log_system_event("BOT_RUNNING", {"mode": "telegram"})
        await client.run_until_disconnected()
    else:
        print("✅ Bot running in offline mode. Press Ctrl+C to exit.")
        log_system_event("BOT_RUNNING", {"mode": "offline"})
        # Keep the process alive so scheduler continues to run
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())

