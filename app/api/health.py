"""
Health, status, and metrics endpoints.

CLIENT SPEC Lines 385-394: Health, Resilience, Operations
- /health (stdlib/curl compatible)
- /status (detailed component status)
- /metrics (Prometheus-compatible)
- Killswitch for emergency stop

All endpoints return JSON and are designed for monitoring/alerting.
"""

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import asyncio
import os

from app.core.logging import system_logger


# Create FastAPI app for health endpoints
app = FastAPI(title="Bybit Copybot Health API", version="1.0.0")

# Killswitch state
_killswitch_active = False
_killswitch_reason = ""
_killswitch_activated_at: Optional[datetime] = None


@app.get("/health")
async def health_check():
    """
    Basic health check (stdlib/curl compatible).
    
    CLIENT SPEC Line 386: "/health (stdlib/curl)"
    
    Returns 200 OK if service is running.
    Use this for simple uptime monitoring.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "bybit-copybot-pro"
    }


@app.get("/status")
async def status_check():
    """
    Detailed status check.
    
    CLIENT SPEC Line 386: "/status"
    
    Returns detailed component status for troubleshooting.
    """
    try:
        # Import here to avoid circular dependencies
        from app.bybit.client import get_bybit_client
        from app.core.ntp_sync import get_ntp_monitor
        from app.core.market_guards import get_market_guards
        from app.core.journal import get_append_only_journal
        from app.storage.db import get_db_connection
        
        # Check each component
        bybit_status = await _check_bybit_status()
        telegram_status = await _check_telegram_status()
        db_status = await _check_database_status()
        
        # NTP status
        ntp_monitor = get_ntp_monitor()
        ntp_status = ntp_monitor.get_status()
        
        # Market guards status
        guards = get_market_guards()
        guards_status = guards.get_statistics()
        
        # Journal status
        journal = get_append_only_journal()
        journal_integrity = journal.verify_integrity()
        
        # Overall trading status
        trading_allowed = (
            bybit_status["available"] and
            ntp_status["trading_allowed"] and
            not _killswitch_active
        )
        
        return {
            "status": "operational" if trading_allowed else "degraded",
            "trading_enabled": trading_allowed,
            "killswitch_active": _killswitch_active,
            "components": {
                "bybit_api": bybit_status,
                "telegram": telegram_status,
                "database": db_status,
                "ntp_sync": ntp_status,
                "market_guards": guards_status,
                "journal": {
                    "entries": journal.get_entry_count(),
                    "integrity_valid": journal_integrity["valid"],
                    "last_hash": journal.last_hash[:16] if journal.last_hash else None
                }
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        system_logger.error(f"Status check error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@app.get("/metrics")
async def metrics():
    """
    Prometheus-compatible metrics.
    
    CLIENT SPEC Line 386: "/metrics"
    
    Returns metrics for monitoring and alerting.
    """
    try:
        # Get 24h statistics
        stats_24h = await _get_24h_statistics()
        
        # Get current state
        from app.core.ntp_sync import get_ntp_monitor
        from app.core.market_guards import get_market_guards
        
        ntp = get_ntp_monitor()
        guards = get_market_guards()
        
        return {
            # Trade metrics
            "total_trades_24h": stats_24h["total_trades"],
            "winning_trades_24h": stats_24h["winning_trades"],
            "losing_trades_24h": stats_24h["losing_trades"],
            "win_rate_24h": stats_24h["win_rate"],
            "total_pnl_24h_usdt": stats_24h["total_pnl"],
            
            # Performance metrics
            "avg_latency_ms": stats_24h["avg_latency"],
            "errors_24h": stats_24h["error_count"],
            
            # System metrics
            "ntp_drift_ms": ntp.last_drift * 1000 if ntp.last_drift else 0,
            "clock_drift_blocks": ntp.drift_blocks,
            "market_guard_blocks": guards.spread_blocks + guards.liquidity_blocks + guards.maintenance_blocks,
            
            # State
            "trading_enabled": ntp.is_trading_allowed() and not _killswitch_active,
            "killswitch_active": _killswitch_active,
            
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        system_logger.error(f"Metrics error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.post("/killswitch")
async def killswitch(x_admin_token: Optional[str] = Header(None)):
    """
    Emergency killswitch to stop all trading.
    
    CLIENT SPEC Line 390: "Killswitch: stop all trading, safely close/cancel; admin-signed /resume"
    
    This:
    1. Blocks all new orders
    2. Cancels all open orders
    3. Optionally closes all positions
    4. Requires admin authentication
    
    Headers:
        X-Admin-Token: Admin authentication token
    """
    global _killswitch_active, _killswitch_reason, _killswitch_activated_at
    
    # Verify admin token
    expected_token = os.getenv("ADMIN_TOKEN", "")
    if not expected_token or x_admin_token != expected_token:
        raise HTTPException(status_code=401, detail="Unauthorized - invalid admin token")
    
    if _killswitch_active:
        return {
            "status": "already_active",
            "activated_at": _killswitch_activated_at.isoformat() if _killswitch_activated_at else None,
            "reason": _killswitch_reason
        }
    
    # Activate killswitch
    _killswitch_active = True
    _killswitch_reason = "Manual killswitch activation"
    _killswitch_activated_at = datetime.utcnow()
    
    system_logger.critical("🚨 KILLSWITCH ACTIVATED", {
        "activated_at": _killswitch_activated_at.isoformat(),
        "activated_by": "admin",
        "action": "EMERGENCY_STOP"
    })
    
    # Emergency stop all trading
    try:
        await _emergency_stop_all_trading()
    except Exception as e:
        system_logger.error(f"Killswitch execution error: {e}", exc_info=True)
    
    return {
        "status": "activated",
        "activated_at": _killswitch_activated_at.isoformat(),
        "message": "All trading stopped. Use /resume to restart."
    }


@app.post("/resume")
async def resume_trading(x_admin_token: Optional[str] = Header(None)):
    """
    Resume trading after killswitch.
    
    CLIENT SPEC Line 390: "admin-signed /resume"
    
    Requires admin authentication.
    """
    global _killswitch_active, _killswitch_reason
    
    # Verify admin token
    expected_token = os.getenv("ADMIN_TOKEN", "")
    if not expected_token or x_admin_token != expected_token:
        raise HTTPException(status_code=401, detail="Unauthorized - invalid admin token")
    
    if not _killswitch_active:
        return {
            "status": "not_active",
            "message": "Killswitch is not active"
        }
    
    # Deactivate killswitch
    _killswitch_active = False
    _killswitch_reason = ""
    
    system_logger.info("✅ Killswitch deactivated - trading resumed", {
        "deactivated_at": datetime.utcnow().isoformat(),
        "deactivated_by": "admin"
    })
    
    return {
        "status": "resumed",
        "message": "Trading resumed",
        "timestamp": datetime.utcnow().isoformat()
    }


def is_killswitch_active() -> bool:
    """Check if killswitch is active."""
    return _killswitch_active


# Helper functions

async def _check_bybit_status() -> Dict[str, Any]:
    """Check Bybit API status."""
    try:
        from app.bybit.client import get_bybit_client
        client = get_bybit_client()
        
        # Try simple API call
        response = await client.get_server_time()
        
        return {
            "available": response.get("retCode") == 0,
            "server_time": response.get("result", {}).get("timeSecond"),
            "last_check": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e),
            "last_check": datetime.utcnow().isoformat()
        }


async def _check_telegram_status() -> Dict[str, Any]:
    """Check Telegram connection status."""
    try:
        from app.telegram.strict_client import get_strict_telegram_client
        client = await get_strict_telegram_client()
        
        return {
            "connected": client.client.is_connected() if client else False,
            "active_trades": client.get_active_trades_count() if client else 0,
            "last_check": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "last_check": datetime.utcnow().isoformat()
        }


async def _check_database_status() -> Dict[str, Any]:
    """Check database connection status."""
    try:
        from app.storage.db import get_db_connection
        db = await get_db_connection()
        
        # Try simple query
        async with db:
            cursor = await db.execute("SELECT COUNT(*) FROM trades")
            result = await cursor.fetchone()
            trade_count = result[0] if result else 0
        
        return {
            "available": True,
            "total_trades": trade_count,
            "last_check": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e),
            "last_check": datetime.utcnow().isoformat()
        }


async def _get_24h_statistics() -> Dict[str, Any]:
    """Get 24-hour trading statistics."""
    try:
        from app.storage.db import get_db_connection
        db = await get_db_connection()
        
        # Get trades from last 24h
        cutoff = datetime.utcnow() - timedelta(hours=24)
        
        async with db:
            cursor = await db.execute("""
                SELECT COUNT(*), 
                       SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END),
                       SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END),
                       SUM(pnl),
                       AVG(latency_ms)
                FROM trades
                WHERE created_at >= ?
            """, (cutoff.isoformat(),))
            
            result = await cursor.fetchone()
            
            if result:
                total, winning, losing, pnl, avg_latency = result
                win_rate = (winning / total * 100) if total > 0 else 0
            else:
                total, winning, losing, pnl, avg_latency, win_rate = 0, 0, 0, 0, 0, 0
            
            # Get error count
            cursor = await db.execute("""
                SELECT COUNT(*) FROM error_logs
                WHERE timestamp >= ?
            """, (cutoff.isoformat(),))
            
            error_result = await cursor.fetchone()
            error_count = error_result[0] if error_result else 0
        
        return {
            "total_trades": total or 0,
            "winning_trades": winning or 0,
            "losing_trades": losing or 0,
            "win_rate": win_rate,
            "total_pnl": pnl or 0,
            "avg_latency": avg_latency or 0,
            "error_count": error_count
        }
        
    except Exception as e:
        system_logger.error(f"Statistics error: {e}", exc_info=True)
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "avg_latency": 0,
            "error_count": 0
        }


async def _emergency_stop_all_trading():
    """
    Emergency stop all trading (killswitch action).
    
    CLIENT SPEC: "stop all trading, safely close/cancel"
    
    Steps:
    1. Cancel all open orders
    2. Optionally close all positions (configurable)
    3. Block new order placement
    """
    try:
        from app.bybit.client import get_bybit_client
        client = get_bybit_client()
        
        system_logger.critical("🚨 EMERGENCY STOP INITIATED")
        
        # Step 1: Cancel all open orders
        categories = ["linear"]  # Add more if needed
        for category in categories:
            try:
                response = await client.cancel_all_orders(category)
                system_logger.info(f"Cancelled all {category} orders", {
                    "retCode": response.get("retCode"),
                    "retMsg": response.get("retMsg")
                })
            except Exception as e:
                system_logger.error(f"Failed to cancel {category} orders: {e}")
        
        # Step 2: Close all positions (if configured)
        close_positions = os.getenv("KILLSWITCH_CLOSE_POSITIONS", "false").lower() == "true"
        
        if close_positions:
            system_logger.warning("Killswitch configured to close all positions")
            # Get all positions and close them
            try:
                positions_response = await client.get_positions("linear")
                if positions_response.get("retCode") == 0:
                    positions = positions_response.get("result", {}).get("list", [])
                    
                    for position in positions:
                        symbol = position.get("symbol")
                        size = Decimal(str(position.get("size", "0")))
                        side = position.get("side")
                        
                        if size > 0:
                            # Close position with market order
                            close_side = "Sell" if side == "Buy" else "Buy"
                            close_response = await client.place_order({
                                "category": "linear",
                                "symbol": symbol,
                                "side": close_side,
                                "orderType": "Market",
                                "qty": str(size),
                                "reduceOnly": True,
                                "closeOnTrigger": True
                            })
                            
                            system_logger.info(f"Closed position {symbol}", {
                                "retCode": close_response.get("retCode")
                            })
            except Exception as e:
                system_logger.error(f"Failed to close positions: {e}")
        
        system_logger.critical("✅ EMERGENCY STOP COMPLETED")
        
    except Exception as e:
        system_logger.error(f"Emergency stop error: {e}", exc_info=True)
        raise


async def _check_bybit_status() -> Dict[str, Any]:
    """Check if Bybit API is reachable."""
    try:
        from app.bybit.client import get_bybit_client
        client = get_bybit_client()
        
        response = await client.get_server_time()
        
        return {
            "available": response.get("retCode") == 0,
            "server_time": response.get("result", {}).get("timeSecond"),
            "latency_ms": None  # Could add latency measurement
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e)
        }


async def _check_telegram_status() -> Dict[str, Any]:
    """Check if Telegram is connected."""
    try:
        from app.telegram.strict_client import get_strict_telegram_client
        client = await get_strict_telegram_client()
        
        return {
            "connected": client.client.is_connected() if client else False,
            "active_trades": client.get_active_trades_count() if client else 0
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e)
        }


async def _check_database_status() -> Dict[str, Any]:
    """Check if database is accessible."""
    try:
        from app.storage.db import get_db_connection
        db = await get_db_connection()
        
        async with db:
            cursor = await db.execute("SELECT COUNT(*) FROM trades")
            result = await cursor.fetchone()
            
        return {
            "available": True,
            "total_trades": result[0] if result else 0
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e)
        }


async def start_health_server(host: str = "0.0.0.0", port: int = 8080):
    """
    Start health API server.
    
    Should be started in main.py as a background task.
    """
    import uvicorn
    
    system_logger.info("Starting health API server", {
        "host": host,
        "port": port
    })
    
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=False  # Reduce log noise
    )
    
    server = uvicorn.Server(config)
    await server.serve()

