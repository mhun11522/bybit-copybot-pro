from __future__ import annotations
import asyncio
from decimal import Decimal, ROUND_UP
from typing import Dict, List
from app.bybit_client import BybitClient
from app.core.precision import q_price, q_qty, ensure_min_notional
from app.storage.db import aiosqlite, DB_PATH
from app.telegram.output import send_message
from app.telegram import templates
from app import settings


class PyramidManager:
    def __init__(self, bybit_client: BybitClient, trade_id: str, symbol: str, direction: str, leverage: int):
        self.bybit = bybit_client
        self.trade_id = trade_id
        self.symbol = symbol
        self.direction = direction
        self.leverage = leverage
        self.adds_count = 0
        self.current_im_total = settings.INITIAL_MARGIN_USDT
        self.original_entry = None
        self.position_size = Decimal("0")
        self.avg_entry = None
        self.highest_price = None
        self.breakeven_moved = False
        self.leverage_raised = False

    async def monitor(self, entry_price: Decimal, position_size: Decimal):
        """Monitor for pyramid opportunities based on step ladder."""
        self.original_entry = entry_price
        self.position_size = position_size
        self.highest_price = entry_price
        
        # Calculate average entry from position
        try:
            positions = await asyncio.to_thread(self.bybit.get_positions, self.symbol)
            if positions.get("retCode") == 0:
                pos_list = positions.get("result", {}).get("list", [])
                for pos in pos_list:
                    if pos.get("size") and float(pos["size"]) > 0:
                        self.avg_entry = Decimal(str(pos.get("avgPrice", entry_price)))
                        break
        except Exception:
            self.avg_entry = entry_price

        print(f"📈 Starting pyramid monitor for {self.symbol}, entry: {entry_price}")

        while self.adds_count < settings.MAX_PYRAMID_ADDS:
            try:
                # Get current price
                ticker = await asyncio.to_thread(self.bybit.get_ticker, self.symbol)
                if not ticker or ticker.get("retCode") != 0:
                    await asyncio.sleep(5)
                    continue
                
                last_price = Decimal(str(ticker["result"]["list"][0]["lastPrice"]))
                
                # Update highest price for trailing
                if self.direction == "BUY":
                    if self.highest_price is None or last_price > self.highest_price:
                        self.highest_price = last_price
                else:
                    if self.highest_price is None or last_price < self.highest_price:
                        self.highest_price = last_price
                
                # Calculate profit percentage from original entry
                if self.direction == "BUY":
                    profit_pct = (last_price - self.original_entry) / self.original_entry
                else:
                    profit_pct = (self.original_entry - last_price) / self.original_entry
                
                # Check for step ladder triggers
                await self._check_step_triggers(profit_pct, last_price)
                
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"Pyramid monitor error: {e}")
                await asyncio.sleep(5)

    async def _check_step_triggers(self, profit_pct: Decimal, current_price: Decimal):
        """Check and execute step ladder triggers."""
        
        # Step 1: +1.5% - Check IM is 20 USDT if any TP hit
        if profit_pct >= Decimal("0.015") and self.adds_count == 0:
            await self._step_1_5_percent(current_price)
        
        # Step 2: +2.3% - Move SL to breakeven
        if profit_pct >= Decimal("0.023") and not self.breakeven_moved:
            await self._step_2_3_percent(current_price)
        
        # Step 3: +2.4% - Raise leverage to max
        if profit_pct >= Decimal("0.024") and not self.leverage_raised:
            await self._step_2_4_percent(current_price)
        
        # Step 4: +2.5% - IM to 40 USDT
        if profit_pct >= Decimal("0.025") and self.current_im_total < 40:
            await self._step_2_5_percent(current_price)
        
        # Step 5: +4.0% - IM to 60 USDT
        if profit_pct >= Decimal("0.040") and self.current_im_total < 60:
            await self._step_4_0_percent(current_price)
        
        # Step 6: +6.0% - IM to 80 USDT
        if profit_pct >= Decimal("0.060") and self.current_im_total < 80:
            await self._step_6_0_percent(current_price)
        
        # Step 7: +8.6% - IM to 100 USDT
        if profit_pct >= Decimal("0.086") and self.current_im_total < 100:
            await self._step_8_6_percent(current_price)

    async def _step_1_5_percent(self, current_price: Decimal):
        """+1.5%: Check IM is 20 USDT if any TP hit."""
        print(f"📈 Pyramid step 1.5% triggered for {self.symbol}")
        
        # Check if any TP was hit by looking at recent fills
        try:
            # This would need to be implemented based on your fill tracking
            # For now, just add the pyramid order
            await self._add_pyramid_order(current_price, 20)
        except Exception as e:
            print(f"Step 1.5% error: {e}")

    async def _step_2_3_percent(self, current_price: Decimal):
        """+2.3%: Move SL to breakeven."""
        print(f"📈 Pyramid step 2.3% - Moving SL to breakeven for {self.symbol}")
        
        # Move SL to breakeven + small offset
        breakeven_price = self.avg_entry * (Decimal("1.0015") if self.direction == "BUY" else Decimal("0.9985"))
        sl_price = await q_price(self.symbol, breakeven_price)
        
        try:
            await asyncio.to_thread(
                self.bybit.create_sl_order,
                symbol=self.symbol,
                side="Sell" if self.direction == "BUY" else "Buy",
                qty=str(self.position_size),
                trigger_price=str(sl_price),
                trade_id=f"{self.trade_id}-BE",
            )
            
            await send_message(templates.pyramid_breakeven(self.symbol, str(current_price), self.trade_id))
        except Exception as e:
            print(f"Breakeven SL error: {e}")

    async def _step_2_4_percent(self, current_price: Decimal):
        """+2.4%: Raise leverage to max."""
        print(f"📈 Pyramid step 2.4% - Raising leverage for {self.symbol}")
        
        try:
            new_leverage = min(settings.MAX_LEVERAGE_PYRAMID, self.leverage * 2)
            await asyncio.to_thread(
                self.bybit.set_leverage,
                self.symbol,
                new_leverage,
                new_leverage,
            )
            
            self.leverage = new_leverage
            await send_message(templates.pyramid_leverage_raised(self.symbol, new_leverage, self.trade_id))
        except Exception as e:
            print(f"Leverage raise error: {e}")

    async def _step_2_5_percent(self, current_price: Decimal):
        """+2.5%: IM to 40 USDT."""
        await self._add_pyramid_order(current_price, 40)

    async def _step_4_0_percent(self, current_price: Decimal):
        """+4.0%: IM to 60 USDT."""
        await self._add_pyramid_order(current_price, 60)

    async def _step_6_0_percent(self, current_price: Decimal):
        """+6.0%: IM to 80 USDT."""
        await self._add_pyramid_order(current_price, 80)

    async def _step_8_6_percent(self, current_price: Decimal):
        """+8.6%: IM to 100 USDT."""
        await self._add_pyramid_order(current_price, 100)

    async def _add_pyramid_order(self, current_price: Decimal, target_im_total: Decimal):
        """Add pyramid order to reach target IM total."""
        if self.adds_count >= settings.MAX_PYRAMID_ADDS:
            return
        
        # Calculate additional IM needed
        additional_im = target_im_total - self.current_im_total
        if additional_im <= 0:
            return
        
        # Calculate quantity for additional IM
        qty = await self._calculate_pyramid_qty(current_price, additional_im)
        if qty <= 0:
            return
        
        # Place pyramid order
        side = "Buy" if self.direction == "BUY" else "Sell"
        price = await q_price(self.symbol, current_price)
        
        try:
            resp = await asyncio.to_thread(
                self.bybit.create_entry_order,
                self.symbol,
                side,
                str(qty),
                str(price),
                f"{self.trade_id}-PYR{self.adds_count + 1}",
                self.adds_count + 1,
            )
            
            if resp.get("retCode") == 0:
                self.adds_count += 1
                self.current_im_total = target_im_total
                
                # Save pyramid state
                await self._save_pyramid_state()
                
                await send_message(templates.pyramid_added(
                    self.symbol, 
                    str(price), 
                    str(qty), 
                    str(additional_im),
                    str(self.current_im_total),
                    self.trade_id
                ))
                
        except Exception as e:
            print(f"Pyramid order error: {e}")

    async def _calculate_pyramid_qty(self, price: Decimal, im_amount: Decimal) -> Decimal:
        """Calculate quantity for pyramid add based on IM amount."""
        try:
            # IM = (qty * price) / leverage
            # qty = (IM * leverage) / price
            raw_qty = (im_amount * Decimal(self.leverage)) / price
            return await q_qty(self.symbol, raw_qty)
        except Exception:
            return Decimal("0")

    async def _save_pyramid_state(self):
        """Save current pyramid state to database."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO pyramid_state (trade_id, adds_count, im_total)
                    VALUES (?, ?, ?)
                """, (self.trade_id, self.adds_count, float(self.current_im_total)))
                await db.commit()
        except Exception as e:
            print(f"Pyramid state save error: {e}")

    async def get_pyramid_state(self) -> Dict:
        """Get current pyramid state from database."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("""
                    SELECT adds_count, im_total FROM pyramid_state WHERE trade_id = ?
                """, (self.trade_id,)) as cur:
                    row = await cur.fetchone()
                    if row:
                        return {"adds_count": row[0], "im_total": Decimal(str(row[1]))}
        except Exception:
            pass
        return {"adds_count": 0, "im_total": settings.INITIAL_MARGIN_USDT}