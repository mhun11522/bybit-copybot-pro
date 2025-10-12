"""
Telegram output with structured logging (CLIENT SPEC compliance).

All Telegram messages are logged with full metadata for audit/forensics.
"""

import asyncio
from typing import Optional
from app.core.logging import system_logger


async def send_message(
    text: str,
    target_chat_id: int = None,
    *,
    template_name: str = "",
    trade_id: str = "",
    symbol: str = "",
    hashtags: str = "",
    parse_mode: str = "md"
) -> Optional[int]:
    """
    Send message to Telegram output channel with structured logging.
    
    CLIENT SPEC: All operational messages must be logged with full metadata
    for troubleshooting and analysis.
    
    Args:
        text: Message text (supports Markdown with parse_mode="md")
        target_chat_id: Target chat ID (if None, uses OUTPUT_CHANNEL_ID)
        template_name: Template name for logging (e.g., "ORDER_PLACED")
        trade_id: Trade ID for correlation
        symbol: Trading symbol
        hashtags: Hashtags for this message
        parse_mode: Telegram parse mode ("md" for Markdown, "" for plain text)
    
    Returns:
        Message ID if successful, None otherwise
    """
    try:
        # Import here to avoid circular import
        from app.telegram.strict_client import get_strict_telegram_client
        from app.config.settings import OUTPUT_CHANNEL_ID
        
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
            
            # Log 100% with structured data (CLIENT SPEC)
            system_logger.info("telegram_message_sent", {
                "template_name": template_name,
                "trade_id": trade_id,
                "symbol": symbol,
                "hashtags": hashtags,
                "message_id": message_id,
                "chat_id": chat_id,
                "text_length": len(text),
                "parse_mode": parse_mode,
                # Only log first 200 chars of text to avoid huge logs
                "text_preview": text[:200] if len(text) > 200 else text
            })
            
            return message_id
        else:
            # Fallback to printing if no target is configured or not connected
            print(f"[TELEGRAM] {text}")
            
            system_logger.warning("telegram_message_fallback_stdout", {
                "template_name": template_name,
                "trade_id": trade_id,
                "symbol": symbol,
                "hashtags": hashtags,
                "reason": "not_connected" if client else "no_chat_id",
                "text_preview": text[:200] if len(text) > 200 else text
            })
            
            return None
            
    except Exception as e:
        # Log error with full context
        system_logger.error("telegram_message_send_error", {
            "error": str(e),
            "template_name": template_name,
            "trade_id": trade_id,
            "symbol": symbol,
            "hashtags": hashtags,
            "text_preview": text[:200] if len(text) > 200 else text
        }, exc_info=True)
        
        print(f"[TELEGRAM ERROR] Failed to send message: {e}")
        print(f"[FALLBACK] {text}")
        
        return None