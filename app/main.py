"""Unified entrypoint for Bybit Copybot Pro - STRICT COMPLIANCE MODE."""

import asyncio
import sys
import os
import signal
import warnings
from decimal import Decimal

# Windows-specific asyncio fixes
if sys.platform == "win32":
    # Fix Windows asyncio event loop policy
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    # Suppress Windows asyncio cleanup warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning, module="asyncio")
    # Fix Windows asyncio cleanup issues
    import atexit
    def cleanup_asyncio():
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.stop()
        except:
            pass
    atexit.register(cleanup_asyncio)

# CRITICAL: Environment variables must be set in .env file or system environment
# Do not hardcode secrets in code for security reasons
from app.core.decimal_config import ensure_decimal_precision
from app.core.strict_config import STRICT_CONFIG
from app.core.logging import system_logger
from app.config.settings import (
    BYBIT_ENDPOINT, TIMEZONE, RISK_PER_TRADE, BASE_IM, 
    MAX_CONCURRENT_TRADES, ALWAYS_WHITELIST_CHANNELS
)
from app.telegram.strict_client import start_strict_telegram
from app.reports.strict_scheduler import start_strict_report_scheduler
from app.reports.cleanup import cleanup_scheduler
from app.runtime.resume import resume_open_trades
from app.bybit.client import BybitClient
from app.trade.manager import get_position_manager
from app.core.symbol_registry import get_symbol_registry
from app.core.idempotency import get_idempotency_manager
# from app.core.intelligent_tpsl import initialize_intelligent_tpsl  # OLD VERSION - REMOVED

# Fix Windows console encoding for emojis
if sys.platform.startswith("win"):
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
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="asyncio")

async def _print_config_snapshot():
    """Print configuration snapshot with redacted secrets."""
    from app.config.settings import BYBIT_ENDPOINT, BYBIT_API_KEY, BYBIT_API_SECRET
    
    # Redact API secrets
    redacted_key = f"{BYBIT_API_KEY[:8]}...{BYBIT_API_KEY[-4:]}" if BYBIT_API_KEY else "NOT_SET"
    redacted_secret = f"{BYBIT_API_SECRET[:8]}...{BYBIT_API_SECRET[-4:]}" if BYBIT_API_SECRET else "NOT_SET"
    
    print("🔧 Configuration Snapshot:")
    print(f"   Endpoint: {BYBIT_ENDPOINT}")
    print(f"   API Key: {redacted_key}")
    print(f"   API Secret: {redacted_secret}")
    print(f"   Timezone: {STRICT_CONFIG.timezone}")
    print(f"   Risk per trade: {STRICT_CONFIG.risk_pct * 100}%")
    print(f"   Base IM: {STRICT_CONFIG.im_target} USDT")
    print(f"   Max concurrent trades: {STRICT_CONFIG.max_trades}")

async def _validate_api(client: BybitClient):
    """Fail-fast API validation with strict config."""
    try:
        r = await client.wallet_balance("USDT")
        equity = r["result"]["list"][0].get("totalEquity")
        system_logger.info("API key validated", {'equity': equity})
        print(f"✅ API key validated. Equity: {equity} USDT")
    except Exception as e:
        system_logger.error("API validation failed", {'error': str(e)})
        print("❌ API key/endpoint invalid or timestamp drift. Fix .env / system clock.")
        print(f"   Error: {e}")
        raise

async def _initialize_strict_components():
    """Initialize all strict compliance components."""
    try:
        # Ensure decimal precision
        ensure_decimal_precision()
        system_logger.info("Decimal precision configured")
        
        # Initialize symbol registry
        symbol_registry = await get_symbol_registry()
        await symbol_registry.update_symbols(force=True)
        system_logger.info("Symbol registry initialized")
        
        # Initialize idempotency manager
        idempotency_manager = get_idempotency_manager()
        system_logger.info("Idempotency manager initialized")
        
        # Initialize intelligent TP/SL handler
        from app.core.intelligent_tpsl_fixed_v3 import get_intelligent_tpsl_handler_fixed
        handler = get_intelligent_tpsl_handler_fixed()
        await handler.initialize()
        system_logger.info("Intelligent TP/SL handler initialized")
        
        # Start simulated TP/SL manager (for testnet fallback)
        from app.core.simulated_tpsl import start_simulated_tpsl
        await start_simulated_tpsl()
        system_logger.info("Simulated TP/SL manager started")
        
        # Log configuration
        system_logger.info("Strict configuration loaded", {
            'risk_pct': str(STRICT_CONFIG.risk_pct),
            'im_target': str(STRICT_CONFIG.im_target),
            'max_trades': STRICT_CONFIG.max_trades,
            'timezone': STRICT_CONFIG.timezone,
            'swing_leverage': str(STRICT_CONFIG.swing_leverage),
            'fast_leverage': str(STRICT_CONFIG.fast_leverage),
            'min_dynamic_leverage': str(STRICT_CONFIG.min_dynamic_leverage)
        })
        
        print("✅ Strict compliance components initialized")
        
    except Exception as e:
        system_logger.error(f"Failed to initialize strict components: {e}", exc_info=True)
        raise

async def _validate_strict_requirements():
    """Validate all strict requirements are met."""
    try:
        # Validate configuration
        if STRICT_CONFIG.risk_pct <= 0 or STRICT_CONFIG.risk_pct > 0.1:
            raise ValueError("Risk percentage must be between 0 and 10%")
        
        if STRICT_CONFIG.im_target <= 0 or STRICT_CONFIG.im_target > 1000:
            raise ValueError("IM target must be between 0 and 1000 USDT")
        
        if STRICT_CONFIG.max_trades <= 0 or STRICT_CONFIG.max_trades > 1000:
            raise ValueError("Max trades must be between 0 and 1000")
        
        # Validate leverage policy
        if not STRICT_CONFIG.is_leverage_in_forbidden_gap(Decimal("6.5")):
            raise ValueError("Forbidden leverage gap validation failed - 6.5 should be forbidden")
        
        # Validate timezone
        try:
            tz = STRICT_CONFIG.get_timezone()
            system_logger.info(f"Timezone validated: {tz}")
        except Exception as e:
            raise ValueError(f"Invalid timezone: {e}")
        
        system_logger.info("All strict requirements validated")
        print("✅ All strict requirements validated")
        
    except Exception as e:
        system_logger.error(f"Strict requirements validation failed: {e}", exc_info=True)
        raise

async def main():
    """Main function with strict compliance."""
    print("🚀 Bybit Copybot Pro - STRICT COMPLIANCE MODE")
    print(f"Python {sys.version}")
    print(f"Platform: {sys.platform}")
    
    # Print configuration snapshot
    await _print_config_snapshot()
    
    # Configure asyncio for better performance
    if sys.platform.startswith("win"):
        pass  # Already configured above
    
    try:
        # Reset circuit breaker on startup
        from app.core.errors import breaker_reset
        breaker_reset()
        
        # Initialize strict components
        await _initialize_strict_components()
        
        # Validate strict requirements
        await _validate_strict_requirements()
        
        # Initialize Bybit client (singleton)
        from app.bybit.client import get_bybit_client
        client = get_bybit_client()
        
        # Validate API keys first (fail-fast)
        await _validate_api(client)
        
        # Start strict report scheduler (exact client timing)
        await start_strict_report_scheduler()
        print("✅ Strict report scheduler started (Daily 08:00, Weekly Sat 22:00)")
        
        # Start 6-day cleanup scheduler for unfilled orders
        asyncio.create_task(cleanup_scheduler())
        print("✅ 6-day cleanup scheduler started")
        
        # Resume open trades: reattach OCO, trailing, hedge monitors
        try:
            await resume_open_trades()
            print("✅ Open trades resumed")
        except Exception as e:
            system_logger.warning(f"Resume error: {e}")
            print(f"⚠️ Resume error: {e}")
        
        # Start position manager
        position_manager = await get_position_manager()
        asyncio.create_task(position_manager.start_cleanup_scheduler())
        print("✅ Position manager started")
        
        # Start Bybit WebSocket for real-time updates (if available)
        try:
            from app.bybit.websocket import get_websocket
            ws = await get_websocket()
            print("✅ Bybit WebSocket started for real-time updates")
        except Exception as e:
            print(f"⚠️ WebSocket not available: {e}")
            print("ℹ️ Bot will use REST API polling for updates")
        
        # Start advanced report scheduler
        try:
            from app.reports.scheduler_v2 import get_report_scheduler
            report_scheduler = await get_report_scheduler()
            await report_scheduler.start()
            print("✅ Advanced report scheduler started (Daily 08:00, Weekly Sat 22:00 Stockholm)")
        except Exception as e:
            print(f"⚠️ Report scheduler not available: {e}")
            print("ℹ️ Reports will not be automatically generated")
        
        # Emit "BOOT OK" message with trace_id
        system_logger.info("BOOT OK", {
            'endpoint': BYBIT_ENDPOINT,
            'timezone': TIMEZONE,
            'risk_pct': str(RISK_PER_TRADE),
            'base_im': str(BASE_IM),
            'max_trades': MAX_CONCURRENT_TRADES,
            'whitelist_channels': ALWAYS_WHITELIST_CHANNELS
        })
        print("🚀 BOOT OK - All systems initialized")
        
        # Start strict Telegram client with all compliance features
        system_logger.info("Starting strict Telegram client with ALL COMPLIANCE FEATURES", {
            'features': [
                'Message sequencing: No Telegram until Bybit confirms',
                f'Order types: 100% Limit entries ({STRICT_CONFIG.entry_time_in_force} for precise waiting), 100% Reduce-Only exits',
                'Leverage policy: SWING x6, FAST x10, DYNAMIC ≥7.5',
                'Strategies: BE, Pyramid, Trailing, Hedge, Re-entry',
                'Reports: Daily 08:00, Weekly Sat 22:00 Stockholm time',
                'Max trades: 100 concurrent limit',
                'Swedish templates: All messages in Swedish',
                'Idempotency: 90-second sliding window',
                'Symbol validation: USDT perps only with quantization',
                'Decimal precision: 28-digit precision, no floats'
            ]
        })
        
        await start_strict_telegram()
        
    except KeyboardInterrupt:
        system_logger.info("Bot stopped by user")
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        system_logger.error(f"Bot error: {e}", exc_info=True)
        print(f"❌ Bot error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup on exit
        system_logger.info("Starting cleanup process")
        try:
            # Close HTTP client first
            await client.aclose()
            
            # Stop report scheduler
            from app.reports.strict_scheduler import stop_strict_report_scheduler
            await stop_strict_report_scheduler()
            
            # Clean up resume tasks
            from app.runtime.resume import cleanup_resume_tasks
            await cleanup_resume_tasks()
            
            # Clean up memory resources
            from app.core.memory_manager import cleanup_resources
            cleanup_results = await cleanup_resources()
            system_logger.info(f"Memory cleanup completed: {cleanup_results}")
            
            # Stop WebSocket (if available)
            try:
                from app.bybit.websocket import stop_websocket
                await stop_websocket()
            except Exception as e:
                print(f"⚠️ WebSocket cleanup error: {e}")
            
            # Stop report scheduler (if available)
            try:
                from app.reports.scheduler_v2 import get_report_scheduler
                report_scheduler = await get_report_scheduler()
                await report_scheduler.stop()
            except Exception as e:
                print(f"⚠️ Report scheduler cleanup error: {e}")
            
            # Stop simulated TP/SL manager
            try:
                from app.core.simulated_tpsl import stop_simulated_tpsl
                await stop_simulated_tpsl()
            except Exception as e:
                print(f"⚠️ Simulated TP/SL cleanup error: {e}")
                
            # Get all running tasks and cancel them properly
            current_task = asyncio.current_task()
            tasks = [task for task in asyncio.all_tasks() if not task.done() and task is not current_task]
            if tasks:
                system_logger.info(f"Cancelling {len(tasks)} running tasks")
                for task in tasks:
                    task.cancel()
                # Wait for tasks to complete with timeout to avoid hanging
                await asyncio.wait(tasks, timeout=5.0, return_when=asyncio.ALL_COMPLETED)
        except Exception as e:
            system_logger.error(f"Cleanup error: {e}", exc_info=True)
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
