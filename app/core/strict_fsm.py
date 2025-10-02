"""Strict FSM for trade lifecycle management."""

import asyncio
from enum import Enum
from typing import Dict, Any, Optional, Callable
from decimal import Decimal
from datetime import datetime
from app.core.logging import system_logger, trade_logger
from app.core.strict_config import STRICT_CONFIG
from app.core.confirmation_gate import get_confirmation_gate

class TradeState(Enum):
    """Trade lifecycle states."""
    INIT = "INIT"
    LEVERAGE_SET = "LEVERAGE_SET"
    ENTRY_PLACED = "ENTRY_PLACED"
    ENTRY_FILLED = "ENTRY_FILLED"
    TP_SL_PLACED = "TP_SL_PLACED"
    RUNNING = "RUNNING"
    TP_HIT = "TP_HIT"
    SL_HIT = "SL_HIT"
    HEDGE_ACTIVE = "HEDGE_ACTIVE"
    REENTRY_ATTEMPT = "REENTRY_ATTEMPT"
    CLOSED = "CLOSED"
    ERROR = "ERROR"

class TradeFSM:
    """Strict FSM for trade lifecycle management."""
    
    def __init__(self, signal_data: Dict[str, Any]):
        self.signal_data = signal_data
        self.state = TradeState.INIT
        self.trade_id = f"{signal_data['symbol']}_{int(datetime.now().timestamp())}"
        self.entry_orders = []
        self.exit_orders = []
        self.position_size = Decimal("0")
        self.entry_price = Decimal("0")
        self.current_pnl = Decimal("0")
        self.pyramid_level = 0
        self.trailing_active = False
        self.hedge_count = 0
        self.reentry_count = 0
        self.error_count = 0
        self.max_errors = 3
        
        # State transition handlers
        self._handlers = {
            TradeState.INIT: self._handle_init,
            TradeState.LEVERAGE_SET: self._handle_leverage_set,
            TradeState.ENTRY_PLACED: self._handle_entry_placed,
            TradeState.ENTRY_FILLED: self._handle_entry_filled,
            TradeState.TP_SL_PLACED: self._handle_tp_sl_placed,
            TradeState.RUNNING: self._handle_running,
            TradeState.TP_HIT: self._handle_tp_hit,
            TradeState.SL_HIT: self._handle_sl_hit,
            TradeState.HEDGE_ACTIVE: self._handle_hedge_active,
            TradeState.REENTRY_ATTEMPT: self._handle_reentry_attempt,
            TradeState.CLOSED: self._handle_closed,
            TradeState.ERROR: self._handle_error
        }
    
    async def run(self) -> bool:
        """Run the FSM until completion or error."""
        try:
            system_logger.info(f"Starting FSM for trade {self.trade_id}", {
                'symbol': self.signal_data['symbol'],
                'direction': self.signal_data['direction'],
                'mode': self.signal_data['mode']
            })
            
            while self.state not in [TradeState.CLOSED, TradeState.ERROR]:
                handler = self._handlers.get(self.state)
                if not handler:
                    system_logger.error(f"No handler for state {self.state}")
                    await self._transition_to(TradeState.ERROR)
                    break
                
                try:
                    success = await handler()
                    if not success:
                        await self._transition_to(TradeState.ERROR)
                        break
                except Exception as e:
                    system_logger.error(f"Handler error in state {self.state}: {e}", exc_info=True)
                    self.error_count += 1
                    if self.error_count >= self.max_errors:
                        await self._transition_to(TradeState.ERROR)
                        break
                    else:
                        await asyncio.sleep(1)  # Brief pause before retry
            
            return self.state == TradeState.CLOSED
            
        except Exception as e:
            system_logger.error(f"FSM run error: {e}", exc_info=True)
            await self._transition_to(TradeState.ERROR)
            return False
    
    async def _transition_to(self, new_state: TradeState):
        """Transition to new state."""
        old_state = self.state
        self.state = new_state
        
        system_logger.info(f"State transition: {old_state} -> {new_state}", {
            'trade_id': self.trade_id,
            'symbol': self.signal_data['symbol']
        })
    
    async def _handle_init(self) -> bool:
        """Handle INIT state - validate signal and prepare."""
        try:
            # Validate signal data
            if not self._validate_signal():
                return False
            
            # Check if we can open new trade
            if not await self._check_capacity():
                return False
            
            # Calculate position size
            position_size = await self._calculate_position_size()
            if position_size <= 0:
                return False
            
            self.position_size = position_size
            
            # Transition to leverage setting
            await self._transition_to(TradeState.LEVERAGE_SET)
            return True
            
        except Exception as e:
            system_logger.error(f"Init handler error: {e}", exc_info=True)
            return False
    
    async def _handle_leverage_set(self) -> bool:
        """Handle LEVERAGE_SET state - set leverage on Bybit."""
        try:
            gate = get_confirmation_gate()
            
            # Set leverage through confirmation gate
            success = await gate.wait_for_confirmation(
                f"leverage_{self.trade_id}",
                self._set_leverage_operation,
                self._leverage_confirmed_callback
            )
            
            if success:
                await self._transition_to(TradeState.ENTRY_PLACED)
            else:
                await self._transition_to(TradeState.ERROR)
            
            return success
            
        except Exception as e:
            system_logger.error(f"Leverage set handler error: {e}", exc_info=True)
            return False
    
    async def _handle_entry_placed(self) -> bool:
        """Handle ENTRY_PLACED state - place entry orders."""
        try:
            gate = get_confirmation_gate()
            
            # Place entry orders through confirmation gate
            success = await gate.place_entry_orders(
                self.signal_data['symbol'],
                self.signal_data['direction'],
                [Decimal(e) for e in self.signal_data['entries']],
                self.position_size,
                Decimal(str(self.signal_data['leverage'])),
                self.signal_data['channel_name']
            )
            
            if success:
                await self._transition_to(TradeState.ENTRY_FILLED)
            else:
                await self._transition_to(TradeState.ERROR)
            
            return success
            
        except Exception as e:
            system_logger.error(f"Entry placed handler error: {e}", exc_info=True)
            return False
    
    async def _handle_entry_filled(self) -> bool:
        """Handle ENTRY_FILLED state - monitor for fills."""
        try:
            # Check for position
            position = await self._get_position()
            if position and float(position.get('size', 0)) > 0:
                self.entry_price = Decimal(str(position.get('avgPrice', 0)))
                await self._transition_to(TradeState.TP_SL_PLACED)
                return True
            else:
                # Wait for fill
                await asyncio.sleep(1)
                return True
                
        except Exception as e:
            system_logger.error(f"Entry filled handler error: {e}", exc_info=True)
            return False
    
    async def _handle_tp_sl_placed(self) -> bool:
        """Handle TP_SL_PLACED state - place TP/SL orders."""
        try:
            gate = get_confirmation_gate()
            
            # Place TP/SL orders through confirmation gate
            success = await gate.place_exit_orders(
                self.signal_data['symbol'],
                self.signal_data['direction'],
                self.position_size,
                [Decimal(tp) for tp in self.signal_data.get('tps', [])],
                Decimal(str(self.signal_data.get('sl', 0))) if self.signal_data.get('sl') else None,
                self.signal_data['channel_name']
            )
            
            if success:
                await self._transition_to(TradeState.RUNNING)
            else:
                await self._transition_to(TradeState.ERROR)
            
            return success
            
        except Exception as e:
            system_logger.error(f"TP/SL placed handler error: {e}", exc_info=True)
            return False
    
    async def _handle_running(self) -> bool:
        """Handle RUNNING state - monitor position and manage strategies."""
        try:
            # Check position status
            position = await self._get_position()
            if not position or float(position.get('size', 0)) == 0:
                # Position closed
                await self._transition_to(TradeState.CLOSED)
                return True
            
            # Update PnL
            self.current_pnl = Decimal(str(position.get('unrealisedPnl', 0)))
            
            # Check for TP hits
            if await self._check_tp_hit():
                await self._transition_to(TradeState.TP_HIT)
                return True
            
            # Check for SL hits
            if await self._check_sl_hit():
                await self._transition_to(TradeState.SL_HIT)
                return True
            
            # Check for hedge trigger
            if await self._check_hedge_trigger():
                await self._transition_to(TradeState.HEDGE_ACTIVE)
                return True
            
            # Check for pyramid levels
            await self._check_pyramid_levels()
            
            # Check for trailing stop
            await self._check_trailing_stop()
            
            # Brief pause before next check
            await asyncio.sleep(1)
            return True
            
        except Exception as e:
            system_logger.error(f"Running handler error: {e}", exc_info=True)
            return False
    
    async def _handle_tp_hit(self) -> bool:
        """Handle TP_HIT state - manage TP hits."""
        try:
            # Check if this is TP2 for breakeven
            if self.pyramid_level >= 2:
                await self._move_to_breakeven()
            
            # Continue running
            await self._transition_to(TradeState.RUNNING)
            return True
            
        except Exception as e:
            system_logger.error(f"TP hit handler error: {e}", exc_info=True)
            return False
    
    async def _handle_sl_hit(self) -> bool:
        """Handle SL_HIT state - manage SL hits and re-entry."""
        try:
            # Check if we can re-enter
            if self.reentry_count < STRICT_CONFIG.max_reentries:
                await self._transition_to(TradeState.REENTRY_ATTEMPT)
            else:
                await self._transition_to(TradeState.CLOSED)
            
            return True
            
        except Exception as e:
            system_logger.error(f"SL hit handler error: {e}", exc_info=True)
            return False
    
    async def _handle_hedge_active(self) -> bool:
        """Handle HEDGE_ACTIVE state - manage hedge position."""
        try:
            # Implement hedge logic
            await self._manage_hedge()
            await self._transition_to(TradeState.RUNNING)
            return True
            
        except Exception as e:
            system_logger.error(f"Hedge active handler error: {e}", exc_info=True)
            return False
    
    async def _handle_reentry_attempt(self) -> bool:
        """Handle REENTRY_ATTEMPT state - attempt re-entry."""
        try:
            self.reentry_count += 1
            
            # Attempt re-entry
            success = await self._attempt_reentry()
            if success:
                await self._transition_to(TradeState.ENTRY_PLACED)
            else:
                await self._transition_to(TradeState.CLOSED)
            
            return True
            
        except Exception as e:
            system_logger.error(f"Re-entry attempt handler error: {e}", exc_info=True)
            return False
    
    async def _handle_closed(self) -> bool:
        """Handle CLOSED state - finalize trade."""
        try:
            # Record final trade data
            await self._record_trade_completion()
            
            system_logger.info(f"Trade {self.trade_id} completed", {
                'symbol': self.signal_data['symbol'],
                'final_pnl': str(self.current_pnl),
                'pyramid_level': self.pyramid_level,
                'hedge_count': self.hedge_count,
                'reentry_count': self.reentry_count
            })
            
            return True
            
        except Exception as e:
            system_logger.error(f"Closed handler error: {e}", exc_info=True)
            return False
    
    async def _handle_error(self) -> bool:
        """Handle ERROR state - error recovery."""
        try:
            system_logger.error(f"Trade {self.trade_id} entered error state", {
                'symbol': self.signal_data['symbol'],
                'error_count': self.error_count,
                'state': self.state.value
            })
            
            # Attempt to close position
            await self._emergency_close()
            await self._transition_to(TradeState.CLOSED)
            
            return True
            
        except Exception as e:
            system_logger.error(f"Error handler error: {e}", exc_info=True)
            return False
    
    def _validate_signal(self) -> bool:
        """Validate signal data."""
        required_fields = ['symbol', 'direction', 'entries', 'leverage', 'mode']
        for field in required_fields:
            if field not in self.signal_data:
                system_logger.error(f"Missing required field: {field}")
                return False
        
        if not self.signal_data.get('tps') and not self.signal_data.get('sl'):
            system_logger.error("Signal must have at least one TP or SL")
            return False
        
        return True
    
    async def _check_capacity(self) -> bool:
        """Check if we can open new trade."""
        # This would check against the 100 trade limit
        # Implementation depends on your trade tracking system
        return True
    
    async def _calculate_position_size(self) -> Decimal:
        """Calculate position size based on risk management."""
        # This would implement the 2% risk, 20 USDT IM logic
        # Implementation depends on your risk management system
        return Decimal("0.001")  # Placeholder
    
    async def _set_leverage_operation(self) -> Dict[str, Any]:
        """Set leverage operation for confirmation gate."""
        # This would call Bybit to set leverage
        return {'retCode': 0}  # Placeholder
    
    async def _leverage_confirmed_callback(self, result: Dict[str, Any]):
        """Callback when leverage is confirmed."""
        pass  # Placeholder
    
    async def _get_position(self) -> Optional[Dict[str, Any]]:
        """Get current position from Bybit."""
        # This would call Bybit to get position
        return None  # Placeholder
    
    async def _check_tp_hit(self) -> bool:
        """Check if TP was hit."""
        return False  # Placeholder
    
    async def _check_sl_hit(self) -> bool:
        """Check if SL was hit."""
        return False  # Placeholder
    
    async def _check_hedge_trigger(self) -> bool:
        """Check if hedge should be triggered."""
        return False  # Placeholder
    
    async def _check_pyramid_levels(self):
        """Check and handle pyramid levels."""
        pass  # Placeholder
    
    async def _check_trailing_stop(self):
        """Check and handle trailing stop."""
        pass  # Placeholder
    
    async def _move_to_breakeven(self):
        """Move SL to breakeven after TP2."""
        pass  # Placeholder
    
    async def _manage_hedge(self):
        """Manage hedge position."""
        pass  # Placeholder
    
    async def _attempt_reentry(self) -> bool:
        """Attempt re-entry after SL."""
        return False  # Placeholder
    
    async def _record_trade_completion(self):
        """Record trade completion in database."""
        pass  # Placeholder
    
    async def _emergency_close(self):
        """Emergency close position."""
        pass  # Placeholder