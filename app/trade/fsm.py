from decimal import Decimal
import asyncio
from app.config.settings import CATEGORY, MAX_CONCURRENT_TRADES
from app.bybit.client import BybitClient
# from app.bybit.websocket import get_websocket  # Temporarily disabled due to missing websockets module
from app.core.precision import q_price, q_qty, ensure_min_notional
from app.core.errors import safe_step, breaker_reset
from app.trade.planner import plan_dual_entries
from app.trade.risk import qty_for_2pct_risk
from app.telegram import templates_v2
from app.telegram.output import send_message
from app.storage.db import init_db, get_trade, close_trade

from app.trade.oco import OCOManager
from app.trade.trailing import TrailingStopManager
from app.trade.hedge import HedgeReentryManager
from app.trade.pyramid import PyramidManager
from app.trade.tp2_be import TP2BreakEvenManager

async def _active_trades() -> int:
    """Count active trades using the unified database."""
    from app.storage.db import aiosqlite, DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM trades WHERE state!='DONE'")
        result = await cur.fetchone()
        return result[0] or 0

async def _upsert_trade(trade_id, **fields):
    """Upsert trade using the unified database."""
    from app.storage.db import aiosqlite, DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO trades(trade_id,symbol,direction,avg_entry,position_size,leverage,channel_name,state)
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(trade_id) DO UPDATE SET
                symbol=excluded.symbol,
                direction=excluded.direction,
                avg_entry=excluded.avg_entry,
                position_size=excluded.position_size,
                leverage=excluded.leverage,
                channel_name=excluded.channel_name,
                state=excluded.state
        """, (trade_id, fields.get("symbol"), fields.get("direction"), fields.get("avg_entry"),
              fields.get("position_size"), fields.get("leverage"), fields.get("channel_name"), fields.get("state")))
        await db.commit()

class TradeFSM:
    def __init__(self, sig: dict):
        self.sig = sig
        self.bybit = BybitClient()
        self.trade_id = f"{sig['symbol']}-{sig['direction']}-{int(abs(hash(str(sig)))%1e8)}"
        self.position_size = Decimal("0")
        self.avg_entry = None
        self.original_entry = Decimal(str(sig["entries"][0]))  # CRITICAL: Store original entry for pyramid calculations
        self._tasks = []  # Track background tasks to avoid recursive cancellation
        self.position_filled = asyncio.Event()  # WebSocket event for fill detection
        self.ws_position_data = None  # Store position data from WebSocket

    async def validate_symbol(self):
        """Validate that the symbol exists on Bybit before proceeding"""
        from app.bybit.client import BybitAPIError
        try:
            # Test if symbol exists by getting instrument info
            result = await self.bybit.instruments(CATEGORY, self.sig["symbol"])
            if result.get("retCode") != 0:
                print(f"❌ Symbol {self.sig['symbol']} not found on Bybit: {result.get('retMsg')}")
                await send_message(templates_v2.error_symbol_invalid(
                    self.sig['symbol'], 
                    self.sig.get('channel_name', '?'),
                    result.get('retMsg', '')
                ))
                raise ValueError(f"Symbol {self.sig['symbol']} not found")
            print(f"✅ Symbol {self.sig['symbol']} validated")
        except BybitAPIError as e:
            # Handle Bybit API errors specifically (symbol invalid, etc.)
            print(f"❌ Symbol {self.sig['symbol']} not found on Bybit: {e}")
            await send_message(templates_v2.error_symbol_invalid(
                self.sig['symbol'], 
                self.sig.get('channel_name', '?'),
                str(e)
            ))
            raise ValueError(f"Symbol {self.sig['symbol']} not found")
        except ValueError:
            # Re-raise ValueError to stop the trade (already sent error message)
            raise
        except Exception as e:
            # For other connection errors
            print(f"⚠️  Symbol validation failed for {self.sig['symbol']}: {e}")
            await send_message(templates_v2.error_api_failed(
                self.sig['symbol'],
                self.sig.get('channel_name', '?'),
                str(e)
            ))
            raise ValueError(f"Symbol validation failed for {self.sig['symbol']}")

    @safe_step("open_guard")
    async def open_guard(self):
        if await _active_trades() >= MAX_CONCURRENT_TRADES:
            await send_message(f"⛔ Kapacitetsgräns {MAX_CONCURRENT_TRADES} uppnådd / Capacity reached")
            raise RuntimeError("capacity")
        await _upsert_trade(self.trade_id,
                            symbol=self.sig["symbol"],
                            direction=self.sig["direction"],
                            avg_entry=0,
                            position_size=0,
                            leverage=self.sig["leverage"],
                            channel_name=self.sig["channel_name"],
                            state="OPENING")

    @safe_step("set_leverage")
    async def set_leverage(self):
        # Get maximum leverage allowed for this symbol
        max_lev = await self.bybit.get_max_leverage(CATEGORY, self.sig["symbol"])
        
        # Log leverage calculation details
        original_lev = float(self.sig["leverage"])
        print(f"🔧 Leverage calculation for {self.sig['symbol']}:")
        print(f"   Original calculated: {original_lev:.2f}x")
        print(f"   Symbol max allowed: {max_lev}x")
        
        # Adjust requested leverage to symbol's max
        lev = min(original_lev, max_lev)
        mode = self.sig["mode"]
        
        # Update signal with actual leverage that will be used
        self.sig["leverage"] = lev
        
        print(f"   Final leverage: {lev:.2f}x (mode: {mode})")
        
        # Validate leverage policy with adjusted leverage
        if mode == "SWING" and lev < 6:
            # If max leverage is less than 6, use whatever is available
            if max_lev < 6:
                lev = max_lev
                print(f"⚠️  Symbol {self.sig['symbol']} max leverage is {max_lev}x, using that instead of 6x")
        elif mode == "DYNAMIC" and lev < 7.5:
            # If max leverage is less than 7.5, downgrade to SWING mode
            if max_lev < 7.5:
                lev = min(6.0, max_lev)
                self.sig["mode"] = "SWING"
                mode = "SWING"
                print(f"⚠️  Symbol {self.sig['symbol']} max leverage is {max_lev}x, switching to SWING mode")
        elif mode == "FAST" and lev < 10:
            # If max leverage is less than 10, use whatever is available
            if max_lev < 10:
                lev = max_lev
                print(f"⚠️  Symbol {self.sig['symbol']} max leverage is {max_lev}x, using that instead of 10x+")
        
        try:
            r = await self.bybit.set_leverage(CATEGORY, self.sig["symbol"], lev, lev)
            breaker_reset()
            # Don't send message here - comprehensive message already sent
            return r
        except Exception as e:
            print(f"❌ Failed to set leverage for {self.sig['symbol']}: {e}")
            await send_message(templates_v2.error_order_rejected(
                self.sig['symbol'],
                self.sig.get('channel_name', '?'),
                f"Leverage setting failed: {e}"
            ))
            # CRITICAL: Do not continue trading if leverage fails - risk management would be broken
            raise ValueError(f"Cannot set leverage for {self.sig['symbol']}: {e}")

    @safe_step("place_entries")
    async def place_entries(self):
        try:
            # Safety check: if no entries, skip order placement
            if not self.sig.get("entries") or len(self.sig["entries"]) == 0:
                print(f"⚠️  No entry prices found in signal for {self.sig['symbol']}, skipping order placement")
                await send_message(templates_v2.error_signal_invalid(
                    self.sig['symbol'],
                    self.sig.get('channel_name', '?')
                ))
                return
            
            # PRE-FLIGHT CHECKS: Verify margin and balance before placing orders
            from app.config.settings import IM_PER_ENTRY_USDT
            
            # Check wallet balance
            try:
                balance_result = await self.bybit.wallet_balance("USDT")
                equity = Decimal(balance_result["result"]["list"][0].get("totalEquity", "0"))
                available = Decimal(balance_result["result"]["list"][0].get("totalAvailableBalance", "0"))
                required_margin = Decimal(str(IM_PER_ENTRY_USDT))
                
                if available < required_margin:
                    print(f"❌ Insufficient margin: {available} USDT available, {required_margin} USDT required")
                    await send_message(templates_v2.error_insufficient_balance(
                        self.sig['symbol'],
                        self.sig.get('channel_name', '?')
                    ))
                    return
                    
                print(f"✅ Margin check passed: {available:.2f} USDT available, {required_margin:.2f} USDT required")
            except Exception as e:
                print(f"⚠️  Could not check wallet balance: {e}")
                # Continue anyway - balance check is informational
            
            side = "Buy" if self.sig["direction"] == "BUY" else "Sell"
            plan_entries, splits = plan_dual_entries(self.sig["direction"], self.sig["entries"])
            
            # Use IM-based sizing (20 USDT per entry) as per client requirements
            from app.trade.risk import split_dual_qty
            lev = Decimal(str(self.sig["leverage"]))
            e1_q = await q_price(CATEGORY, self.sig["symbol"], plan_entries[0])
            e2_q = await q_price(CATEGORY, self.sig["symbol"], plan_entries[1])
            q1, q2 = await split_dual_qty(CATEGORY, self.sig["symbol"], e1_q, e2_q, lev)

            # Store quantities for later use
            self.planned_total_qty = q1 + q2
            self.plan_entries = plan_entries
            self.entry_qty = (q1, q2)
            
            # Place two entry orders
            result1 = await self.bybit.entry_limit_postonly(
                CATEGORY, self.sig["symbol"], side,
                str(q1), str(e1_q), f"{self.trade_id}-E1"
            )
            order_id_1 = result1.get('result', {}).get('orderId', 'N/A')
            print(f"✅ Entry order placed: E1 - {q1} @ {e1_q}, orderId: {order_id_1}")
            
            result2 = await self.bybit.entry_limit_postonly(
                CATEGORY, self.sig["symbol"], side,
                str(q2), str(e2_q), f"{self.trade_id}-E2"
            )
            order_id_2 = result2.get('result', {}).get('orderId', 'N/A')
            print(f"✅ Entry order placed: E2 - {q2} @ {e2_q}, orderId: {order_id_2}")
            
            breaker_reset()
            
            # Send order placed confirmation to Telegram
            try:
                # Calculate actual IM from the placed orders
                # IM_PER_ENTRY_USDT is the TOTAL IM for the trade, split across 2 entries
                from app.config.settings import IM_PER_ENTRY_USDT
                im_actual = float(IM_PER_ENTRY_USDT)  # Total IM for the trade (20 USDT default)
                
                await send_message(templates_v2.order_placed(
                    symbol=self.sig["symbol"],
                    channel_name=self.sig.get("channel_name", "?"),
                    direction=self.sig["direction"],
                    mode=self.sig.get("mode", "FAST"),
                    entry=str(plan_entries[0]),  # First entry price
                    tps=self.sig.get("tps", []),
                    sl=str(self.sig.get("sl", "?")),
                    leverage=self.sig.get("leverage", 10.0),
                    im_actual=im_actual,
                    order_id=f"{order_id_1}, {order_id_2}"  # Both order IDs
                ))
                print(f"📤 Order placed message sent to Telegram")
            except Exception as e:
                print(f"⚠️  Could not send order placed message: {e}")
        except Exception as e:
            print(f"⚠️  Failed to place entries for {self.sig['symbol']}: {e}")
            # Don't raise the exception to prevent circuit breaker activation
            # Just log the error and continue
            await send_message(templates_v2.error_order_failed(
                self.sig['symbol'],
                self.sig.get('channel_name', '?')
            ))

    async def _on_position_update(self, position_data: dict):
        """WebSocket handler for position updates"""
        try:
            symbol = position_data.get("symbol")
            if symbol != self.sig["symbol"]:
                return
            
            size = Decimal(str(position_data.get("size") or "0"))
            if size > 0:
                print(f"🔔 WebSocket: Position update for {symbol}, size={size}")
                self.ws_position_data = position_data
                self.position_filled.set()  # Signal that position is filled
        except Exception as e:
            print(f"⚠️  Error processing position update: {e}")
    
    @safe_step("confirm_position")
    async def confirm_position(self):
        """
        Wait for PostOnly entry orders to fill (NEVER use Market orders).
        Flow: PostOnly → WebSocket/polling wait → Fill → TP/SL
        Strategy: Only execute at correct entry price, wait up to 36 hours.
        """
        # STRATEGY: Only PostOnly orders - wait for correct entry or timeout
        # No market fallback - orders fill when price reaches the level
        max_wait_time = 36 * 3600  # Wait up to 36 hours for PostOnly orders to fill
        
        # WebSocket temporarily disabled - using polling only
        use_websocket = False
        print(f"📡 Using REST polling for {self.sig['symbol']} position updates")
        
        start_time = asyncio.get_event_loop().time()
        
        # Main wait loop
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            
            # WebSocket disabled - using polling only
            
            # Polling: Check position via REST API every 2 seconds
            should_poll = True
            
            if should_poll:
                try:
                    pos = await self.bybit.positions(CATEGORY, self.sig["symbol"])
                    lst = pos.get("result", {}).get("list", [])
                    
                    # Log every check (polling mode)
                    print(f"🔍 Checking position {self.sig['symbol']} ({int(elapsed)}s elapsed): {len(lst)} positions found")
                    
                    if lst:
                        row = lst[0]
                        size = Decimal(str(row.get("size") or "0"))
                        
                        if size > 0:
                            # ✅ Position confirmed via polling
                            print(f"✅ Position confirmed via polling: {size} @ {row.get('avgPrice')}")
                            self.position_size = size
                            self.avg_entry = Decimal(str(row.get("avgPrice") or self.sig["entries"][0]))
                            
                            await self._finalize_position_confirmation()
                            
                            # WebSocket disabled
                            
                            return
                
                except Exception as e:
                    if int(elapsed) % 10 == 0:
                        print(f"   Error checking position: {e}")
            
            # STRATEGY REQUIREMENT: NEVER use Market orders, only PostOnly
            # PostOnly orders will fill when price reaches the level
            # No market fallback - wait for correct entry conditions
            # Max wait time is 36 hours total
            
            # Check if we've exceeded max wait time
            if elapsed >= max_wait_time:
                hours = int(elapsed / 3600)
                print(f"❌ PostOnly orders did not fill after {hours}h for {self.sig['symbol']}")
                print(f"   Cancelling unfilled orders and stopping trade")
                
                # Cancel all open orders for this symbol
                try:
                    await self.bybit.cancel_all(CATEGORY, self.sig["symbol"])
                    print(f"   ✅ Cancelled all orders for {self.sig['symbol']}")
                except Exception as e:
                    print(f"   ⚠️  Failed to cancel orders: {e}")
                
                await send_message(templates_v2.error_position_not_opened(
                    self.sig['symbol'],
                    self.sig.get('channel_name', '?')
                ))
                
                raise Exception(f"Position not confirmed for {self.sig['symbol']} after {int(elapsed)}s")
            
            # Wait 2 seconds before next check
            await asyncio.sleep(2)
    
    async def _finalize_position_confirmation(self):
        """Helper to finalize position confirmation and send notifications"""
        await _upsert_trade(self.trade_id,
                            symbol=self.sig["symbol"],
                            direction=self.sig["direction"],
                            avg_entry=float(self.avg_entry),
                            position_size=float(self.position_size),
                            leverage=self.sig["leverage"],
                            channel_name=self.sig["channel_name"],
                            state="OPEN")
        breaker_reset()
        
        print(f"✅ Position confirmed: {self.position_size} @ {self.avg_entry}")
        
        # Send merged position message (both entries filled)
        from app.config.settings import IM_PER_ENTRY_USDT
        im_total = float(IM_PER_ENTRY_USDT) * 2  # Total IM for both entries
        await send_message(templates_v2.position_merged(
            channel=self.sig.get("channel_name", "?"),
            symbol=self.sig["symbol"],
            side=self.sig["direction"],
            qty=float(self.position_size),
            avg_entry=float(self.avg_entry),
            im_total=im_total,
            lev=self.sig.get("leverage", 10.0),
            mode=self.sig.get("mode", "FAST")
        ))
        
        # Place TP/SL orders immediately after position confirmation
        await self.place_tpsl()
        
        # Send position opened notification
        await send_message(templates_v2.position_opened(
            self.sig["symbol"],
            self.sig.get("channel_name", "?"),
            self.sig["direction"],
            self.sig.get("mode", "FAST"),
            str(self.avg_entry),
            str(self.position_size),
            self.sig.get("tps", []),
            str(self.sig.get("sl", "?")),
            self.sig.get("leverage", 10.0)
        ))
        
        # Start advanced trading controllers
        await self._start_controllers()

    @safe_step("place_tpsl")
    async def place_tpsl(self):
        print(f"🎯 Placing TP/SL orders for {self.sig['symbol']}...")
        exit_side = "Sell" if self.sig["direction"] == "BUY" else "Buy"
        splits = [Decimal("0.5"), Decimal("0.3"), Decimal("0.2")][:len(self.sig["tps"])]

        # Place Take Profit orders
        tp_orders = []
        for i, (tp_raw, frac) in enumerate(zip(self.sig["tps"], splits), start=1):
            p = await q_price(CATEGORY, self.sig["symbol"], tp_raw)
            q = await q_qty(CATEGORY, self.sig["symbol"], self.position_size * frac)
            q = await ensure_min_notional(CATEGORY, self.sig["symbol"], p, q)
            link_id = f"{self.trade_id}-TP{i}"
            await self.bybit.tp_limit_reduceonly(CATEGORY, self.sig["symbol"], exit_side, str(q), str(p), link_id)
            tp_orders.append(link_id)
            print(f"   ✅ TP{i} placed: {q} @ {p}")

        # Place Stop Loss order
        sl = await q_price(CATEGORY, self.sig["symbol"], self.sig["sl"])
        full_q = await q_qty(CATEGORY, self.sig["symbol"], self.position_size)
        sl_link_id = f"{self.trade_id}-SL"
        await self.bybit.sl_market_reduceonly_mark(CATEGORY, self.sig["symbol"], exit_side, str(full_q), str(sl), sl_link_id)
        print(f"   ✅ SL placed: {full_q} @ {sl}")
        
        # Store order IDs for OCO management
        self.tp_orders = tp_orders
        self.sl_order = sl_link_id
        
        print(f"🎯 All TP/SL orders placed successfully for {self.sig['symbol']}")
        print(f"   📋 TP orders: {tp_orders}")
        print(f"   📋 SL order: {sl_link_id}")
        print(f"   🔗 OCO logic: When any TP fills, SL will be cancelled (and vice versa)")
        
        breaker_reset()
        # Don't send message here - TP/SL info already included in position_opened message

    async def run(self):
        # Validate symbol exists on Bybit before trading
        await self.validate_symbol()
        await self.open_guard()
        await self.set_leverage()
        await self.place_entries()
        await self.confirm_position()
        # TP/SL placement is now handled in _finalize_position_confirmation()

    async def _start_controllers(self):
        """
        Start advanced trading controllers after position is confirmed.
        Controllers: OCO, Trailing, Hedge, Pyramid, TP2-BE
        """
        print(f"🎮 Starting trading controllers for {self.sig['symbol']}...")
        
        try:
            # Initialize controllers with confirmed position data
            oco = OCOManager(self.trade_id, self.sig["symbol"], self.sig["direction"], 
                            self.sig["channel_name"], self.sig.get("channel_id"))
            trail = TrailingStopManager(self.trade_id, self.sig["symbol"], self.sig["direction"], 
                                       self.original_entry, self.avg_entry, self.position_size, self.sig["channel_name"])
            hedge = HedgeReentryManager(self.trade_id, self.sig["symbol"], self.sig["direction"], 
                                       self.avg_entry, self.position_size, self.sig["leverage"], 
                                       self.sig["channel_name"])
            pyr = PyramidManager(self.trade_id, self.sig["symbol"], self.sig["direction"], 
                                self.original_entry, self.avg_entry, self.position_size, self.sig["leverage"], 
                                self.sig["channel_name"])
            tp2be = TP2BreakEvenManager(self.trade_id, self.sig["symbol"], self.sig["direction"], 
                                        self.avg_entry, self.sig["channel_name"])
            
            # Start all controllers as background tasks
            for mgr in (oco, trail, hedge, pyr, tp2be):
                t = asyncio.create_task(mgr.run())
                self._tasks.append(t)
            
            print(f"✅ Controllers started: OCO, Trailing (+6.1%), Hedge (-2%), Pyramid (7 levels), TP2-BE")
            
        except Exception as e:
            print(f"⚠️  Failed to start controllers: {e}")
            # Don't crash the trade if controllers fail to start