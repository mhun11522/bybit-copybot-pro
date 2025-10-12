"""Centralized trade state management for Trade ID tracking (CLIENT SPEC)."""

from typing import Dict, Optional


class TradeState:
    """
    Central state manager for tracking Trade IDs across message chains.
    
    CLIENT SPEC: Each trade must have a consistent Trade ID that appears
    in all messages from signal received through position closed.
    """
    
    # Dictionary mapping trade keys to Trade IDs
    # Key format: f"{symbol}:{direction}:{timestamp}" or custom key
    trade_ids: Dict[str, str] = {}
    
    # Additional trade metadata
    trade_metadata: Dict[str, Dict] = {}
    
    @classmethod
    def get_or_set_trade_id(cls, key: str, new_id: str) -> str:
        """
        Get existing Trade ID for a key, or set and return new one.
        
        Args:
            key: Unique key for this trade (e.g., "BTCUSDT:LONG:1234567890")
            new_id: New Trade ID to set if key doesn't exist
        
        Returns:
            Trade ID (either existing or newly set)
        """
        if key in cls.trade_ids:
            return cls.trade_ids[key]
        
        cls.trade_ids[key] = new_id
        return new_id
    
    @classmethod
    def get_trade_id(cls, key: str) -> Optional[str]:
        """
        Get Trade ID for a key without creating one.
        
        Args:
            key: Trade key
        
        Returns:
            Trade ID if exists, None otherwise
        """
        return cls.trade_ids.get(key)
    
    @classmethod
    def set_trade_metadata(cls, key: str, metadata: Dict) -> None:
        """
        Store additional metadata for a trade.
        
        Args:
            key: Trade key
            metadata: Dictionary of metadata
        """
        cls.trade_metadata[key] = metadata
    
    @classmethod
    def get_trade_metadata(cls, key: str) -> Optional[Dict]:
        """
        Get metadata for a trade.
        
        Args:
            key: Trade key
        
        Returns:
            Metadata dictionary if exists, None otherwise
        """
        return cls.trade_metadata.get(key)
    
    @classmethod
    def clear_trade(cls, key: str) -> None:
        """
        Clear trade data (ID and metadata) for a key.
        
        Args:
            key: Trade key to clear
        """
        cls.trade_ids.pop(key, None)
        cls.trade_metadata.pop(key, None)
    
    @classmethod
    def get_all_active_trades(cls) -> Dict[str, str]:
        """
        Get all active trade IDs.
        
        Returns:
            Dictionary of {key: trade_id}
        """
        return cls.trade_ids.copy()

