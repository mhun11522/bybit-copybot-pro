"""
Enhanced Trade State Management with original_entry_price support.

CLIENT SPEC (doc/10_15.md Lines 495-505):
- All percentage calculations (TP/SL/BE/trailing) MUST use original_entry_price
- original_entry_price is set on first fill and NEVER changed
- Pyramid/hedge/re-entry do NOT affect original_entry_price
- This ensures consistent percentage calculations throughout trade lifecycle

This module provides immutable original_entry_price tracking.
"""

from decimal import Decimal
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from app.core.logging import system_logger


class TradeStatus(Enum):
    """Trade lifecycle status."""
    INIT = "INIT"
    LEVERAGE_SET = "LEVERAGE_SET"
    ENTRY_PLACED = "ENTRY_PLACED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FULLY_FILLED = "FULLY_FILLED"
    RUNNING = "RUNNING"
    TP_HIT = "TP_HIT"
    SL_HIT = "SL_HIT"
    CLOSED = "CLOSED"
    ERROR = "ERROR"


@dataclass
class TradeStateV2:
    """
    Enhanced trade state with immutable original_entry_price.
    
    CLIENT SPEC COMPLIANCE:
    - original_entry_price: Set on first fill, NEVER modified
    - All % calculations use original_entry_price (not avg_entry_price)
    - Pyramid/hedge/re-entry create new positions but don't affect original_entry_price
    
    Key Fields:
    - original_entry_price: IMMUTABLE - First fill price (for % calculations)
    - avg_entry_price: Current weighted average (for position tracking)
    - current_price: Latest market price
    """
    
    # Core identifiers
    trade_id: str
    symbol: str
    direction: str  # "LONG" or "SHORT"
    
    # Entry prices (CRITICAL)
    original_entry_price: Optional[Decimal] = None  # IMMUTABLE after first fill
    avg_entry_price: Optional[Decimal] = None  # Current weighted average
    
    # Position tracking
    total_qty: Decimal = Decimal("0")
    filled_qty: Decimal = Decimal("0")
    remaining_qty: Decimal = Decimal("0")
    
    # Leverage & margin
    leverage: Decimal = Decimal("6.0")
    initial_margin: Decimal = Decimal("20.0")
    current_margin: Decimal = Decimal("20.0")
    
    # Order tracking
    entry_order_ids: List[str] = field(default_factory=list)
    exit_order_ids: List[str] = field(default_factory=list)
    
    # Status
    status: TradeStatus = TradeStatus.INIT
    
    # Strategy states
    pyramid_level: int = 0
    breakeven_activated: bool = False
    trailing_activated: bool = False
    hedge_count: int = 0
    reentry_count: int = 0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    first_fill_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    # Metadata
    signal_data: Dict[str, Any] = field(default_factory=dict)
    channel_name: str = ""
    
    # PnL tracking
    realized_pnl: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    
    # Lock flag for original_entry_price
    _original_entry_locked: bool = False
    
    def set_original_entry_price(self, price: Decimal) -> None:
        """
        Set original entry price (ONLY ONCE).
        
        CLIENT SPEC: This can only be called once, on first fill.
        Any subsequent calls will be rejected to ensure immutability.
        
        Args:
            price: First fill price
            
        Raises:
            ValueError: If original_entry_price already set
        """
        if self._original_entry_locked:
            system_logger.error(
                "Attempted to modify locked original_entry_price",
                {
                    "trade_id": self.trade_id,
                    "current_original_entry": str(self.original_entry_price),
                    "attempted_new_value": str(price)
                }
            )
            raise ValueError(
                "CLIENT SPEC VIOLATION: original_entry_price is IMMUTABLE after first fill"
            )
        
        if price <= 0:
            raise ValueError(f"Invalid entry price: {price}")
        
        self.original_entry_price = price
        self._original_entry_locked = True
        self.first_fill_at = datetime.now()
        
        # Also set avg_entry_price initially
        if self.avg_entry_price is None:
            self.avg_entry_price = price
        
        system_logger.info(
            f"Set original_entry_price for {self.trade_id}",
            {
                "trade_id": self.trade_id,
                "symbol": self.symbol,
                "original_entry_price": str(price),
                "locked": True
            }
        )
    
    def update_avg_entry_price(self, new_fill_price: Decimal, fill_qty: Decimal) -> None:
        """
        Update weighted average entry price for new fills.
        
        NOTE: This updates avg_entry_price but NEVER touches original_entry_price.
        
        Args:
            new_fill_price: Price of new fill
            fill_qty: Quantity filled
        """
        if self.avg_entry_price is None:
            self.avg_entry_price = new_fill_price
        else:
            # Weighted average calculation
            total_cost = (self.avg_entry_price * self.filled_qty) + (new_fill_price * fill_qty)
            new_total_qty = self.filled_qty + fill_qty
            self.avg_entry_price = total_cost / new_total_qty
        
        self.filled_qty += fill_qty
        
        system_logger.info(
            f"Updated avg_entry_price for {self.trade_id}",
            {
                "trade_id": self.trade_id,
                "avg_entry_price": str(self.avg_entry_price),
                "original_entry_price": str(self.original_entry_price),
                "filled_qty": str(self.filled_qty)
            }
        )
    
    def calculate_pnl_from_original_entry(
        self,
        current_price: Decimal
    ) -> Dict[str, Decimal]:
        """
        Calculate PnL using original_entry_price (CLIENT SPEC).
        
        CRITICAL FIX (Requirement #30): PnL calculation must be correct.
        - pnl_pct: Price movement % (without leverage)
        - pnl_pct_leveraged: ROI % on margin (with leverage)
        - pnl_usdt: Actual USDT profit/loss
        
        Args:
            current_price: Current market price
            
        Returns:
            Dict with 'pnl_pct', 'pnl_usdt', 'pnl_pct_leveraged'
        """
        if self.original_entry_price is None:
            raise ValueError("original_entry_price not set yet")
        
        # Calculate price movement percentage (WITHOUT leverage)
        if self.direction.upper() == "LONG":
            pnl_pct = (current_price - self.original_entry_price) / self.original_entry_price * 100
        else:  # SHORT
            pnl_pct = (self.original_entry_price - current_price) / self.original_entry_price * 100
        
        # Leveraged PnL percentage (ROI on margin)
        pnl_pct_leveraged = pnl_pct * self.leverage
        
        # CRITICAL FIX: PnL in USDT (based on initial margin)
        # Formula: IM * (price_change_pct / 100) * leverage
        # Example: 20 USDT * (1.59% / 100) * 10x = 3.18 USDT ✓
        # NOT: 20 USDT * (15.9% / 100) = 3.18 USDT (this is the SAME, leveraged pct already includes it)
        pnl_usdt = self.initial_margin * (pnl_pct_leveraged / Decimal("100"))
        
        return {
            "pnl_pct": pnl_pct,  # Price movement (e.g., 1.59%)
            "pnl_pct_leveraged": pnl_pct_leveraged,  # ROI on margin (e.g., 15.9%)
            "pnl_usdt": pnl_usdt  # Actual profit (e.g., 3.18 USDT)
        }
    
    def calculate_target_price_from_original(
        self,
        target_pct: Decimal
    ) -> Decimal:
        """
        Calculate target price from original_entry_price + percentage.
        
        CLIENT SPEC: All TP/SL/BE calculations use original_entry_price.
        
        Args:
            target_pct: Target percentage (e.g., 2.3 for +2.3%)
            
        Returns:
            Target price
        """
        if self.original_entry_price is None:
            raise ValueError("original_entry_price not set yet")
        
        if self.direction.upper() == "LONG":
            target_price = self.original_entry_price * (Decimal("1") + target_pct / Decimal("100"))
        else:  # SHORT
            target_price = self.original_entry_price * (Decimal("1") - target_pct / Decimal("100"))
        
        return target_price
    
    def get_current_gain_pct_from_original(
        self,
        current_price: Decimal
    ) -> Decimal:
        """
        Get current gain percentage from original_entry_price.
        
        Args:
            current_price: Current market price
            
        Returns:
            Gain percentage (can be negative)
        """
        if self.original_entry_price is None:
            raise ValueError("original_entry_price not set yet")
        
        if self.direction.upper() == "LONG":
            gain_pct = (current_price - self.original_entry_price) / self.original_entry_price * 100
        else:  # SHORT
            gain_pct = (self.original_entry_price - current_price) / self.original_entry_price * 100
        
        return gain_pct
    
    def increment_pyramid_level(self) -> None:
        """Increment pyramid level."""
        self.pyramid_level += 1
        system_logger.info(
            f"Pyramid level incremented for {self.trade_id}",
            {
                "trade_id": self.trade_id,
                "new_level": self.pyramid_level,
                "original_entry_price": str(self.original_entry_price)
            }
        )
    
    def activate_breakeven(self) -> None:
        """Mark breakeven as activated."""
        self.breakeven_activated = True
        system_logger.info(f"Breakeven activated for {self.trade_id}")
    
    def activate_trailing(self) -> None:
        """Mark trailing as activated."""
        self.trailing_activated = True
        system_logger.info(f"Trailing activated for {self.trade_id}")
    
    def increment_hedge(self) -> None:
        """Increment hedge count."""
        self.hedge_count += 1
        system_logger.info(f"Hedge count incremented for {self.trade_id}: {self.hedge_count}")
    
    def increment_reentry(self) -> None:
        """Increment reentry count."""
        self.reentry_count += 1
        system_logger.info(f"Reentry count incremented for {self.trade_id}: {self.reentry_count}")
    
    def update_status(self, new_status: TradeStatus) -> None:
        """Update trade status."""
        old_status = self.status
        self.status = new_status
        
        system_logger.info(
            f"Trade status updated for {self.trade_id}",
            {
                "trade_id": self.trade_id,
                "old_status": old_status.value,
                "new_status": new_status.value
            }
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "original_entry_price": str(self.original_entry_price) if self.original_entry_price else None,
            "avg_entry_price": str(self.avg_entry_price) if self.avg_entry_price else None,
            "total_qty": str(self.total_qty),
            "filled_qty": str(self.filled_qty),
            "leverage": str(self.leverage),
            "initial_margin": str(self.initial_margin),
            "current_margin": str(self.current_margin),
            "status": self.status.value,
            "pyramid_level": self.pyramid_level,
            "breakeven_activated": self.breakeven_activated,
            "trailing_activated": self.trailing_activated,
            "hedge_count": self.hedge_count,
            "reentry_count": self.reentry_count,
            "created_at": self.created_at.isoformat(),
            "first_fill_at": self.first_fill_at.isoformat() if self.first_fill_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "realized_pnl": str(self.realized_pnl),
            "unrealized_pnl": str(self.unrealized_pnl),
            "channel_name": self.channel_name
        }


class TradeStateManager:
    """
    Manager for multiple trade states.
    
    Provides centralized access to active trade states.
    """
    
    def __init__(self):
        """Initialize trade state manager."""
        self._states: Dict[str, TradeStateV2] = {}
    
    def create_trade_state(
        self,
        trade_id: str,
        symbol: str,
        direction: str,
        leverage: Decimal,
        initial_margin: Decimal,
        signal_data: Dict[str, Any],
        channel_name: str
    ) -> TradeStateV2:
        """
        Create a new trade state.
        
        Args:
            trade_id: Unique trade ID
            symbol: Trading symbol
            direction: "LONG" or "SHORT"
            leverage: Leverage multiplier
            initial_margin: Initial margin in USDT
            signal_data: Original signal data
            channel_name: Source channel name
            
        Returns:
            New TradeStateV2 instance
        """
        if trade_id in self._states:
            raise ValueError(f"Trade ID {trade_id} already exists")
        
        state = TradeStateV2(
            trade_id=trade_id,
            symbol=symbol,
            direction=direction,
            leverage=leverage,
            initial_margin=initial_margin,
            current_margin=initial_margin,
            signal_data=signal_data,
            channel_name=channel_name
        )
        
        self._states[trade_id] = state
        
        system_logger.info(
            f"Created trade state for {trade_id}",
            {
                "trade_id": trade_id,
                "symbol": symbol,
                "direction": direction,
                "leverage": str(leverage),
                "initial_margin": str(initial_margin)
            }
        )
        
        return state
    
    def get_state(self, trade_id: str) -> Optional[TradeStateV2]:
        """Get trade state by ID."""
        return self._states.get(trade_id)
    
    def remove_state(self, trade_id: str) -> None:
        """Remove trade state."""
        if trade_id in self._states:
            del self._states[trade_id]
            system_logger.info(f"Removed trade state for {trade_id}")
    
    def get_all_active_states(self) -> List[TradeStateV2]:
        """Get all active trade states."""
        return list(self._states.values())
    
    def get_states_by_symbol(self, symbol: str) -> List[TradeStateV2]:
        """Get all trade states for a symbol."""
        return [state for state in self._states.values() if state.symbol == symbol]


# Global singleton manager
_trade_state_manager: Optional[TradeStateManager] = None


def get_trade_state_manager() -> TradeStateManager:
    """Get global trade state manager singleton."""
    global _trade_state_manager
    if _trade_state_manager is None:
        _trade_state_manager = TradeStateManager()
    return _trade_state_manager

