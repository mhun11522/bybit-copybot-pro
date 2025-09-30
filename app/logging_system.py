from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from app import settings


class StructuredLogger:
    def __init__(self, name: str = "bybit_bot"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Create file handler
        file_handler = logging.FileHandler(settings.LOG_FILE)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def log_trade_event(self, event_type: str, trade_id: str, symbol: str, 
                       data: Dict[str, Any], level: str = "INFO"):
        """Log a trade-related event with structured data."""
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "trade_id": trade_id,
            "symbol": symbol,
            "data": data,
            "correlation_id": str(uuid.uuid4())[:8]
        }
        
        log_message = json.dumps(log_data, default=str)
        
        if level.upper() == "ERROR":
            self.logger.error(log_message)
        elif level.upper() == "WARNING":
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)

    def log_signal_event(self, event_type: str, channel_id: int, symbol: str, 
                        data: Dict[str, Any], level: str = "INFO"):
        """Log a signal-related event with structured data."""
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "channel_id": channel_id,
            "symbol": symbol,
            "data": data,
            "correlation_id": str(uuid.uuid4())[:8]
        }
        
        log_message = json.dumps(log_data, default=str)
        
        if level.upper() == "ERROR":
            self.logger.error(log_message)
        elif level.upper() == "WARNING":
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)

    def log_system_event(self, event_type: str, data: Dict[str, Any], level: str = "INFO"):
        """Log a system-related event with structured data."""
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "data": data,
            "correlation_id": str(uuid.uuid4())[:8]
        }
        
        log_message = json.dumps(log_data, default=str)
        
        if level.upper() == "ERROR":
            self.logger.error(log_message)
        elif level.upper() == "WARNING":
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)


# Global logger instance
logger = StructuredLogger()

# Convenience functions
def log_trade_start(trade_id: str, symbol: str, direction: str, mode: str, 
                   channel_name: str, entries: list, leverage: int):
    """Log trade start event."""
    logger.log_trade_event(
        "TRADE_START",
        trade_id,
        symbol,
        {
            "direction": direction,
            "mode": mode,
            "channel_name": channel_name,
            "entries": [str(e) for e in entries],
            "leverage": leverage
        }
    )

def log_trade_end(trade_id: str, symbol: str, pnl_usdt: float, pnl_pct: float, 
                 exit_reason: str):
    """Log trade end event."""
    logger.log_trade_event(
        "TRADE_END",
        trade_id,
        symbol,
        {
            "pnl_usdt": pnl_usdt,
            "pnl_pct": pnl_pct,
            "exit_reason": exit_reason
        }
    )

def log_signal_received(channel_id: int, symbol: str, direction: str, 
                       channel_name: str, signal_text: str):
    """Log signal received event."""
    logger.log_signal_event(
        "SIGNAL_RECEIVED",
        channel_id,
        symbol,
        {
            "direction": direction,
            "channel_name": channel_name,
            "signal_text": signal_text[:100] + "..." if len(signal_text) > 100 else signal_text
        }
    )

def log_order_placed(trade_id: str, symbol: str, order_type: str, 
                    side: str, qty: str, price: str, order_id: str):
    """Log order placed event."""
    logger.log_trade_event(
        "ORDER_PLACED",
        trade_id,
        symbol,
        {
            "order_type": order_type,
            "side": side,
            "qty": qty,
            "price": price,
            "order_id": order_id
        }
    )

def log_error(trade_id: str, symbol: str, error_type: str, error_message: str, 
              context: Dict[str, Any] = None):
    """Log error event."""
    logger.log_trade_event(
        "ERROR",
        trade_id,
        symbol,
        {
            "error_type": error_type,
            "error_message": error_message,
            "context": context or {}
        },
        "ERROR"
    ) 