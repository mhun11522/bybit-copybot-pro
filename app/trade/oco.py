"""OCO (One-Cancels-Other) Manager with TP2 Break-even rule."""

import asyncio
from decimal import Decimal
from app.bybit.client import BybitClient
from app.core.precision import q_price, q_qty
from app.telegram.output import send_message
from app.config.settings import CATEGORY

class OCOManager:
    """Manages OCO logic and TP2 break-even rule."""
    
    def __init__(self, trade_id, symbol, direction, channel_name):
        self.trade_id = trade_id
        self.symbol = symbol
        self.direction = direction
        self.channel_name = channel_name
        self.bybit = BybitClient()
        self._running = False
        self.tp2_filled = False

    async def run(self):
        """Run OCO monitoring with TP2 break-even rule."""
        self._running = True
        print(f"🔄 OCO Manager started for {self.symbol}")
        
        while self._running:
            try:
                # Check open orders
                orders = await self.bybit.query_open(CATEGORY, self.symbol)
                open_orders = orders.get("result", {}).get("list", [])
                
                # Check if TP2 was filled
                if not self.tp2_filled:
                    tp2_filled = any(
                        order.get("orderLinkId", "").endswith("-TP2") and 
                        order.get("orderStatus") == "Filled"
                        for order in open_orders
                    )
                    
                    if tp2_filled:
                        await self._move_sl_to_break_even()
                        self.tp2_filled = True
                
                # Check if all TPs filled or SL hit
                tp_orders = [o for o in open_orders if o.get("orderLinkId", "").endswith(("-TP1", "-TP2", "-TP3"))]
                sl_orders = [o for o in open_orders if o.get("orderLinkId", "").endswith("-SL")]
                
                if not tp_orders and sl_orders:
                    # All TPs filled, cancel remaining orders
                    await self.bybit.cancel_all(CATEGORY, self.symbol)
                    await send_message(f"🎯 All TPs filled for {self.symbol} • Source: {self.channel_name}")
                    self._running = False
                    break
                
                if tp_orders and not sl_orders:
                    # SL hit, cancel remaining orders
                    await self.bybit.cancel_all(CATEGORY, self.symbol)
                    await send_message(f"🛑 Stop loss hit for {self.symbol} • Source: {self.channel_name}")
                    self._running = False
                    break
                    
            except Exception as e:
                print(f"❌ OCO error for {self.symbol}: {e}")
            
            await asyncio.sleep(2)

    async def _move_sl_to_break_even(self):
        """Move SL to break-even + 0.0015% after TP2 fill."""
        try:
            # Get current position
            positions = await self.bybit.positions(CATEGORY, self.symbol)
            if not positions.get("result", {}).get("list"):
                return
            
            position = positions["result"]["list"][0]
            avg_entry = Decimal(str(position.get("avgPrice", "0")))
            size = Decimal(str(position.get("size", "0")))
            
            if size <= 0:
                return
            
            # Calculate break-even + 0.0015%
            if self.direction == "BUY":
                new_sl = avg_entry * Decimal("1.000015")  # +0.0015%
            else:
                new_sl = avg_entry * Decimal("0.999985")  # -0.0015%
            
            # Quantize the new SL price
            new_sl_q = await q_price(CATEGORY, self.symbol, new_sl)
            size_q = await q_qty(CATEGORY, self.symbol, size)
            
            # Cancel old SL and place new one
            await self.bybit.cancel_all(CATEGORY, self.symbol)
            
            # Place new SL at break-even + 0.0015%
            exit_side = "Sell" if self.direction == "BUY" else "Buy"
            await self.bybit.sl_market_reduceonly_mark(
                CATEGORY, self.symbol, exit_side, str(size_q), str(new_sl_q), 
                f"{self.trade_id}-SL-BE"
            )
            
            await send_message(
                f"⛳ TP2 filled! Moved SL to break-even +0.0015% ({new_sl_q}) for {self.symbol} • Source: {self.channel_name}"
            )
            
        except Exception as e:
            print(f"❌ Failed to move SL to break-even for {self.symbol}: {e}")