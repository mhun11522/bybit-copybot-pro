"""
Telegram output with structured logging (CLIENT SPEC compliance).

All Telegram messages are logged with full metadata for audit/forensics.
CLIENT SPEC Line 293: Timeline logging proves Telegram after Bybit ack.
CLIENT SPEC (doc/10_12_3.md Lines 92-318): JSON Lines with trace_id, message_text_hash, session_id.
"""

import asyncio
import hashlib
import uuid
from typing import Optional
from app.core.logging import system_logger
from app.core.timeline_logger import log_telegram_send

# Global session ID (generated once per bot runtime)
_session_id = str(uuid.uuid4())

def get_session_id() -> str:
    """Get the current bot session ID."""
    return _session_id


async def send_message(
    text: str,
    target_chat_id: int = None,
    *,
    template_name: str = "",
    trade_id: str = "",
    symbol: str = "",
    hashtags: str = "",
    parse_mode: str = "md",
    operation_id: str = "",  # For timeline logging
    trace_id: str = ""  # CLIENT SPEC: UUID for event chain correlation
) -> Optional[int]:
    """
    Send message to Telegram output channel with structured logging.
    
    CLIENT SPEC: All operational messages must be logged with full metadata
    for troubleshooting and analysis.
    CLIENT SPEC (doc/10_12_3.md Lines 92-318): JSON Lines with mandatory fields.
    
    Args:
        text: Message text (supports Markdown with parse_mode="md")
        target_chat_id: Target chat ID (if None, uses OUTPUT_CHANNEL_ID)
        template_name: Template name for logging (e.g., "ORDER_PLACED")
        trade_id: Trade ID for correlation
        symbol: Trading symbol
        hashtags: Hashtags for this message
        parse_mode: Telegram parse mode ("md" for Markdown, "" for plain text)
        operation_id: Operation ID for timeline logging
        trace_id: Trace ID for event chain correlation (generated if not provided)
    
    Returns:
        Message ID if successful, None otherwise
    """
    try:
        # Import here to avoid circular import
        from app.telegram.strict_client import get_strict_telegram_client
        from app.config.settings import OUTPUT_CHANNEL_ID
        from app.core.strict_config import STRICT_CONFIG
        
        # CLIENT FIX: is_production not in environment_detector, detect from endpoint
        def is_production():
            return "demo" not in STRICT_CONFIG.bybit_endpoint.lower() and "testnet" not in STRICT_CONFIG.bybit_endpoint.lower()
        
        # CLIENT SPEC: Generate trace_id if not provided
        if not trace_id:
            trace_id = str(uuid.uuid4())
        
        # CLIENT SPEC: Calculate message_text_hash for integrity
        message_text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
        
        # Get the strict client
        client = await get_strict_telegram_client()
        
        # Use OUTPUT_CHANNEL_ID as default if configured
        chat_id = target_chat_id or OUTPUT_CHANNEL_ID
        
        if chat_id and client.client.is_connected():
            # Send with parse_mode for markdown support (**bold**, etc.)
            msg = await client.client.send_message(
                chat_id,
                text,
                parse_mode=parse_mode if parse_mode else None
            )
            
            # Get message ID
            message_id = getattr(msg, "id", None)
            
            # Timeline: Log Telegram send (CLIENT SPEC Line 293 - ACK-Gate proof)
            if operation_id:
                await log_telegram_send(operation_id, message_id, template_name, symbol)
            
            # Log 100% with structured data (CLIENT SPEC doc/10_12_3.md Lines 92-318)
            # CLIENT SPEC Line 56: Log FULL text on success, not just preview
            # CLIENT SPEC: JSON Lines with mandatory fields (trace_id, message_text_hash, session_id)
            system_logger.info("telegram_message_sent", {
                # Original fields
                "template_name": template_name,
                "trade_id": trade_id,
                "symbol": symbol,
                "hashtags": hashtags,
                "message_id": message_id,
                "chat_id": chat_id,
                "text_length": len(text),
                "parse_mode": parse_mode,
                "operation_id": operation_id,
                "full_text": text,  # CLIENT SPEC: Full text, not preview
                
                # CLIENT SPEC (doc/10_12_3.md): Mandatory fields
                "event": "telegram_message_sent",
                "event_version": "1.0.0",
                "env": "PROD" if is_production() else "DEMO",
                "channel": "external",
                "message_status": "sent",
                "message_text_hash": message_text_hash,  # SHA256 for integrity
                "trace_id": trace_id,  # UUID for event chain correlation
                "session_id": get_session_id(),  # Bot runtime session ID
                "retry_count": 0
            })
            
            return message_id
        else:
            # Fallback to printing if no target is configured or not connected
            print(f"[TELEGRAM] {text}")
            
            # CLIENT SPEC Line 57: Log full text on fallback too
            # CLIENT SPEC: Include mandatory trace fields even on fallback
            system_logger.warning("telegram_message_fallback_stdout", {
                "template_name": template_name,
                "trade_id": trade_id,
                "symbol": symbol,
                "hashtags": hashtags,
                "reason": "not_connected" if client else "no_chat_id",
                "full_text": text,  # CLIENT SPEC: Full text
                
                # CLIENT SPEC: Mandatory fields
                "event": "telegram_message_fallback",
                "event_version": "1.0.0",
                "env": "PROD" if is_production() else "DEMO",
                "channel": "external",
                "message_status": "fallback",
                "message_text_hash": message_text_hash,
                "trace_id": trace_id,
                "session_id": get_session_id(),
                "retry_count": 0
            })
            
            return None
            
    except Exception as e:
        # Calculate hash even on error
        message_text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
        if not trace_id:
            trace_id = str(uuid.uuid4())
        
        # Log error with full context
        # CLIENT SPEC Line 57: Dump full text on error for debugging
        # CLIENT SPEC: Include mandatory trace fields even on error
        system_logger.error("telegram_message_send_error", {
            "error": str(e),
            "template_name": template_name,
            "trade_id": trade_id,
            "symbol": symbol,
            "hashtags": hashtags,
            "full_text": text,  # CLIENT SPEC: Full text on error
            
            # CLIENT SPEC: Mandatory fields
            "event": "telegram_message_error",
            "event_version": "1.0.0",
            "env": "PROD" if is_production() else "DEMO",
            "channel": "external",
            "message_status": "failed",
            "message_text_hash": message_text_hash,
            "trace_id": trace_id,
            "session_id": get_session_id(),
            "retry_count": 0
        }, exc_info=True, extra={"text": text})
        
        print(f"[TELEGRAM ERROR] Failed to send message: {e}")
        print(f"[FALLBACK] {text}")
        
        return None