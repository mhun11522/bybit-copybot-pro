"""Strict FSM for trade lifecycle management."""

import asyncio
from enum import Enum
from typing import Dict, Any, Optional, Callable
from decimal import Decimal, ROUND_DOWN
from datetime import datetime
from app.core.logging import system_logger, trade_logger
from app.core.strict_config import STRICT_CONFIG
from app.core.confirmation_gate import get_confirmation_gate
from app.strategies.pyramid_v2 import PyramidStrategyV2
from app.strategies.trailing_v2 import TrailingStopStrategyV2
from app.strategies.hedge_v2 import HedgeStrategyV2
from app.strategies.reentry_v2 import ReentryStrategyV2

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
        # Validate signal data
        self._validate_signal_data(signal_data)
        self.signal_data = signal_data
        self.state = TradeState.INIT
        self.trade_id = f"{signal_data['symbol']}_{int(datetime.now().timestamp())}"
        self.entry_orders = []
        self.exit_orders = []
        self.position_size = Decimal("0")
        self.entry_price = Decimal("0")
        self.original_entry = Decimal("0")  # Store original entry for pyramid calculations
        self.current_pnl = Decimal("0")
        self.pyramid_level = 0
        self.trailing_active = False
        self.hedge_count = 0
        self.reentry_count = 0
        self.error_count = 0
        self.max_errors = 3
        
        # Initialize strategies
        self.pyramid_strategy = None
        self.trailing_strategy = None
        self.hedge_strategy = None
        self.reentry_strategy = None
        
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
    
    def _validate_signal_data(self, signal_data: Dict[str, Any]) -> None:
        """Validate signal data before processing."""
        required_fields = ['symbol', 'direction', 'mode', 'entries', 'leverage', 'channel_name']
        
        for field in required_fields:
            if field not in signal_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate symbol format
        symbol = signal_data['symbol']
        if not isinstance(symbol, str) or not symbol.endswith('USDT'):
            raise ValueError(f"Invalid symbol format: {symbol}")
        
        # Validate direction
        direction = signal_data['direction']
        if direction not in ['LONG', 'SHORT']:
            raise ValueError(f"Invalid direction: {direction}")
        
        # Validate mode (CLIENT SPEC: SWING, DYNAMIC, FIXED only)
        mode = signal_data['mode']
        if mode not in ['SWING', 'DYNAMIC', 'FIXED']:
            raise ValueError(f"Invalid mode: {mode}")
        
        # Validate entries
        entries = signal_data['entries']
        if not isinstance(entries, list) or len(entries) == 0:
            raise ValueError("Entries must be a non-empty list")
        
        # Validate leverage
        leverage = signal_data['leverage']
        if not isinstance(leverage, (int, float, Decimal)) or leverage <= 0 or leverage > 100:
            raise ValueError(f"Invalid leverage: {leverage}")
        
        # Validate channel name
        channel_name = signal_data['channel_name']
        if not isinstance(channel_name, str) or len(channel_name) == 0:
            raise ValueError("Channel name must be a non-empty string")
    
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
        # Check trade limit before starting
        from app.core.trade_limiter import get_trade_limiter
        trade_limiter = get_trade_limiter()
        
        if not trade_limiter.can_start_trade(self.signal_data['symbol']):
            system_logger.warning(f"Trade limit reached, rejecting signal for {self.signal_data['symbol']}", {
                'symbol': self.signal_data['symbol'],
                'active_trades': trade_limiter.get_active_trades()['count'],
                'max_trades': trade_limiter.max_trades
            })
            return False
        
        # Register this trade
        if not trade_limiter.start_trade(self.trade_id, self.signal_data['symbol']):
            system_logger.error(f"Failed to register trade {self.trade_id}")
            return False
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
            
            # Save initial trade to database
            await self._save_trade_to_database()
            
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
            # Handle MARKET entries properly
            processed_entries = []
            for e in self.signal_data['entries']:
                if e == "MARKET":
                    processed_entries.append("MARKET")
                else:
                    processed_entries.append(Decimal(e))
            
            # Extract TPs and SL for template data
            tps = self.signal_data.get('tps', [])
            sl = self.signal_data.get('sl')
            
            success = await gate.place_entry_orders(
                self.signal_data['symbol'],
                self.signal_data['direction'],
                processed_entries,
                self.position_size,
                Decimal(str(self.signal_data['leverage'])),
                self.signal_data['channel_name'],
                tps=tps,
                sl=sl
            )
            
            if success:
                await self._transition_to(TradeState.ENTRY_FILLED)
            else:
                await self._transition_to(TradeState.ERROR)
            
            return success
            
        except Exception as e:
            error_msg = str(e)
            if "closed symbol error" in error_msg or "not live" in error_msg:
                system_logger.warning(f"Symbol {self.signal_data['symbol']} is not tradeable on Bybit", {
                    'symbol': self.signal_data['symbol'],
                    'error': error_msg
                })
            else:
                system_logger.error(f"Entry placed handler error: {e}", exc_info=True)
            await self._transition_to(TradeState.ERROR)
            return False
    
    async def _handle_entry_filled(self) -> bool:
        """Handle ENTRY_FILLED state - monitor for fills."""
        try:
            # Initialize timeout counter if not exists
            if not hasattr(self, '_fill_check_count'):
                self._fill_check_count = 0
                # PostOnly orders may take longer to fill (waiting for exact price)
                self._max_fill_checks = 300  # 5 minutes timeout for PostOnly orders
            
            # Check for position
            position = await self._get_position()
            if position and float(position.get('size', 0)) > 0:
                self.entry_price = Decimal(str(position.get('avgPrice', 0)))
                self.original_entry = self.entry_price  # Store for pyramid calculations
                
                # Update position size from actual filled position
                self.position_size = Decimal(str(position.get('size', 0)))
                
                # Initialize strategies now that we have entry price
                self._initialize_strategies()
                
                # Update database with actual entry price and position size
                await self._save_trade_to_database()
                
                system_logger.info(f"Position filled for {self.signal_data['symbol']}: {position.get('size')} contracts at {self.entry_price}")
                await self._transition_to(TradeState.TP_SL_PLACED)
                return True
            else:
                # Increment check counter
                self._fill_check_count += 1
                
                # Check if timeout reached
                if self._fill_check_count >= self._max_fill_checks:
                    system_logger.warning(f"Entry fill timeout for {self.signal_data['symbol']} after {self._max_fill_checks} seconds")
                    await self._transition_to(TradeState.ERROR)
                    return False
                
                # Wait for fill (only log every 10 checks to reduce spam)
                if self._fill_check_count % 10 == 0:
                    system_logger.debug(f"Waiting for fill for {self.signal_data['symbol']} (check {self._fill_check_count}/{self._max_fill_checks})")
                
                await asyncio.sleep(1)
                return True
                
        except Exception as e:
            system_logger.error(f"Entry filled handler error: {e}", exc_info=True)
            return False
    
    async def _handle_tp_sl_placed(self) -> bool:
        """Handle TP_SL_PLACED state - place TP/SL orders."""
        try:
            gate = get_confirmation_gate()
            
            # Get TP/SL values from signal data
            tps = self.signal_data.get('tps', [])
            sl = self.signal_data.get('sl')
            
            system_logger.info(f"Placing TP/SL orders for {self.signal_data['symbol']}: TPs={tps}, SL={sl}")
            
            # Convert TP values to Decimal
            tp_decimals = []
            if tps:
                for tp in tps:
                    if tp and tp != "DEFAULT_TP":
                        tp_decimals.append(Decimal(str(tp)))
                    else:
                        tp_decimals.append("DEFAULT_TP")
            else:
                tp_decimals = ["DEFAULT_TP"]  # Use default TP if none specified
            
            # Convert SL to Decimal
            sl_decimal = None
            if sl and sl != "DEFAULT_SL":
                sl_decimal = Decimal(str(sl))
            else:
                sl_decimal = "DEFAULT_SL"  # Use default SL if none specified
            
            # Place TP/SL orders through confirmation gate
            success = await gate.place_exit_orders(
                self.signal_data['symbol'],
                self.signal_data['direction'],
                self.position_size,
                tp_decimals,
                sl_decimal,
                self.signal_data['channel_name'],
                entry_price=self.entry_price  # Pass actual entry price from position
            )
            
            if success:
                system_logger.info(f"TP/SL orders placed successfully for {self.signal_data['symbol']}")
                await self._transition_to(TradeState.RUNNING)
            else:
                system_logger.warning(f"TP/SL orders failed for {self.signal_data['symbol']}, but position is still active")
                system_logger.warning(f"Continuing to RUNNING state - TP/SL can be added manually if needed")
                await self._transition_to(TradeState.RUNNING)
            
            return success
            
        except Exception as e:
            system_logger.error(f"TP/SL placed handler error for {self.signal_data['symbol']}: {e}", exc_info=True)
            return False
    
    async def _handle_running(self) -> bool:
        """Handle RUNNING state - monitor position and manage strategies."""
        try:
            # Check position status
            position = await self._get_position()
            if not position or float(position.get('size', 0)) == 0:
                # Position closed
                system_logger.info(f"Position closed for {self.signal_data['symbol']}, transitioning to CLOSED")
                await self._transition_to(TradeState.CLOSED)
                return True
            
            # Update PnL
            self.current_pnl = Decimal(str(position.get('unrealisedPnl', 0)))
            
            # Check for TP hits
            try:
                if await self._check_tp_hit():
                    system_logger.info(f"TP hit detected for {self.signal_data['symbol']}")
                    await self._transition_to(TradeState.TP_HIT)
                    return True
            except Exception as e:
                system_logger.warning(f"TP hit check failed for {self.signal_data['symbol']}: {e}")
            
            # Check for SL hits
            try:
                if await self._check_sl_hit():
                    system_logger.info(f"SL hit detected for {self.signal_data['symbol']}")
                    await self._transition_to(TradeState.SL_HIT)
                    return True
            except Exception as e:
                system_logger.warning(f"SL hit check failed for {self.signal_data['symbol']}: {e}")
            
            # Check for hedge trigger (only if hedge strategy is active)
            try:
                if self.hedge_strategy:
                    if await self._check_hedge_trigger():
                        system_logger.info(f"Hedge trigger detected for {self.signal_data['symbol']}")
                        await self._transition_to(TradeState.HEDGE_ACTIVE)
                        return True
            except Exception as e:
                system_logger.warning(f"Hedge trigger check failed for {self.signal_data['symbol']}: {e}")
            
            # Check for pyramid levels (only if pyramid strategy is active)
            try:
                if self.pyramid_strategy:
                    await self._check_pyramid_levels()
            except Exception as e:
                system_logger.warning(f"Pyramid levels check failed for {self.signal_data['symbol']}: {e}")
            
            # Check for trailing stop (only if trailing strategy is active)
            try:
                if self.trailing_strategy:
                    await self._check_trailing_stop()
            except Exception as e:
                system_logger.warning(f"Trailing stop check failed for {self.signal_data['symbol']}: {e}")
            
            # Brief pause before next check
            await asyncio.sleep(1)
            return True
            
        except Exception as e:
            system_logger.error(f"Running handler error for {self.signal_data['symbol']}: {e}", exc_info=True)
            # Don't transition to ERROR, just log and continue
            await asyncio.sleep(1)
            return True
    
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
            # Unregister trade from limiter
            from app.core.trade_limiter import get_trade_limiter
            trade_limiter = get_trade_limiter()
            trade_limiter.end_trade(self.trade_id)
            
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
            
            # Unregister trade from limiter
            from app.core.trade_limiter import get_trade_limiter
            trade_limiter = get_trade_limiter()
            trade_limiter.end_trade(self.trade_id)
            
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
        """Calculate position size based on risk management using proper contract-based logic."""
        try:
            from app.core.symbol_registry import get_symbol_registry
            from app.core.position_calculator import PositionCalculator
            from app.bybit.client import get_bybit_client
            
            # Get account balance
            client = get_bybit_client()
            balance_data = await client.wallet_balance("USDT")
            if not balance_data:
                system_logger.error("Failed to get account balance - no response")
                return Decimal("0")
            
            # Check if the response has the expected structure
            if 'result' in balance_data and 'list' in balance_data['result'] and balance_data['result']['list']:
                # Extract balance from the list format
                account_info = balance_data['result']['list'][0]
                balance = Decimal(str(account_info.get('totalWalletBalance', '0')))
            elif 'totalWalletBalance' in balance_data:
                balance = Decimal(str(balance_data['totalWalletBalance']))
            else:
                system_logger.error(f"Unexpected balance data format: {balance_data}")
                # Use default balance for testing
                balance = Decimal("1000.0")
                system_logger.warning(f"Using default balance: {balance}")
            
            if balance <= 0:
                system_logger.error(f"Invalid balance: {balance}, using default")
                balance = Decimal("1000.0")  # Default for testing
            
            # Get entry price (use first entry)
            entry_price = self.signal_data['entries'][0]
            if entry_price == "MARKET":
                # For market entries, we'll need to get current price
                ticker_response = await client.get_ticker(self.signal_data['symbol'])
                if ticker_response and 'result' in ticker_response and 'list' in ticker_response['result'] and ticker_response['result']['list']:
                    # Extract lastPrice from the first ticker in the list
                    ticker_data = ticker_response['result']['list'][0]
                    if 'lastPrice' in ticker_data:
                        entry_price = Decimal(str(ticker_data['lastPrice']))
                    else:
                        system_logger.error(f"No lastPrice in ticker data for {self.signal_data['symbol']}")
                        return Decimal("0")
                else:
                    system_logger.error(f"Failed to get market price for {self.signal_data['symbol']}: {ticker_response}")
                    return Decimal("0")
            else:
                entry_price = Decimal(str(entry_price))
            
            # Get leverage
            leverage = self.signal_data.get('leverage', Decimal('10'))
            if isinstance(leverage, (int, float)):
                leverage = Decimal(str(leverage))
            
            # Get channel risk multiplier
            channel_name = self.signal_data.get('channel_name', 'DEFAULT')
            from app.config.trading_config import get_channel_risk_multiplier
            risk_multiplier = Decimal(str(get_channel_risk_multiplier(channel_name)))
            
            # Get symbol metadata
            symbol = self.signal_data['symbol']
            registry = get_symbol_registry()
            symbol_info = await registry.get_symbol_info(symbol)
            
            if not symbol_info:
                system_logger.error(f"Symbol info not found for {symbol}")
                return Decimal("0")
            
            # Use the new position calculator
            position_size, debug_info = await PositionCalculator.calculate_contract_qty(
                symbol=symbol,
                wallet_balance=balance,
                risk_pct=STRICT_CONFIG.risk_pct,
                leverage=leverage,
                entry_price=entry_price,
                symbol_info=symbol_info,
                channel_risk_multiplier=risk_multiplier
            )
            
            return position_size
            
        except Exception as e:
            system_logger.error(f"Position size calculation failed: {e}", exc_info=True)
            return Decimal("0")
    
    async def _set_leverage_operation(self) -> Dict[str, Any]:
        """Set leverage operation for confirmation gate."""
        try:
            from app.bybit.client import BybitClient
            from app.core.symbol_registry import get_symbol_registry
            
            client = BybitClient()
            symbol = self.signal_data['symbol']
            leverage = self.signal_data['leverage']
            
            # Check symbol's maximum leverage limit
            registry = get_symbol_registry()
            symbol_info = await registry.get_symbol_info(symbol)
            
            if symbol_info:
                max_leverage = symbol_info.max_leverage
                if leverage > max_leverage:
                    system_logger.warning(f"Leverage {leverage}x exceeds max {max_leverage}x for {symbol}, adjusting")
                    leverage = max_leverage
                    # Update signal data with adjusted leverage
                    self.signal_data['leverage'] = leverage
            
            # Set leverage on Bybit with fallback mechanism
            fallback_leverages = [leverage, 10, 5, 3, 1]  # Try progressively lower leverage
            
            for attempt_leverage in fallback_leverages:
                result = await client.set_leverage(
                    category="linear",
                    symbol=symbol,
                    buy_leverage=str(attempt_leverage),
                    sell_leverage=str(attempt_leverage)
                )
                
                if result.get('retCode') == 0:
                    if attempt_leverage != leverage:
                        system_logger.warning(f"Leverage adjusted from {leverage}x to {attempt_leverage}x for {symbol}")
                        # Update signal data with adjusted leverage
                        self.signal_data['leverage'] = attempt_leverage
                    system_logger.info(f"Leverage set successfully: {symbol} = {attempt_leverage}x")
                    return result
                else:
                    system_logger.warning(f"Failed to set {attempt_leverage}x leverage for {symbol}: {result.get('retMsg', 'Unknown error')}")
                    continue
            
            # If all attempts failed
            system_logger.error(f"Failed to set any leverage for {symbol} after trying all fallback values")
            return result
                
        except Exception as e:
            system_logger.error(f"Leverage setting error: {e}", exc_info=True)
            return {'retCode': -1, 'retMsg': str(e)}
    
    async def _leverage_confirmed_callback(self, result: Dict[str, Any]):
        """Callback when leverage is confirmed."""
        pass  # Placeholder
    
    async def _get_position(self) -> Optional[Dict[str, Any]]:
        """Get current position from Bybit."""
        try:
            from app.bybit.client import get_bybit_client
            client = get_bybit_client()
            
            # Initialize position check counter if not exists
            if not hasattr(self, '_position_check_count'):
                self._position_check_count = 0
            
            # Get position from Bybit
            result = await client.get_position(
                category="linear",
                symbol=self.signal_data['symbol']
            )
            
            if result.get('retCode') == 0:
                positions = result.get('result', {}).get('list', [])
                if positions:
                    position = positions[0]
                    size = float(position.get('size', 0))
                    if size > 0:  # Only return if we have a position
                        # Only log positions that we're actively managing (not existing positions)
                        # Check if we have a trade_id or are in an active state
                        if hasattr(self, 'trade_id') and self.trade_id:
                            # Only log once per position to avoid spam
                            if not hasattr(self, '_position_logged') or not self._position_logged:
                                system_logger.info(f"Position found for {self.signal_data['symbol']}: {size} contracts")
                                self._position_logged = True
                        return position
                    else:
                        # Only log every 10th check to reduce spam
                        self._position_check_count += 1
                        if self._position_check_count % 10 == 0:
                            system_logger.debug(f"No position found for {self.signal_data['symbol']} (check {self._position_check_count})")
                else:
                    # Only log every 10th check to reduce spam
                    self._position_check_count += 1
                    if self._position_check_count % 10 == 0:
                        system_logger.debug(f"No positions in result for {self.signal_data['symbol']} (check {self._position_check_count})")
            else:
                system_logger.warning(f"Position API error for {self.signal_data['symbol']}: {result.get('retMsg', 'Unknown error')}")
            
            return None
            
        except Exception as e:
            system_logger.error(f"Failed to get position for {self.signal_data['symbol']}: {e}", exc_info=True)
            return None
    
    async def _check_tp_hit(self) -> bool:
        """Check if TP was hit."""
        return False  # Placeholder
    
    async def _check_sl_hit(self) -> bool:
        """Check if SL was hit."""
        return False  # Placeholder
    
    async def _check_hedge_trigger(self) -> bool:
        """Check if hedge should be triggered."""
        if not self.hedge_strategy:
            return False
            
        # If hedge is already activated, don't check again
        if self.hedge_strategy.activated:
            return False
            
        try:
            # Get current price from position
            position = await self._get_position()
            if not position:
                # No position found - transition to CLOSED state to stop hedge checks
                system_logger.warning(f"No position found for {self.signal_data['symbol']} - transitioning to CLOSED")
                await self._transition_to(TradeState.CLOSED)
                return False
                
            current_price = Decimal(str(position.get('markPrice', 0)))
            if current_price > 0:
                activated = await self.hedge_strategy.check_and_activate(current_price, self.original_entry)
                if activated:
                    system_logger.info(f"Hedge strategy activated for {self.signal_data['symbol']}")
                    return True
        except Exception as e:
            system_logger.error(f"Hedge trigger check error: {e}", exc_info=True)
        
        return False
    
    def _initialize_strategies(self):
        """Initialize all trading strategies."""
        try:
            channel_name = self.signal_data.get('channel_name', 'Unknown')
            
            # Initialize Pyramid Strategy
            self.pyramid_strategy = PyramidStrategyV2(
                trade_id=self.trade_id,
                symbol=self.signal_data['symbol'],
                direction=self.signal_data['direction'],
                original_entry=self.original_entry,
                channel_name=channel_name
            )
            
            # Initialize Trailing Stop Strategy
            self.trailing_strategy = TrailingStopStrategyV2(
                trade_id=self.trade_id,
                symbol=self.signal_data['symbol'],
                direction=self.signal_data['direction'],
                channel_name=channel_name
            )
            
            # Initialize Hedge Strategy
            self.hedge_strategy = HedgeStrategyV2(
                trade_id=self.trade_id,
                symbol=self.signal_data['symbol'],
                direction=self.signal_data['direction'],
                original_entry=self.original_entry,
                channel_name=channel_name
            )
            
            # Initialize Re-entry Strategy
            self.reentry_strategy = ReentryStrategyV2(
                trade_id=self.trade_id,
                symbol=self.signal_data['symbol'],
                direction=self.signal_data['direction'],
                channel_name=channel_name
            )
            
            system_logger.info(f"Strategies initialized for {self.signal_data['symbol']}")
            
        except Exception as e:
            system_logger.error(f"Strategy initialization error: {e}", exc_info=True)

    async def _check_pyramid_levels(self):
        """Check and handle pyramid levels."""
        if not self.pyramid_strategy:
            return
            
        try:
            # Get current price from position
            position = await self._get_position()
            if position:
                current_price = Decimal(str(position.get('markPrice', 0)))
                if current_price > 0:
                    activated = await self.pyramid_strategy.check_and_activate(current_price)
                    if activated:
                        self.pyramid_level += 1
                        system_logger.info(f"Pyramid level {self.pyramid_level} activated for {self.signal_data['symbol']}")
        except Exception as e:
            system_logger.error(f"Pyramid check error: {e}", exc_info=True)
            # Don't let pyramid errors crash the trade
            # Continue with normal trade flow
    
    async def _check_trailing_stop(self):
        """Check and handle trailing stop."""
        if not self.trailing_strategy:
            return
            
        try:
            # Get current price from position
            position = await self._get_position()
            if position:
                current_price = Decimal(str(position.get('markPrice', 0)))
                if current_price > 0:
                    updated = await self.trailing_strategy.check_and_update(current_price, self.original_entry)
                    if updated and not self.trailing_active:
                        self.trailing_active = True
                        system_logger.info(f"Trailing stop activated for {self.signal_data['symbol']}")
        except Exception as e:
            system_logger.error(f"Trailing stop check error: {e}", exc_info=True)
    
    async def _move_to_breakeven(self):
        """Move SL to breakeven after TP2."""
        pass  # Placeholder
    
    async def _manage_hedge(self):
        """Manage hedge position."""
        pass  # Placeholder
    
    async def _attempt_reentry(self) -> bool:
        """Attempt re-entry after SL."""
        if not self.reentry_strategy:
            return False
            
        try:
            # Get current market price
            from app.bybit.client import get_bybit_client
            client = get_bybit_client()
            
            # Get ticker for current price
            ticker_result = await client.get_ticker("linear", self.signal_data['symbol'])
            if ticker_result.get('retCode') == 0:
                ticker = ticker_result.get('result', {}).get('list', [])
                if ticker:
                    current_price = Decimal(str(ticker[0].get('lastPrice', 0)))
                    if current_price > 0:
                        success = await self.reentry_strategy.attempt_reentry(current_price)
                        if success:
                            system_logger.info(f"Re-entry attempted for {self.signal_data['symbol']} at {current_price}")
                            return True
                        else:
                            system_logger.info(f"Re-entry conditions not met for {self.signal_data['symbol']}")
            
        except Exception as e:
            system_logger.error(f"Re-entry attempt error: {e}", exc_info=True)
        
        return False
    
    async def _save_trade_to_database(self):
        """Save trade data to database."""
        try:
            from app.storage.db import save_trade
            
            # Save trade data to database
            await save_trade(
                trade_id=self.trade_id,
                symbol=self.signal_data['symbol'],
                direction=self.signal_data['direction'],
                entry_price=float(self.entry_price or 0),  # Use 0 if entry_price not set yet
                size=float(self.position_size),
                state=self.state.value
            )
            
            system_logger.info(f"Trade {self.trade_id} saved to database", {
                'symbol': self.signal_data['symbol'],
                'state': self.state.value,
                'entry_price': float(self.entry_price or 0),
                'position_size': float(self.position_size)
            })
            
        except Exception as e:
            system_logger.error(f"Failed to save trade to database: {e}", exc_info=True)
    
    async def _record_trade_completion(self):
        """Record trade completion in database."""
        try:
            # Update trade with final data
            await self._save_trade_to_database()
            
            system_logger.info(f"Trade {self.trade_id} completion recorded", {
                'symbol': self.signal_data['symbol'],
                'final_state': self.state.value,
                'final_pnl': str(self.current_pnl),
                'pyramid_level': self.pyramid_level
            })
            
        except Exception as e:
            system_logger.error(f"Failed to record trade completion: {e}", exc_info=True)
    
    async def _emergency_close(self):
        """Emergency close position."""
        pass  # Placeholder