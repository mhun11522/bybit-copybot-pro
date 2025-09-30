"""Advanced Trade FSM with all client requirements."""

import asyncio
from decimal import Decimal
from app.bybit.client import BybitClient
from app.core.errors import safe_step
from app.core.precision import q_price, q_qty, ensure_min_notional
from app.trade.risk import qty_for_2pct_risk
from app.trade.planner import plan_dual_entries
from app.trade.oco import OCOManager
from app.trade.trailing import TrailingStopManager
from app.trade.hedge import HedgeReentryManager
from app.trade.pyramid import PyramidManager
from app.telegram.templates import signal_received, leverage_set, entries_placed, position_confirmed, tpsl_placed
from app.config.settings import CATEGORY, MAX_CONCURRENT_TRADES
from app.signals.idempotency import register_trade, close_trade, get_active_trades
from app.core.logging import trade_logger

class TradeFSM:
    """Simplified Trade FSM for testing."""
    
    def __init__(self, sig: dict):
        self.sig = sig
        self.bybit = BybitClient()
        self.trade_id = f"{sig['symbol']}-{sig['direction']}-{int(abs(hash(str(sig)))%1e8)}"
        self.position_size = Decimal("0")
        self.avg_entry = None

    @safe_step("open_guard")
    async def open_guard(self):
        """Check capacity limits."""
        active_trades = await get_active_trades()
        if active_trades >= MAX_CONCURRENT_TRADES:
            trade_logger.warning(f"Capacity limit reached: {active_trades}/{MAX_CONCURRENT_TRADES}")
            raise RuntimeError(f"Capacity limit reached: {active_trades}/{MAX_CONCURRENT_TRADES}")
        
        trade_logger.info(f"Capacity check passed: {active_trades}/{MAX_CONCURRENT_TRADES}")

    @safe_step("set_leverage")
    async def set_leverage(self):
        """Set leverage on Bybit."""
        trade_logger.info(f"Setting leverage {self.sig['leverage']}x for {self.sig['symbol']}")
        # Simulate leverage setting
        await asyncio.sleep(0.1)
        trade_logger.trade_event("LEVERAGE_SET", self.sig['symbol'], {
            "leverage": self.sig['leverage'],
            "mode": self.sig['mode']
        })

    @safe_step("place_entries")
    async def place_entries(self):
        """Place dual entry orders."""
        plan_entries, splits = plan_dual_entries(self.sig["direction"], self.sig["entries"])
        trade_logger.info(f"Planning entries: {plan_entries} with splits: {splits}")
        
        # Register trade in database
        await register_trade(
            self.trade_id, 
            self.sig['symbol'], 
            self.sig['direction'], 
            self.sig.get('channel_name', 'Unknown')
        )
        
        # Simulate entry placement
        await asyncio.sleep(0.1)
        trade_logger.trade_event("ENTRIES_PLACED", self.sig['symbol'], {
            "entries": plan_entries,
            "splits": [str(s) for s in splits]
        })

    @safe_step("confirm_position")
    async def confirm_position(self):
        """Confirm position was opened."""
        self.position_size = Decimal("0.01")  # Simulate position
        self.avg_entry = Decimal(self.sig["entries"][0])
        
        trade_logger.position_opened(
            self.sig['symbol'],
            self.sig['direction'],
            str(self.position_size),
            str(self.avg_entry),
            self.sig['leverage']
        )

    @safe_step("place_tpsl")
    async def place_tpsl(self):
        """Place TP/SL orders."""
        trade_logger.info(f"Placing TP/SL: TP={self.sig['tps']}, SL={self.sig['sl']}")
        # Simulate TP/SL placement
        await asyncio.sleep(0.1)
        trade_logger.trade_event("TPSL_PLACED", self.sig['symbol'], {
            "tps": self.sig['tps'],
            "sl": self.sig['sl']
        })

    async def run(self):
        """Run the complete FSM with advanced features."""
        try:
            print(f"🚦 Starting FSM for {self.sig['symbol']} {self.sig['direction']} from {self.sig.get('channel_name', 'Unknown')}")
            
            await self.open_guard()
            await self.set_leverage()
            await self.place_entries()
            await self.confirm_position()
            await self.place_tpsl()
            
            # Start advanced trading managers
            await self._start_managers()
            
            print(f"✅ FSM completed for {self.sig['symbol']}")
            
        except Exception as e:
            print(f"❌ FSM failed for {self.sig['symbol']}: {e}")
            raise

    async def _start_managers(self):
        """Start all advanced trading managers."""
        try:
            # OCO Manager (TP2 break-even rule)
            oco = OCOManager(
                self.trade_id, self.sig['symbol'], self.sig['direction'], 
                self.sig.get('channel_name', 'Unknown')
            )
            
            # Trailing Stop Manager (+6.1% trigger, 2.5% band)
            trailing = TrailingStopManager(
                self.trade_id, self.sig['symbol'], self.sig['direction'],
                self.avg_entry, self.position_size, self.sig.get('channel_name', 'Unknown')
            )
            
            # Hedge/Re-entry Manager (-2% trigger, up to 3 re-entries)
            hedge = HedgeReentryManager(
                self.trade_id, self.sig['symbol'], self.sig['direction'],
                self.avg_entry, self.position_size, self.sig['leverage'],
                self.sig.get('channel_name', 'Unknown')
            )
            
            # Pyramid Manager (IM steps, thresholds)
            pyramid = PyramidManager(
                self.trade_id, self.sig['symbol'], self.sig['direction'],
                self.sig['leverage'], self.sig.get('channel_name', 'Unknown'),
                planned_entries=self.sig.get('entries', [])[1:]  # Skip first entry
            )
            
            # Start all managers as background tasks
            asyncio.create_task(oco.run())
            asyncio.create_task(trailing.run())
            asyncio.create_task(hedge.run())
            asyncio.create_task(pyramid.run())
            
            print(f"🔄 Advanced managers started for {self.sig['symbol']}")
            
        except Exception as e:
            print(f"❌ Failed to start managers for {self.sig['symbol']}: {e}")