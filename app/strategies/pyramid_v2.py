"""
Pyramid strategy implementation with exact client requirements.

CLIENT SPEC COMPLIANCE (doc/10_15.md Lines 365-377):
- All triggers calculated from original_entry_price (IMMUTABLE)
- +1.5%: IM check = 20 USDT
- +2.3%: SL → BE + 0.0015%
- +2.4%: Leverage → max (LEVERAGE-ONLY, no qty/IM) - "Pyramid Step 4" in templates
- +2.5%: IM → 40 USDT total
- +4.0%: IM → 60; +6.0%: IM → 80; +8.6%: IM → 100

CRITICAL: +2.4% step MUST be leverage-only (forbid qty_add/im_add per CLIENT SPEC)
"""

from decimal import Decimal
from typing import Dict, Any
from app.bybit.client import BybitClient
from app.core.logging import system_logger
from app.telegram.output import send_message
from app.telegram.engine import render_template
from app.core.confirmation_gate import ConfirmationGate

class PyramidStrategyV2:
    """
    Pyramid strategy with exact client requirements.
    
    Step numbering harmonization (CLIENT SPEC):
    - Code index 2 (+2.4% leverage-only) = "Pyramid Step 4" in templates
    - This ensures template messages match code behavior
    """
    
    def __init__(self, trade_id: str, symbol: str, direction: str, original_entry: Decimal, channel_name: str):
        self.trade_id = trade_id
        self.symbol = symbol
        self.direction = direction.upper()
        self.original_entry = original_entry
        self.channel_name = channel_name
        from app.bybit.client import get_bybit_client
        self.bybit = get_bybit_client()
        
        # CLIENT FIX (COMPLIANCE doc/10_12_2.md Lines 291-325):
        # Read pyramid levels from STRICT_CONFIG instead of hardcoding
        # Pyramid levels calculated from ORIGINAL ENTRY as per CLIENT SPECIFICATION
        # CRITICAL: All percentages calculated from ORIGINAL ENTRY, not current price
        from app.core.strict_config import STRICT_CONFIG
        
        self.levels = {}
        for level_config in STRICT_CONFIG.pyramid_levels:
            trigger = level_config["trigger"]
            action = level_config["action"]
            # Convert to dict format expected by existing logic
            level_dict = {"action": action}
            if "target_im" in level_config:
                level_dict["target_im"] = Decimal(str(level_config["target_im"]))
            if "leverage_cap" in level_config:
                level_dict["leverage_cap"] = Decimal(str(level_config["leverage_cap"]))
            
            self.levels[trigger] = level_dict
        
        self.activated_levels = set()
        self.max_adds = len(STRICT_CONFIG.pyramid_levels)  # Dynamic based on config
    
    async def check_and_activate(self, current_price: Decimal) -> bool:
        """Check if pyramid levels should be activated."""
        # Calculate gain from original entry
        if self.direction == "LONG":
            gain_pct = (current_price - self.original_entry) / self.original_entry * 100
        else:  # SHORT
            gain_pct = (self.original_entry - current_price) / self.original_entry * 100
        
        # Check each level
        for level_pct, config in self.levels.items():
            if gain_pct >= level_pct and level_pct not in self.activated_levels:
                await self._activate_level(level_pct, config, gain_pct)
                self.activated_levels.add(level_pct)
                return True
        
        return False
    
    async def _activate_level(self, level_pct: Decimal, config: Dict[str, Any], gain_pct: Decimal):
        """
        Activate a pyramid level based on action type.
        
        CLIENT SPEC: Enforces leverage-only constraint at +2.4% step.
        """
        try:
            level_num = len(self.activated_levels) + 1
            action = config.get("action", "")
            
            # CLIENT SPEC VALIDATION: At +2.4%, ONLY leverage changes allowed
            # This is called "Pyramid Step 4" in Telegram templates (doc/requirement.txt Line 10)
            if level_pct == STRICT_CONFIG.pyramid_step4_trigger:
                if action != "set_full_leverage":
                    error_msg = (
                        f"Pyramid +2.4% (Template 'Step 4') MUST be leverage-only. "
                        f"Found action: {action}. "
                        f"CLIENT SPEC: doc/requirement.txt Lines 33-41"
                    )
                    system_logger.error(
                        f"CLIENT SPEC VIOLATION: +2.4% step must be leverage-only",
                        {
                            "symbol": self.symbol,
                            "trigger": "+2.4%",
                            "template_name": "Pyramid Step 4",
                            "action": action,
                            "expected": "set_full_leverage",
                            "max_leverage": "50x"
                        }
                    )
                    raise ValueError(error_msg)
                
                # Enforce max leverage cap of 50x for this step
                    leverage_cap = config.get("leverage_cap", STRICT_CONFIG.pyramid_leverage_cap)
                if leverage_cap > STRICT_CONFIG.pyramid_leverage_cap:
                    system_logger.warning(
                        f"Leverage cap {leverage_cap} exceeds Step 4 max (50x), clamping",
                        {"symbol": self.symbol, "requested": str(leverage_cap), "capped": "50"}
                    )
                    config["leverage_cap"] = STRICT_CONFIG.pyramid_leverage_cap
            
            success = False
            
            if action == "im_check":
                # Step 1: Check that IM is 20 USDT if any TP has been hit
                # This is a validation step, not an action
                target_im = config.get("target_im", 20)
                
                # Fetch current IM from Bybit
                from app.core.confirmation_gate import get_confirmation_gate
                gate = get_confirmation_gate()
                im_confirmed = await gate._fetch_confirmed_im(self.symbol)
                
                if im_confirmed < Decimal(str(target_im)):
                    system_logger.warning(
                        f"Pyramid Step 1: IM check failed",
                        {
                            "symbol": self.symbol,
                            "current_im": float(im_confirmed),
                            "expected_im": target_im
                        }
                    )
                else:
                    system_logger.info(
                        f"Pyramid Step 1: IM check passed",
                        {
                            "symbol": self.symbol,
                            "current_im": float(im_confirmed),
                            "expected_im": target_im
                        }
                    )
                success = True
            
            elif action == "im_total":
                # Steps 1, 4, 5, 6, 7: IM increased to target total
                # CLIENT SPEC: This action NOT allowed at +2.4%
                target_im = config.get("target_im", STRICT_CONFIG.pyramid_position_size)
                success = await self._update_position_size_to_total_im(target_im)
                
            elif action == "sl_breakeven":
                # Step 2: +2.3%: SL is moved to breakeven + costs
                success = await self._move_sl_to_breakeven()
                
            elif action == "set_full_leverage":
                # Step 3 (code) / Step 4 (templates): +2.4%: LEVERAGE-ONLY
                # CLIENT SPEC: ETH=50x cap, others=instrument max
                success = await self._set_full_leverage()
                
            elif action == "add_im":
                # Legacy action name - treat as im_total
                # CLIENT SPEC: This action NOT allowed at +2.4%
                target_im = config.get("target_im", STRICT_CONFIG.pyramid_position_size)
                success = await self._update_position_size_to_total_im(target_im)
            
            if success:
                # CLIENT FIX (DEEP_ANALYSIS): Verify Bybit actually confirmed before sending Telegram
                # Do NOT send Telegram if Bybit operation failed
                pos_data = await self.bybit.get_position("linear", self.symbol)
                
                # ✅ VERIFY Bybit returned success
                if pos_data.get('retCode') != 0:
                    system_logger.error(
                        f"Pyramid step executed locally but Bybit verification failed",
                        {
                            "symbol": self.symbol,
                            "level": level_num,
                            "action": action,
                            "retCode": pos_data.get('retCode'),
                            "retMsg": pos_data.get('retMsg')
                        }
                    )
                    return  # ❌ Do NOT send Telegram message
                
                # ✅ Bybit confirmed - proceed with message
                system_logger.info(f"Pyramid level {level_num} activated for {self.symbol} at +{gain_pct:.2f}% - Action: {action}")
                
                # Fetch exact IM from Bybit using singleton pattern
                from app.core.confirmation_gate import get_confirmation_gate
                gate = get_confirmation_gate()
                im_confirmed = await gate._fetch_confirmed_im(self.symbol)
                
                # Get position data (already fetched above for verification)
                qty_total = Decimal("0")
                current_leverage = Decimal("1")
                if pos_data.get("result", {}).get("list"):
                    position = pos_data["result"]["list"][0]
                    qty_total = Decimal(str(position.get("size", "0")))
                    current_leverage = Decimal(str(position.get("leverage", "1")))
                
                # CLIENT FIX: Calculate profit WITH LEVERAGE
                # gain_pct is the trade % (price movement)
                # Client requirement: Must show profit including leverage
                
                # PRIORITY 2: Use Engine queue instead of direct send_message
                # This provides rate limiting, retry logic, and centralized management
                from app.telegram.engine import get_template_engine
                engine = get_template_engine()
                
                # Prepare data for template
                template_data = {
                    'symbol': self.symbol,
                    'source_name': self.channel_name,
                    'side': self.direction,
                    'level': level_num,
                    'price': current_price,
                    'gain_pct': float(gain_pct),  # Trade % (price movement)
                    'leverage': current_leverage,  # FROM BYBIT!
                    'sl': getattr(self, 'sl', None),  # For type detection
                    'qty_added': Decimal("0"),  # Would need tracking
                    'qty_total': qty_total,
                    'im_added': Decimal("0"),  # Would need tracking
                    'trade_id': self.trade_id,
                    'bot_order_id': f"BOT-{self.trade_id}",
                    'bybit_order_id': ''
                }
                
                # Enqueue through Engine (includes rate limiting & retry)
                await engine.enqueue_and_send("PYRAMID_STEP", template_data, priority=3)
            else:
                system_logger.error(f"Pyramid action {action} failed for {self.symbol}; not sending activation message")
            
        except Exception as e:
            system_logger.error(f"Pyramid level activation error: {e}", exc_info=True)
    
    async def _check_im_20_if_tp_hit(self) -> bool:
        """Check that IM is 20 USDT if any TP has been hit."""
        try:
            # Get current position
            pos = await self.bybit.get_position("linear", self.symbol)
            
            # CRITICAL FIX: Check API return code first
            if pos.get('retCode') != 0:
                system_logger.error(f"Failed to get position for IM check: {pos.get('retMsg')}")
                return False
            
            if pos.get("result", {}).get("list"):
                position = pos["result"]["list"][0]
                current_im = Decimal(str(position.get("initialMargin", "0")))
                
                # Check if any TP has been hit by looking at position size vs original
                # If position size is reduced, it means some TPs were hit
                current_size = Decimal(str(position.get("size", "0")))
                
                # If IM is less than 20 USDT and TPs were hit, add to position
                if current_im < STRICT_CONFIG.pyramid_position_size and current_size > 0:
                    # Add to position to bring IM to target size
                    im_to_add = STRICT_CONFIG.pyramid_position_size - current_im
                    await self._add_im_to_position(im_to_add)
                    
                    system_logger.info(f"Added {im_to_add} USDT IM to bring total to 20 USDT for {self.symbol}")
                    return True
                else:
                    return True  # IM already at target or no position
            return False
        except Exception as e:
            system_logger.error(f"IM check error: {e}", exc_info=True)
            return False

    async def _move_sl_to_breakeven(self) -> bool:
        """Move SL to breakeven + costs."""
        try:
            # Get current position
            pos = await self.bybit.positions("linear", self.symbol)
            if pos.get("result", {}).get("list"):
                position = pos["result"]["list"][0]
                avg_price = Decimal(str(position.get("avgPrice", "0")))
                
                # Calculate breakeven + small buffer
                if self.direction == "LONG":
                    be_price = avg_price * STRICT_CONFIG.pyramid_price_tolerance_min  # Below entry
                else:  # SELL
                    be_price = avg_price * STRICT_CONFIG.pyramid_price_tolerance_max  # Above entry
                
                # Place new SL order
                order_body = {
                    "category": "linear",
                    "symbol": self.symbol,
                    "side": "Sell" if self.direction == "LONG" else "Buy",
                    "orderType": "Limit",
                    "qty": "0",  # Will be filled by position size
                    "price": str(be_price),
                    "timeInForce": "GTC",
                    "reduceOnly": True,
                    "positionIdx": 0,
                    "orderLinkId": f"be_{self.trade_id}"
                }
                
                result = await self.bybit.place_order(order_body)
                if result.get('retCode') == 0:
                    system_logger.info(f"SL moved to breakeven for {self.symbol}")
                    return True
                else:
                    system_logger.error(f"Failed to move SL to breakeven: {result}")
                    return False
            return False
                    
        except Exception as e:
            system_logger.error(f"Breakeven SL move error: {e}", exc_info=True)
            return False
    
    async def _set_full_leverage(self) -> bool:
        """
        Pyramid +2.4%: Set full leverage (LEVERAGE-ONLY, NO qty/IM changes).
        
        CLIENT SPEC (doc/10_15.md Lines 365-377):
        - This is the "Pyramid Step 4" referred to in templates (leverage-only step)
        - +2.4%: Leverage → max (to x50); RECOMPUTE position
        - CRITICAL: ONLY changes leverage, NEVER adds qty or IM
        - Templates require: "Pyramid Step 4" = leverage-only (forbid qty_add/im_add)
        
        RULES:
        - ETH: Set to 50x (capped by instrument max if lower)
        - Other symbols: Set to instrument max
        - NO qty changes
        - NO IM additions
        - Recompute position with new leverage (automatic by Bybit)
        """
        try:
            from app.core.leverage_policy import LeveragePolicy
            
            # Get instrument max leverage
            instrument_max = await LeveragePolicy.get_instrument_max_leverage(self.symbol)
            
            # Determine target leverage
            if "ETH" in self.symbol.upper():
                # ETH: min(50, instrument_max)
                target_leverage = min(STRICT_CONFIG.pyramid_leverage_cap, instrument_max)
                system_logger.info(f"ETH pyramid +2.4% (leverage-only): setting leverage to {target_leverage}x (cap=50x, instrument_max={instrument_max}x)")
            else:
                # Other symbols: use instrument max
                target_leverage = instrument_max
                system_logger.info(f"Pyramid +2.4% (leverage-only): setting leverage to instrument max {target_leverage}x for {self.symbol}")
            
            # CRITICAL CLIENT SPEC ENFORCEMENT:
            # This step ONLY changes leverage - no qty add, no IM add
            # Bybit will automatically recompute position with new leverage
            
            # Set leverage via Bybit API
            result = await self.bybit.set_leverage(
                category="linear",
                symbol=self.symbol,
                buy_leverage=str(target_leverage),
                sell_leverage=str(target_leverage)
            )
            
            # Check for success (retCode 0 or 110043 "leverage not modified")
            if result.get('retCode') in [0, 110043]:
                system_logger.info(
                    f"Leverage-only step complete: {target_leverage}x for {self.symbol}",
                    {
                        "symbol": self.symbol,
                        "trigger": "+2.4%",
                        "new_leverage": str(target_leverage),
                        "qty_added": "0",  # NEVER adds qty
                        "im_added": "0",   # NEVER adds IM
                        "action": "leverage_only"
                    }
                )
                return True
            else:
                system_logger.error(f"Failed to set full leverage: {result}")
                return False
                
        except Exception as e:
            system_logger.error(f"Set full leverage error: {e}", exc_info=True)
            return False
    
    async def _update_leverage(self, new_leverage: Decimal) -> bool:
        """
        Update leverage (legacy method, kept for compatibility).
        Use _set_full_leverage() for Step 3 instead.
        """
        try:
            result = await self.bybit.set_leverage(
                category="linear",
                symbol=self.symbol,
                buy_leverage=str(new_leverage),
                sell_leverage=str(new_leverage)
            )
            
            if result.get('retCode') in [0, 110043]:  # 0=success, 110043=no change needed
                system_logger.info(f"Leverage updated to {new_leverage}x for {self.symbol}")
                return True
            else:
                system_logger.error(f"Failed to update leverage: {result}")
                return False
        except Exception as e:
            system_logger.error(f"Leverage update error: {e}", exc_info=True)
            return False
    
    async def _update_position_size_to_total_im(self, target_im_total: Decimal) -> bool:
        """
        Update position size to reach target TOTAL IM (CLIENT SPEC).
        
        IMPORTANT: target_im_total is the TOTAL IM desired, not the amount to add.
        Calculate how much to add by: (target_total - current_im)
        
        Args:
            target_im_total: Target total IM in USDT (e.g., 20, 40, 60, 80, 100)
        
        Returns:
            True if successful or no action needed, False on error
        """
        try:
            # Get current position
            pos = await self.bybit.positions("linear", self.symbol)
            
            # CRITICAL FIX: Check API return code first
            if pos.get('retCode') != 0:
                system_logger.error(f"Failed to get position for IM update: {pos.get('retMsg')}")
                return False
            
            if pos.get("result", {}).get("list"):
                position = pos["result"]["list"][0]
                current_size = Decimal(str(position.get("size", "0")))
                current_im = Decimal(str(position.get("positionIM", "0")))  # Current IM
                avg_price = Decimal(str(position.get("avgPrice", "0")))
                leverage = Decimal(str(position.get("leverage", "1")))
                
                # Calculate IM to add
                im_to_add = target_im_total - current_im
                
                if im_to_add <= 0:
                    system_logger.info(f"IM already at or above target ({current_im} >= {target_im_total}), no action needed")
                    return True  # Already at target
                
                # Calculate additional size needed
                # Formula: additional_qty = (im_to_add * leverage) / price
                additional_size = (im_to_add * leverage) / avg_price
                
                # CRITICAL FIX: Quantize quantity to valid step size
                from app.core.symbol_registry import get_symbol_registry
                symbol_registry = get_symbol_registry()
                symbol_info = await symbol_registry.get_symbol_info(self.symbol)
                
                if symbol_info:
                    # Quantize to valid step size
                    additional_size = symbol_info.quantize_qty(additional_size)
                    
                    # Validate quantity meets minimum requirements
                    if not symbol_info.validate_qty(additional_size):
                        system_logger.error(f"Quantity {additional_size} invalid for {self.symbol} (min: {symbol_info.min_qty}, max: {symbol_info.max_qty})")
                        return False
                    
                    # Validate notional value
                    notional = additional_size * avg_price
                    if not symbol_info.validate_notional(notional):
                        system_logger.error(f"Notional {notional} too small for {self.symbol} (min: {symbol_info.min_notional})")
                        return False
                else:
                    system_logger.warning(f"No symbol info found for {self.symbol}, using raw quantity")
                
                system_logger.info(f"Adding {im_to_add} USDT IM to {self.symbol} (current: {current_im}, target: {target_im_total})")
                
                # Add to position
                bybit_side = "Buy" if self.direction == "LONG" else "Sell"
                
                order_body = {
                    "category": "linear",
                    "symbol": self.symbol,
                    "side": bybit_side,
                    "orderType": "Market",
                    "qty": str(additional_size),
                    "timeInForce": "IOC",
                    "reduceOnly": False,
                    "positionIdx": 0,
                    "orderLinkId": f"pyramid_im_{self.trade_id}_{len(self.activated_levels)}"
                }
                
                result = await self.bybit.place_order(order_body)
                if result.get('retCode') == 0:
                    system_logger.info(f"Position IM increased to {target_im_total} USDT for {self.symbol} (+{additional_size} contracts)")
                    return True
                else:
                    system_logger.error(f"Failed to increase position IM: {result}")
                    return False
            return False
        except Exception as e:
            system_logger.error(f"Update position size to total IM error: {e}", exc_info=True)
            return False
    
    async def _update_position_size(self, new_im: Decimal) -> bool:
        """
        Update position size to new IM target (legacy method).
        Use _update_position_size_to_total_im() for new code.
        """
        return await self._update_position_size_to_total_im(new_im)
    
    async def _add_im_to_position(self, im_to_add: Decimal):
        """Add specific IM amount to position."""
        try:
            # Get current position
            pos = await self.bybit.get_position("linear", self.symbol)
            
            # CRITICAL FIX: Check API return code first
            if pos.get('retCode') != 0:
                system_logger.error(f"Failed to get position for IM addition: {pos.get('retMsg')}")
                return  # Exit early on error
            
            if pos.get("result", {}).get("list"):
                position = pos["result"]["list"][0]
                current_size = Decimal(str(position.get("size", "0")))
                avg_price = Decimal(str(position.get("avgPrice", "0")))
                leverage = Decimal(str(position.get("leverage", "1")))
                
                # Calculate additional size needed for the IM
                additional_size = (im_to_add * leverage) / avg_price
                
                if additional_size > 0:
                    # Convert direction to Bybit format for adding margin
                    # For LONG positions: adding margin requires Buy orders
                    # For SHORT positions: adding margin requires Sell orders
                    bybit_side = "Buy" if self.direction == "LONG" else "Sell"
                    
                    # Add to position
                    order_body = {
                        "category": "linear",
                        "symbol": self.symbol,
                        "side": bybit_side,  # Correct side for adding margin
                        "orderType": "Market",
                        "qty": str(additional_size),
                        "timeInForce": "IOC",
                        "reduceOnly": False,
                        "positionIdx": 0,
                        "orderLinkId": f"add_im_{self.trade_id}_{len(self.activated_levels)}"
                    }
                    
                    result = await self.bybit.place_order(order_body)
                    if result.get('retCode') == 0:
                        system_logger.info(f"Added {additional_size} contracts (${im_to_add} IM) to {self.symbol}")
                    else:
                        system_logger.error(f"Failed to add IM: {result}")
                        
        except Exception as e:
            system_logger.error(f"Add IM error: {e}", exc_info=True)
