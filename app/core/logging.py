"""Structured logging with traceId and error mapping."""

import json
import uuid
import traceback
import os
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
# Removed retcodes import - no longer needed

# Create logs directory if it doesn't exist
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

class StructuredLogger:
    """Structured JSON logger with traceId support and file output."""
    
    def __init__(self, name: str):
        self.name = name
        self.trace_id = str(uuid.uuid4())[:8]
        self.log_file = LOG_DIR / f"{name}.log"
    
    def _log(self, level: str, message: str, data: Dict[str, Any] = None):
        """Log structured message to both stdout and file."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "logger": self.name,
            "traceId": self.trace_id,
            "message": message,
            "data": data or {}
        }
        
        log_line = json.dumps(log_entry, ensure_ascii=False)
        
        # Print to stdout (for console viewing)
        print(log_line)
        
        # Write to file (for persistence and auditing per CLIENT REQUIREMENT #21)
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_line + '\n')
        except Exception as e:
            # If file write fails, at least log to stdout
            print(f"ERROR: Failed to write log to file {self.log_file}: {e}")
    
    def info(self, message: str, data: Dict[str, Any] = None):
        """Log info message."""
        self._log("INFO", message, data)
    
    def warning(self, message: str, data: Dict[str, Any] = None):
        """Log warning message."""
        self._log("WARNING", message, data)
    
    def error(self, message: str, data: Dict[str, Any] = None, exc_info: bool = False):
        """Log error message."""
        error_data = data or {}
        if exc_info:
            error_data["exception"] = traceback.format_exc()
        self._log("ERROR", message, error_data)
    
    def critical(self, message: str, data: Dict[str, Any] = None, exc_info: bool = False):
        """Log critical error message."""
        error_data = data or {}
        if exc_info:
            error_data["exception"] = traceback.format_exc()
        self._log("CRITICAL", message, error_data)
    
    def debug(self, message: str, data: Dict[str, Any] = None):
        """Log debug message."""
        self._log("DEBUG", message, data)
    
    def trade_event(self, event_type: str, symbol: str, data: Dict[str, Any] = None):
        """Log trade-specific event."""
        trade_data = {
            "event_type": event_type,
            "symbol": symbol,
            **(data or {})
        }
        self.info(f"Trade event: {event_type}", trade_data)
    
    def bybit_error(self, error_code: int, operation: str, data: Dict[str, Any] = None):
        """Log Bybit API error."""
        error_message = f"Bybit API error {error_code}"
        error_data = {
            "error_code": error_code,
            "error_message": error_message,
            "operation": operation,
            **(data or {})
        }
        self.error(f"Bybit API error: {error_message}", error_data)
    
    def signal_parsed(self, symbol: str, direction: str, channel_name: str, data: Dict[str, Any] = None):
        """Log signal parsing success."""
        signal_data = {
            "symbol": symbol,
            "direction": direction,
            "channel_name": channel_name,
            **(data or {})
        }
        self.info("Signal parsed successfully", signal_data)
    
    def order_placed(self, symbol: str, order_type: str, side: str, qty: str, price: str, order_id: str):
        """Log order placement."""
        order_data = {
            "symbol": symbol,
            "order_type": order_type,
            "side": side,
            "qty": qty,
            "price": price,
            "order_id": order_id
        }
        self.info("Order placed", order_data)
    
    def order_filled(self, symbol: str, order_id: str, fill_qty: str, fill_price: str):
        """Log order fill."""
        fill_data = {
            "symbol": symbol,
            "order_id": order_id,
            "fill_qty": fill_qty,
            "fill_price": fill_price
        }
        self.info("Order filled", fill_data)
    
    def position_opened(self, symbol: str, side: str, size: str, avg_price: str, leverage: int):
        """Log position opening."""
        position_data = {
            "symbol": symbol,
            "side": side,
            "size": size,
            "avg_price": avg_price,
            "leverage": leverage
        }
        self.info("Position opened", position_data)
    
    def position_closed(self, symbol: str, side: str, size: str, pnl: str, reason: str):
        """Log position closing."""
        close_data = {
            "symbol": symbol,
            "side": side,
            "size": size,
            "pnl": pnl,
            "reason": reason
        }
        self.info("Position closed", close_data)
    
    def manager_event(self, manager_type: str, symbol: str, event: str, data: Dict[str, Any] = None):
        """Log manager-specific event."""
        manager_data = {
            "manager_type": manager_type,
            "symbol": symbol,
            "event": event,
            **(data or {})
        }
        self.info(f"{manager_type} event: {event}", manager_data)

# Global logger instances
trade_logger = StructuredLogger("trade")
system_logger = StructuredLogger("system")
telegram_logger = StructuredLogger("telegram")
bybit_logger = StructuredLogger("bybit")