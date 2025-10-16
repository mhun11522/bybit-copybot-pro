"""
Timeline logger for ACK-Gate compliance proof.

CLIENT SPEC Line 293: "PASS evidence: timeline logs proving Telegram is emitted 
strictly after the corresponding Bybit ack/WS event."

This logger creates a microsecond-precision timeline of all events to prove:
1. Bybit request sent
2. Bybit acknowledgment received (retCode=0)
3. Telegram message sent

The timeline can be analyzed to verify no Telegram message precedes its Bybit ack.
"""

import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional
import json
from pathlib import Path
import pytz

from app.core.logging import system_logger

class TimelineEvent:
    """Single timeline event with microsecond precision."""
    
    def __init__(self, operation_id: str, event_type: str, data: Dict[str, Any]):
        self.operation_id = operation_id
        self.event_type = event_type
        self.data = data
        self.timestamp_utc = datetime.now(pytz.UTC)
        self.timestamp_unix = self.timestamp_utc.timestamp()
        self.timestamp_iso = self.timestamp_utc.isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "operation_id": self.operation_id,
            "event_type": self.event_type,
            "timestamp_utc": self.timestamp_iso,
            "timestamp_unix": self.timestamp_unix,
            "data": self.data
        }


class TimelineLogger:
    """
    Timeline logger for compliance proof.
    
    Logs sequence of events:
    1. BYBIT_REQUEST: When request sent to Bybit
    2. BYBIT_ACK: When Bybit responds (with retCode)
    3. TELEGRAM_SEND: When Telegram message sent
    
    Provides verification that Telegram always follows Bybit ack.
    """
    
    def __init__(self, timeline_file: Path = None):
        self.timeline_file = timeline_file or Path("logs/timeline.jsonl")
        self.timeline_file.parent.mkdir(parents=True, exist_ok=True)
        self._events: Dict[str, list] = {}  # operation_id → [events]
        self._lock = asyncio.Lock()
    
    async def log_bybit_request(self, operation_id: str, operation: str, 
                                data: Dict[str, Any]) -> None:
        """
        Log Bybit API request.
        
        Args:
            operation_id: Unique operation identifier
            operation: Operation type (e.g., "place_order", "set_leverage")
            data: Request payload
        """
        event = TimelineEvent(operation_id, "BYBIT_REQUEST", {
            "operation": operation,
            "symbol": data.get("symbol"),
            "side": data.get("side"),
            "orderType": data.get("orderType"),
            "qty": data.get("qty"),
            "price": data.get("price")
        })
        
        await self._append_event(event)
        
        system_logger.debug("Timeline: Bybit request", event.to_dict())
    
    async def log_bybit_ack(self, operation_id: str, retCode: int, 
                            response: Dict[str, Any]) -> None:
        """
        Log Bybit acknowledgment.
        
        Args:
            operation_id: Operation identifier (must match request)
            retCode: Bybit return code (0 = success)
            response: Full Bybit response
        """
        event = TimelineEvent(operation_id, "BYBIT_ACK", {
            "retCode": retCode,
            "retMsg": response.get("retMsg"),
            "orderId": response.get("result", {}).get("orderId"),
            "orderLinkId": response.get("result", {}).get("orderLinkId"),
            "success": (retCode == 0)
        })
        
        await self._append_event(event)
        
        system_logger.debug("Timeline: Bybit ack", event.to_dict())
    
    async def log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Log a generic timeline event.
        
        Args:
            event_type: Type of event (e.g., "BYBIT_REQUEST", "BYBIT_ACK", "TELEGRAM_SEND")
            data: Event data dictionary
        """
        operation_id = data.get("operation_id", "unknown")
        event = TimelineEvent(operation_id, event_type, data)
        
        await self._append_event(event)
        
        system_logger.debug(f"Timeline: {event_type}", event.to_dict())
    
    async def log_telegram_send(self, operation_id: str, message_id: Optional[int],
                                template_name: str, symbol: str) -> None:
        """
        Log Telegram message sent.
        
        Args:
            operation_id: Operation identifier (must match Bybit request/ack)
            message_id: Telegram message ID (None if failed)
            template_name: Template used
            symbol: Trading symbol
        """
        event = TimelineEvent(operation_id, "TELEGRAM_SEND", {
            "message_id": message_id,
            "template_name": template_name,
            "symbol": symbol,
            "success": (message_id is not None)
        })
        
        await self._append_event(event)
        
        system_logger.debug("Timeline: Telegram send", event.to_dict())
    
    async def _append_event(self, event: TimelineEvent) -> None:
        """Append event to timeline (thread-safe)."""
        async with self._lock:
            # Add to in-memory timeline
            if event.operation_id not in self._events:
                self._events[event.operation_id] = []
            self._events[event.operation_id].append(event)
            
            # Append to file for persistence
            with open(self.timeline_file, 'a') as f:
                f.write(json.dumps(event.to_dict()) + '\n')
                f.flush()
    
    async def verify_sequence(self, operation_id: str) -> Dict[str, Any]:
        """
        Verify correct sequence for an operation.
        
        CLIENT SPEC: Must prove sequence is: REQUEST → ACK (retCode=0) → TELEGRAM
        
        Args:
            operation_id: Operation to verify
        
        Returns:
            {
                "valid": bool,
                "sequence": [event_types],
                "timestamps": [timestamps],
                "violations": [descriptions]
            }
        """
        if operation_id not in self._events:
            return {
                "valid": False,
                "error": f"Operation {operation_id} not found in timeline"
            }
        
        events = self._events[operation_id]
        violations = []
        
        # Extract event types and timestamps
        event_types = [e.event_type for e in events]
        timestamps = [e.timestamp_unix for e in events]
        
        # Verify sequence
        if "BYBIT_REQUEST" not in event_types:
            violations.append("Missing BYBIT_REQUEST")
        
        if "BYBIT_ACK" not in event_types:
            violations.append("Missing BYBIT_ACK")
        
        if "TELEGRAM_SEND" in event_types:
            # Find indices
            try:
                req_idx = event_types.index("BYBIT_REQUEST")
                ack_idx = event_types.index("BYBIT_ACK")
                tel_idx = event_types.index("TELEGRAM_SEND")
                
                # Verify order: REQUEST < ACK < TELEGRAM
                if not (req_idx < ack_idx < tel_idx):
                    violations.append(
                        f"Wrong sequence: {event_types}. "
                        f"Expected: BYBIT_REQUEST → BYBIT_ACK → TELEGRAM_SEND"
                    )
                
                # Verify timestamps are ascending
                if not (timestamps[req_idx] < timestamps[ack_idx] < timestamps[tel_idx]):
                    violations.append("Timestamps not ascending")
                
                # Check if Bybit was successful
                ack_event = events[ack_idx]
                if ack_event.data.get("retCode") != 0:
                    # If Bybit failed, Telegram should NOT have been sent
                    violations.append(
                        f"Telegram sent despite Bybit failure (retCode={ack_event.data.get('retCode')})"
                    )
                
            except ValueError as e:
                violations.append(f"Sequence analysis error: {e}")
        
        return {
            "valid": len(violations) == 0,
            "operation_id": operation_id,
            "sequence": event_types,
            "timestamps": [datetime.fromtimestamp(ts, pytz.UTC).isoformat() for ts in timestamps],
            "violations": violations,
            "event_count": len(events)
        }
    
    async def generate_compliance_report(self) -> Dict[str, Any]:
        """
        Generate compliance report for all operations.
        
        CLIENT SPEC: Evidence that ALL Telegram messages followed Bybit acks.
        
        Returns:
            {
                "total_operations": int,
                "valid_sequences": int,
                "violations": [{operation_id, issues}],
                "compliance_rate": float
            }
        """
        total = len(self._events)
        violations = []
        
        for operation_id in self._events.keys():
            result = await self.verify_sequence(operation_id)
            if not result["valid"]:
                violations.append({
                    "operation_id": operation_id,
                    "issues": result.get("violations", [])
                })
        
        valid_count = total - len(violations)
        compliance_rate = (valid_count / total * 100) if total > 0 else 100.0
        
        return {
            "total_operations": total,
            "valid_sequences": valid_count,
            "violations": violations,
            "compliance_rate": compliance_rate,
            "status": "PASS" if compliance_rate == 100.0 else "FAIL"
        }


# Global timeline logger instance
_timeline_logger: Optional[TimelineLogger] = None


def get_timeline_logger() -> TimelineLogger:
    """Get global timeline logger instance."""
    global _timeline_logger
    if _timeline_logger is None:
        _timeline_logger = TimelineLogger()
    return _timeline_logger


async def log_bybit_request(operation_id: str, operation: str, data: Dict[str, Any]):
    """Convenience function to log Bybit request."""
    logger = get_timeline_logger()
    await logger.log_bybit_request(operation_id, operation, data)


async def log_bybit_ack(operation_id: str, retCode: int, response: Dict[str, Any]):
    """Convenience function to log Bybit ack."""
    logger = get_timeline_logger()
    await logger.log_bybit_ack(operation_id, retCode, response)


async def log_telegram_send(operation_id: str, message_id: Optional[int],
                            template_name: str, symbol: str):
    """Convenience function to log Telegram send."""
    logger = get_timeline_logger()
    await logger.log_telegram_send(operation_id, message_id, template_name, symbol)


async def verify_ack_gate_compliance() -> Dict[str, Any]:
    """Verify ACK-Gate compliance for all operations."""
    logger = get_timeline_logger()
    return await logger.generate_compliance_report()

