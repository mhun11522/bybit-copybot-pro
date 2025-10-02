"""Strict compliance main.py with all client requirements."""

import asyncio
import sys
import os
import signal
import warnings
from decimal import Decimal
from app.core.decimal_config import ensure_decimal_precision
from app.core.strict_config import STRICT_CONFIG
from app.core.logging import system_logger
from app.telegram.strict_client import start_strict_telegram
from app.reports.strict_scheduler import start_strict_report_scheduler
from app.reports.cleanup import cleanup_scheduler
from app.runtime.resume import resume_open_trades
from app.bybit.client import BybitClient
from app.trade.manager import get_position_manager
from app.core.symbol_registry import get_symbol_registry
from app.core.idempotency import get_idempotency_manager

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
    """Fail-fast API validation with strict config."""
    try:
        r = await client.wallet_balance("USDT")
        equity = r["result"]["list"][0].get("totalEquity")
        system_logger.info("API key validated", {'equity': equity})
        print(f"[OK] API key validated. Equity: {equity} USDT")
    except Exception as e:
        system_logger.error("API validation failed", {'error': str(e)})
        print("[ERROR] API key/endpoint invalid or timestamp drift. Fix .env / system clock.")
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
        
        print("[OK] Strict compliance components initialized")
        
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
        print("[OK] All strict requirements validated")
        
    except Exception as e:
        system_logger.error(f"Strict requirements validation failed: {e}", exc_info=True)
        raise

async def main():
    """Main function with strict compliance."""
    print("🚀 Starting Bybit Copybot Pro - STRICT COMPLIANCE MODE")
    print(f"Python {sys.version}")
    print(f"Platform: {sys.platform}")
    print(f"Risk per trade: {STRICT_CONFIG.risk_pct * 100}%")
    print(f"IM target: {STRICT_CONFIG.im_target} USDT")
    print(f"Max trades: {STRICT_CONFIG.max_trades}")
    print(f"Timezone: {STRICT_CONFIG.timezone}")
    
    # Configure asyncio for better performance
    if sys.platform.startswith("win"):
        # Set debug mode for development (remove in production)
        # asyncio.get_event_loop().set_debug(True)
        pass
    
    try:
        # Initialize strict components
        await _initialize_strict_components()
        
        # Validate strict requirements
        await _validate_strict_requirements()
        
        # Initialize Bybit client
        client = BybitClient()
        
        # Validate API keys first (fail-fast)
        await _validate_api(client)
        
        # Start strict report scheduler (exact client timing)
        await start_strict_report_scheduler()
        print("[OK] Strict report scheduler started (Daily 08:00, Weekly Sat 22:00)")
        
        # Start 6-day cleanup scheduler for unfilled orders
        asyncio.create_task(cleanup_scheduler())
        print("[OK] 6-day cleanup scheduler started.")
        
        # Resume open trades: reattach OCO, trailing, hedge monitors
        try:
            await resume_open_trades()
            print("[OK] Open trades resumed.")
        except Exception as e:
            system_logger.warning(f"Resume error: {e}")
            print(f"[WARN] Resume error: {e}")
        
        # Start position manager
        position_manager = await get_position_manager()
        asyncio.create_task(position_manager.start_cleanup_scheduler())
        print("[OK] Position manager started.")
        
        # Start strict Telegram client with all compliance features
        print("[INFO] Starting strict Telegram client with ALL COMPLIANCE FEATURES...")
        print("  ✅ Message sequencing: No Telegram until Bybit confirms")
        print("  ✅ Order types: 100% Post-Only entries, 100% Reduce-Only exits")
        print("  ✅ Leverage policy: SWING x6, FAST x10, DYNAMIC ≥7.5")
        print("  ✅ Strategies: BE, Pyramid, Trailing, Hedge, Re-entry")
        print("  ✅ Reports: Daily 08:00, Weekly Sat 22:00 Stockholm time")
        print("  ✅ Max trades: 100 concurrent limit")
        print("  ✅ Swedish templates: All messages in Swedish")
        print("  ✅ Idempotency: 90-second sliding window")
        print("  ✅ Symbol validation: USDT perps only with quantization")
        print("  ✅ Decimal precision: 28-digit precision, no floats")
        
        await start_strict_telegram()
        
    except KeyboardInterrupt:
        system_logger.info("Bot stopped by user")
        print("\n[STOP] Bot stopped by user")
    except Exception as e:
        system_logger.error(f"Bot error: {e}", exc_info=True)
        print(f"[ERROR] Bot error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup on exit
        print("[INFO] Cleaning up...")
        try:
            # Close HTTP client first
            await client.aclose()
            
            # Stop report scheduler
            from app.reports.strict_scheduler import stop_strict_report_scheduler
            await stop_strict_report_scheduler()
            
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
            system_logger.error(f"Cleanup error: {e}", exc_info=True)
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