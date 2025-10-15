"""
Entry Order Policy - Enforces dual entry orders with Post-Only requirement.

CLIENT SPEC (doc/10_15.md Lines 459-471):
- Always place TWO limit entry orders (50/50 split or ±0.1% offset)
- ALL entry orders MUST have post_only=True
- NEVER have reduce_only=True on entries
- Apply proper tick/lot rounding before API call

This module provides a single source of truth for entry order creation logic.
"""

from decimal import Decimal, ROUND_DOWN
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
from app.core.logging import system_logger
from app.core.symbol_registry import SymbolInfo


@dataclass
class DualEntryConfig:
    """Configuration for dual entry strategy."""
    split_strategy: str = "50_50"  # "50_50" or "offset"
    offset_pct: Decimal = Decimal("0.1")  # Default ±0.1% offset for offset strategy
    post_only: bool = True  # MUST be True per CLIENT SPEC
    maker_join_ticks: int = 1  # Number of ticks to move away from taker price


class EntryOrderPolicy:
    """
    Enforces CLIENT SPEC requirements for entry orders.
    
    Key principles:
    1. ALWAYS create TWO entry orders
    2. ALWAYS set post_only=True
    3. NEVER set reduce_only=True
    4. Apply proper tick/lot quantization per symbol
    """
    
    def __init__(self, config: DualEntryConfig = None):
        """
        Initialize entry order policy.
        
        Args:
            config: Dual entry configuration (uses defaults if None)
        """
        self.config = config or DualEntryConfig()
        
        # Hard enforcement: Post-Only must be True per CLIENT SPEC
        if not self.config.post_only:
            raise ValueError("Entry orders MUST have post_only=True per CLIENT SPEC")
    
    def create_dual_entry_orders(
        self,
        symbol: str,
        direction: str,
        total_qty: Decimal,
        entry_prices: List[Decimal],
        symbol_info: SymbolInfo,
        order_link_id_prefix: str
    ) -> List[Dict[str, Any]]:
        """
        Create two entry orders with proper parameters.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            direction: Trade direction ("LONG" or "SHORT")
            total_qty: Total contract quantity to split
            entry_prices: List of entry prices (if len==1, will calculate second with offset)
            symbol_info: Symbol metadata for validation
            order_link_id_prefix: Prefix for orderLinkId generation
            
        Returns:
            List of two order dictionaries ready for Bybit API
            
        Raises:
            ValueError: If inputs are invalid or violate CLIENT SPEC
        """
        # Validate inputs
        self._validate_inputs(symbol, direction, total_qty, entry_prices, symbol_info)
        
        # Determine entry prices
        if len(entry_prices) == 1:
            # Single price provided - create second with offset
            price1, price2 = self._create_offset_prices(
                entry_prices[0], 
                direction,
                symbol_info
            )
        elif len(entry_prices) >= 2:
            # Two prices provided - use them directly
            price1 = self._round_price(entry_prices[0], symbol_info)
            price2 = self._round_price(entry_prices[1], symbol_info)
        else:
            raise ValueError("At least one entry price required")
        
        # Split quantity (50/50)
        qty_per_order = self._split_quantity(total_qty, symbol_info)
        
        # Determine Bybit side
        bybit_side = "Buy" if direction.upper() == "LONG" else "Sell"
        
        # Create order 1
        order1 = self._create_entry_order_dict(
            symbol=symbol,
            side=bybit_side,
            qty=qty_per_order,
            price=price1,
            order_link_id=f"{order_link_id_prefix}_entry1"
        )
        
        # Create order 2
        order2 = self._create_entry_order_dict(
            symbol=symbol,
            side=bybit_side,
            qty=qty_per_order,
            price=price2,
            order_link_id=f"{order_link_id_prefix}_entry2"
        )
        
        # Log creation
        system_logger.info(
            f"Created dual entry orders for {symbol}",
            {
                "symbol": symbol,
                "direction": direction,
                "total_qty": str(total_qty),
                "qty_per_order": str(qty_per_order),
                "price1": str(price1),
                "price2": str(price2),
                "post_only": True,
                "reduce_only": False
            }
        )
        
        return [order1, order2]
    
    def _validate_inputs(
        self,
        symbol: str,
        direction: str,
        total_qty: Decimal,
        entry_prices: List[Decimal],
        symbol_info: SymbolInfo
    ) -> None:
        """Validate input parameters."""
        if not symbol:
            raise ValueError("Symbol cannot be empty")
        
        if direction.upper() not in ["LONG", "SHORT"]:
            raise ValueError(f"Invalid direction: {direction}. Must be LONG or SHORT")
        
        if total_qty <= 0:
            raise ValueError(f"Total quantity must be positive: {total_qty}")
        
        if not entry_prices or len(entry_prices) == 0:
            raise ValueError("At least one entry price required")
        
        for price in entry_prices:
            if price <= 0:
                raise ValueError(f"Entry price must be positive: {price}")
        
        # Validate against symbol constraints
        if total_qty < symbol_info.min_qty:
            raise ValueError(
                f"Total qty {total_qty} below minimum {symbol_info.min_qty}"
            )
        
        if total_qty > symbol_info.max_qty:
            raise ValueError(
                f"Total qty {total_qty} exceeds maximum {symbol_info.max_qty}"
            )
    
    def _create_offset_prices(
        self,
        base_price: Decimal,
        direction: str,
        symbol_info: SymbolInfo
    ) -> Tuple[Decimal, Decimal]:
        """
        Create two prices with ±0.1% offset.
        
        Args:
            base_price: Base entry price
            direction: Trade direction
            symbol_info: Symbol metadata
            
        Returns:
            Tuple of (price1, price2) properly rounded
        """
        offset_multiplier = Decimal("1") + (self.config.offset_pct / Decimal("100"))
        
        if direction.upper() == "LONG":
            # For LONG: Buy at two slightly different prices
            # Price1: base_price - 0.1%
            # Price2: base_price + 0.1%
            price1 = base_price * (Decimal("1") - self.config.offset_pct / Decimal("100"))
            price2 = base_price * offset_multiplier
        else:  # SHORT
            # For SHORT: Sell at two slightly different prices
            price1 = base_price * offset_multiplier
            price2 = base_price * (Decimal("1") - self.config.offset_pct / Decimal("100"))
        
        # Round to tick size
        price1 = self._round_price(price1, symbol_info)
        price2 = self._round_price(price2, symbol_info)
        
        return price1, price2
    
    def _split_quantity(
        self,
        total_qty: Decimal,
        symbol_info: SymbolInfo
    ) -> Decimal:
        """
        Split quantity 50/50 with proper rounding.
        
        Args:
            total_qty: Total quantity to split
            symbol_info: Symbol metadata
            
        Returns:
            Quantity per order (properly quantized)
        """
        # Split in half
        qty_per_order = total_qty / Decimal("2")
        
        # Quantize to step size (ROUND_DOWN to ensure we don't exceed total)
        qty_per_order = symbol_info.quantize_qty(qty_per_order)
        
        # Ensure meets minimum
        if qty_per_order < symbol_info.min_qty:
            raise ValueError(
                f"Qty per order {qty_per_order} below minimum {symbol_info.min_qty}. "
                f"Total qty {total_qty} may be too small for dual entry."
            )
        
        return qty_per_order
    
    def _round_price(
        self,
        price: Decimal,
        symbol_info: SymbolInfo
    ) -> Decimal:
        """Round price to tick size."""
        return symbol_info.quantize_price(price)
    
    def _create_entry_order_dict(
        self,
        symbol: str,
        side: str,
        qty: Decimal,
        price: Decimal,
        order_link_id: str
    ) -> Dict[str, Any]:
        """
        Create entry order dictionary with CLIENT SPEC compliant parameters.
        
        CRITICAL ENFORCEMENT:
        - post_only: MUST be True (timeInForce: "PostOnly")
        - reduceOnly: MUST be False
        - orderType: MUST be "Limit"
        """
        order = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": "Limit",
            "qty": str(qty),
            "price": str(price),
            "timeInForce": "PostOnly",  # CLIENT SPEC: Post-Only enforcement
            "reduceOnly": False,  # CLIENT SPEC: NEVER True for entries
            "positionIdx": 0,
            "orderLinkId": order_link_id
        }
        
        # Validate the order we created
        self._validate_entry_order(order)
        
        return order
    
    def _validate_entry_order(self, order: Dict[str, Any]) -> None:
        """
        Validate that order meets CLIENT SPEC requirements.
        
        Raises:
            ValueError: If order violates CLIENT SPEC
        """
        # CRITICAL: Ensure Post-Only
        if order.get("timeInForce") != "PostOnly":
            raise ValueError(
                "CLIENT SPEC VIOLATION: Entry orders MUST have timeInForce='PostOnly'"
            )
        
        # CRITICAL: Ensure NOT reduce-only
        if order.get("reduceOnly") is not False:
            raise ValueError(
                "CLIENT SPEC VIOLATION: Entry orders MUST have reduceOnly=False"
            )
        
        # Ensure proper order type
        if order.get("orderType") != "Limit":
            raise ValueError(
                "Entry orders must be Limit orders (not Market)"
            )


def create_dual_entry_orders(
    symbol: str,
    direction: str,
    total_qty: Decimal,
    entry_prices: List[Decimal],
    symbol_info: SymbolInfo,
    order_link_id_prefix: str,
    config: DualEntryConfig = None
) -> List[Dict[str, Any]]:
    """
    Convenience function to create dual entry orders.
    
    This is the main entry point for creating entry orders throughout the codebase.
    
    Args:
        symbol: Trading symbol
        direction: "LONG" or "SHORT"
        total_qty: Total contract quantity
        entry_prices: List of entry prices
        symbol_info: Symbol metadata
        order_link_id_prefix: Prefix for order IDs
        config: Optional configuration (uses defaults if None)
        
    Returns:
        List of two order dictionaries ready for Bybit API
    """
    policy = EntryOrderPolicy(config)
    return policy.create_dual_entry_orders(
        symbol=symbol,
        direction=direction,
        total_qty=total_qty,
        entry_prices=entry_prices,
        symbol_info=symbol_info,
        order_link_id_prefix=order_link_id_prefix
    )

