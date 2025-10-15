"""
Exit Order Policy - Enforces reduce-only and proper exit order flags.

CLIENT SPEC (doc/10_15.md Lines 472-482):
- Exit orders (TP/SL) MUST have reduce_only=True
- Entry orders MUST NEVER have reduce_only=True
- Consistent trigger source (Mark/Last/Index) across all SL/TP
- All closing orders: CloseOnTrigger + ReduceOnly

This module provides validation and enforcement of exit order requirements.
"""

from decimal import Decimal
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
from app.core.logging import system_logger


class TriggerSource(Enum):
    """Bybit trigger price types."""
    LAST_PRICE = "LastPrice"
    INDEX_PRICE = "IndexPrice"
    MARK_PRICE = "MarkPrice"


class ExitOrderType(Enum):
    """Types of exit orders."""
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    BREAKEVEN = "BREAKEVEN"
    TRAILING_STOP = "TRAILING_STOP"


@dataclass
class ExitOrderConfig:
    """Configuration for exit orders."""
    trigger_source: TriggerSource = TriggerSource.LAST_PRICE
    close_on_trigger: bool = True
    reduce_only: bool = True  # MUST be True per CLIENT SPEC
    
    @classmethod
    def from_strict_config(cls):
        """Create config from STRICT_CONFIG settings."""
        from app.core.strict_config import STRICT_CONFIG
        
        # Map string to enum
        trigger_str = STRICT_CONFIG.exit_trigger_by
        trigger_map = {
            "LastPrice": TriggerSource.LAST_PRICE,
            "MarkPrice": TriggerSource.MARK_PRICE,
            "IndexPrice": TriggerSource.INDEX_PRICE,
        }
        
        trigger_source = trigger_map.get(trigger_str, TriggerSource.LAST_PRICE)
        
        return cls(
            trigger_source=trigger_source,
            close_on_trigger=True,
            reduce_only=True
        )


class ExitOrderPolicy:
    """
    Enforces CLIENT SPEC requirements for exit orders.
    
    Key principles:
    1. ALL exit orders MUST have reduce_only=True
    2. Consistent trigger_source across all SL/TP
    3. CloseOnTrigger for market-based stops
    4. Validate before submission to Bybit
    """
    
    def __init__(self, config: ExitOrderConfig = None):
        """
        Initialize exit order policy.
        
        Args:
            config: Exit order configuration (uses defaults if None)
        """
        self.config = config or ExitOrderConfig()
        
        # Hard enforcement: Reduce-Only must be True per CLIENT SPEC
        if not self.config.reduce_only:
            raise ValueError("Exit orders MUST have reduce_only=True per CLIENT SPEC")
    
    def create_take_profit_order(
        self,
        symbol: str,
        side: str,
        qty: Decimal,
        price: Decimal,
        order_link_id: str,
        trigger_price: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """
        Create a take profit order.
        
        Args:
            symbol: Trading symbol
            side: Order side ("Buy" or "Sell")
            qty: Contract quantity
            price: TP limit price
            order_link_id: Unique order link ID
            trigger_price: Optional trigger price (for conditional TP)
            
        Returns:
            Order dictionary ready for Bybit API
        """
        order = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": "Limit",
            "qty": str(qty),
            "price": str(price),
            "timeInForce": "GTC",
            "reduceOnly": True,  # CLIENT SPEC: MUST be True
            "positionIdx": 0,
            "orderLinkId": order_link_id
        }
        
        # Add trigger if conditional TP
        if trigger_price is not None:
            order["triggerPrice"] = str(trigger_price)
            order["triggerBy"] = self.config.trigger_source.value
        
        # Validate before returning
        self._validate_exit_order(order, ExitOrderType.TAKE_PROFIT)
        
        system_logger.info(
            f"Created TP order for {symbol}",
            {
                "symbol": symbol,
                "side": side,
                "qty": str(qty),
                "price": str(price),
                "reduce_only": True,
                "order_link_id": order_link_id
            }
        )
        
        return order
    
    def create_stop_loss_order(
        self,
        symbol: str,
        side: str,
        qty: Decimal,
        trigger_price: Decimal,
        order_link_id: str,
        order_type: str = "Market"
    ) -> Dict[str, Any]:
        """
        Create a stop loss order.
        
        Args:
            symbol: Trading symbol
            side: Order side ("Buy" or "Sell")
            qty: Contract quantity
            trigger_price: SL trigger price
            order_link_id: Unique order link ID
            order_type: "Market" or "Limit" (default Market for immediate execution)
            
        Returns:
            Order dictionary ready for Bybit API
        """
        order = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "qty": str(qty),
            "triggerPrice": str(trigger_price),
            "triggerBy": self.config.trigger_source.value,
            "reduceOnly": True,  # CLIENT SPEC: MUST be True
            "closeOnTrigger": self.config.close_on_trigger,
            "positionIdx": 0,
            "orderLinkId": order_link_id
        }
        
        # Add price if Limit order
        if order_type == "Limit":
            order["price"] = str(trigger_price)
            order["timeInForce"] = "GTC"
        
        # Validate before returning
        self._validate_exit_order(order, ExitOrderType.STOP_LOSS)
        
        system_logger.info(
            f"Created SL order for {symbol}",
            {
                "symbol": symbol,
                "side": side,
                "qty": str(qty),
                "trigger_price": str(trigger_price),
                "trigger_source": self.config.trigger_source.value,
                "reduce_only": True,
                "close_on_trigger": self.config.close_on_trigger,
                "order_link_id": order_link_id
            }
        )
        
        return order
    
    def validate_order_flags(
        self,
        order: Dict[str, Any],
        is_exit: bool
    ) -> Dict[str, Any]:
        """
        Validate order flags against CLIENT SPEC.
        
        Args:
            order: Order dictionary to validate
            is_exit: True if exit order, False if entry order
            
        Returns:
            Validation result dict with 'valid' and 'errors' keys
            
        Raises:
            ValueError: If order violates CLIENT SPEC
        """
        errors = []
        
        reduce_only = order.get("reduceOnly", False)
        
        if is_exit:
            # Exit orders MUST have reduceOnly=True
            if not reduce_only:
                errors.append(
                    "CLIENT SPEC VIOLATION: Exit orders MUST have reduceOnly=True"
                )
        else:
            # Entry orders MUST have reduceOnly=False
            if reduce_only:
                errors.append(
                    "CLIENT SPEC VIOLATION: Entry orders MUST have reduceOnly=False"
                )
        
        if errors:
            error_msg = "; ".join(errors)
            system_logger.error(
                f"Order flag validation failed",
                {
                    "is_exit": is_exit,
                    "reduce_only": reduce_only,
                    "errors": errors,
                    "order": order
                }
            )
            raise ValueError(error_msg)
        
        return {"valid": True, "errors": []}
    
    def _validate_exit_order(
        self,
        order: Dict[str, Any],
        order_type: ExitOrderType
    ) -> None:
        """
        Validate that exit order meets CLIENT SPEC requirements.
        
        Args:
            order: Order dictionary to validate
            order_type: Type of exit order
            
        Raises:
            ValueError: If order violates CLIENT SPEC
        """
        # CRITICAL: Ensure reduceOnly=True
        if order.get("reduceOnly") is not True:
            raise ValueError(
                f"CLIENT SPEC VIOLATION: Exit orders MUST have reduceOnly=True. "
                f"Order type: {order_type.value}"
            )
        
        # Validate trigger source consistency for triggered orders
        if "triggerBy" in order:
            trigger_by = order.get("triggerBy")
            if trigger_by not in [ts.value for ts in TriggerSource]:
                raise ValueError(
                    f"Invalid triggerBy: {trigger_by}. "
                    f"Must be one of: {[ts.value for ts in TriggerSource]}"
                )
    
    def get_trigger_source_value(self) -> str:
        """Get the configured trigger source as Bybit API value."""
        return self.config.trigger_source.value


class ExitOrderValidator:
    """
    Standalone validator for exit orders.
    
    Use this to validate orders created elsewhere before submission.
    """
    
    @staticmethod
    def validate_reduce_only_flag(
        order: Dict[str, Any],
        is_exit: bool
    ) -> bool:
        """
        Validate reduce-only flag.
        
        Args:
            order: Order dictionary
            is_exit: True if exit order
            
        Returns:
            True if valid, False otherwise
        """
        reduce_only = order.get("reduceOnly", False)
        
        if is_exit and not reduce_only:
            system_logger.error(
                "Exit order missing reduceOnly=True",
                {"order": order}
            )
            return False
        
        if not is_exit and reduce_only:
            system_logger.error(
                "Entry order has reduceOnly=True (FORBIDDEN)",
                {"order": order}
            )
            return False
        
        return True
    
    @staticmethod
    def scan_order_body_for_violations(
        orders: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Scan multiple orders for CLIENT SPEC violations.
        
        Args:
            orders: List of order dictionaries
            
        Returns:
            List of violation reports (empty if all valid)
        """
        violations = []
        
        for idx, order in enumerate(orders):
            # Detect if exit order based on reduceOnly field or orderLinkId pattern
            order_link_id = order.get("orderLinkId", "")
            is_likely_exit = (
                "tp" in order_link_id.lower() or
                "sl" in order_link_id.lower() or
                "be" in order_link_id.lower() or
                "trail" in order_link_id.lower()
            )
            
            reduce_only = order.get("reduceOnly", False)
            
            # Check for violations
            if is_likely_exit and not reduce_only:
                violations.append({
                    "index": idx,
                    "order_link_id": order_link_id,
                    "violation": "Exit order missing reduceOnly=True",
                    "order": order
                })
            
            if not is_likely_exit and reduce_only:
                violations.append({
                    "index": idx,
                    "order_link_id": order_link_id,
                    "violation": "Entry order has reduceOnly=True (FORBIDDEN)",
                    "order": order
                })
        
        return violations


def create_take_profit_order(
    symbol: str,
    side: str,
    qty: Decimal,
    price: Decimal,
    order_link_id: str,
    config: ExitOrderConfig = None,
    trigger_price: Optional[Decimal] = None
) -> Dict[str, Any]:
    """
    Convenience function to create a take profit order.
    
    Uses STRICT_CONFIG trigger source if no config provided.
    
    Args:
        symbol: Trading symbol
        side: Order side
        qty: Contract quantity
        price: TP price
        order_link_id: Unique ID
        config: Optional configuration (uses STRICT_CONFIG if None)
        trigger_price: Optional trigger price
        
    Returns:
        Order dictionary ready for Bybit API
    """
    if config is None:
        config = ExitOrderConfig.from_strict_config()
    
    policy = ExitOrderPolicy(config)
    return policy.create_take_profit_order(
        symbol=symbol,
        side=side,
        qty=qty,
        price=price,
        order_link_id=order_link_id,
        trigger_price=trigger_price
    )


def create_stop_loss_order(
    symbol: str,
    side: str,
    qty: Decimal,
    trigger_price: Decimal,
    order_link_id: str,
    config: ExitOrderConfig = None,
    order_type: str = "Market"
) -> Dict[str, Any]:
    """
    Convenience function to create a stop loss order.
    
    Uses STRICT_CONFIG trigger source if no config provided.
    
    Args:
        symbol: Trading symbol
        side: Order side
        qty: Contract quantity
        trigger_price: SL trigger price
        order_link_id: Unique ID
        config: Optional configuration (uses STRICT_CONFIG if None)
        order_type: "Market" or "Limit"
        
    Returns:
        Order dictionary ready for Bybit API
    """
    if config is None:
        config = ExitOrderConfig.from_strict_config()
    
    policy = ExitOrderPolicy(config)
    return policy.create_stop_loss_order(
        symbol=symbol,
        side=side,
        qty=qty,
        trigger_price=trigger_price,
        order_link_id=order_link_id,
        order_type=order_type
    )


def get_trigger_source() -> str:
    """
    Get the configured trigger source from STRICT_CONFIG.
    
    Returns:
        Trigger source string ("LastPrice", "MarkPrice", or "IndexPrice")
        
    Example:
        >>> trigger = get_trigger_source()
        >>> # Use in order: order["triggerBy"] = trigger
    """
    from app.core.strict_config import STRICT_CONFIG
    return STRICT_CONFIG.exit_trigger_by

