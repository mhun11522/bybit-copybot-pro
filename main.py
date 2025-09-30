import asyncio
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
        try:
            # Use a more robust connection approach
            print("   Connecting to Telegram...")
            
            # Try to connect with timeout
            try:
                await asyncio.wait_for(client.connect(), timeout=10.0)
            except asyncio.TimeoutError:
                print("⏰ Connection timeout, trying direct connect...")
                await client.connect()
            
            if not await client.is_user_authorized():
                print("❌ User not authorized. Please run telegram_auth.py first.")
                print("🔄 Continuing in offline mode...")
                telegram_ready = False
                log_system_event("TELEGRAM_NOT_AUTHORIZED", {})
            else:
                print("✅ Connected to Telegram. Monitoring for signals...")
                print("📱 Bot is now listening for signals from your channels!")
                log_system_event("TELEGRAM_CONNECTED", {})
                
        except Exception as e:
            print(f"❌ Telegram connection error: {e}")
            print("🔄 Continuing in offline mode...")
            telegram_ready = False
            log_system_event("TELEGRAM_CONNECTION_ERROR", {"error": str(e)})
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
    await start_report_scheduler()
    print("📊 Reporting scheduler started.")
    log_system_event("REPORTING_STARTED", {})

    if telegram_ready and client.is_connected():
        print("✅ Bot + reporting running... (waiting for Telegram messages)")
        print("📡 Monitoring channels for trading signals...")
        print("🎯 Ready to detect and process signals!")
        log_system_event("BOT_RUNNING", {"mode": "telegram"})
        try:
            await client.run_until_disconnected()
        except Exception as e:
            print(f"❌ Telegram connection lost: {e}")
            log_system_event("TELEGRAM_DISCONNECTED", {"error": str(e)})
    else:
        if telegram_ready:
            print("⚠️ Telegram connection failed. Running in offline mode.")
            print("💡 To fix: Run 'python telegram_auth.py' to authenticate")
            log_system_event("BOT_RUNNING", {"mode": "offline_fallback"})
        else:
            print("✅ Bot running in offline mode. Press Ctrl+C to exit.")
            log_system_event("BOT_RUNNING", {"mode": "offline"})
        
        # Keep the process alive so scheduler continues to run
        print("🔄 Bot will continue running in offline mode...")
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())

