import asyncio
from decimal import Decimal
from app.bybit.client import BybitClient
from app.telegram import templates, output
from app.storage.db import close_trade

CATEGORY = "linear"

class OCOManager:
    def __init__(self, trade_id, symbol, direction, channel_name, channel_id=None):
        self.trade_id=trade_id; self.symbol=symbol; self.direction=direction; self.channel_name=channel_name
        self.channel_id=channel_id; self.bybit=BybitClient(); self._running=False

    async def _check_position_closed(self):
        """Check if position is closed by querying positions."""
        try:
            pos = await self.bybit.positions(CATEGORY, self.symbol)
            if pos.get("result", {}).get("list"):
                size = Decimal(str(pos["result"]["list"][0].get("size", "0")))
                return size <= 0
            return True
        except Exception:
            return False

    async def _check_tp_filled(self):
        """Check if any TP was filled by examining order history."""
        try:
            orders = await self.bybit.query_open(CATEGORY, self.symbol)
            open_ids = [o.get("orderLinkId","") for o in orders.get("result",{}).get("list",[]) if o.get("orderLinkId")]
            
            # Check for TP orders (any order ending with TP1, TP2, TP3, TP4)
            tp_open = any(x.endswith(("TP1","TP2","TP3","TP4")) for x in open_ids)
            # Check for SL order (any order ending with SL)
            sl_open = any(x.endswith("SL") for x in open_ids)
            
            # Return: (tp_filled, sl_filled)
            # tp_filled = True if TP orders are gone but SL is still there
            # sl_filled = True if SL order is gone but TP orders are still there
            tp_filled = not tp_open and sl_open
            sl_filled = not sl_open and tp_open
            
            if tp_filled:
                print(f"🔔 OCO: TP orders filled, SL still open - will cancel SL")
            elif sl_filled:
                print(f"🔔 OCO: SL order filled, TP orders still open - will cancel TPs")
            
            return tp_filled, sl_filled
        except Exception as e:
            print(f"OCO: Error checking TP/SL fills: {e}")
            return False, False

    async def _calculate_pnl(self, exit_price: Decimal) -> float:
        """Calculate realized PnL based on position and exit price."""
        try:
            pos = await self.bybit.positions(CATEGORY, self.symbol)
            if pos.get("result", {}).get("list"):
                position = pos["result"]["list"][0]
                size = Decimal(str(position.get("size", "0")))
                avg_price = Decimal(str(position.get("avgPrice", "0")))
                
                if size > 0:
                    # Calculate PnL based on direction
                    if self.direction == "BUY":
                        pnl = (exit_price - avg_price) * size
                    else:  # SELL
                        pnl = (avg_price - exit_price) * size
                    return float(pnl)
            return 0.0
        except Exception as e:
            print(f"Error calculating PnL: {e}")
            return 0.0

    async def _close_trade(self, exit_type: str, exit_price: str = "0"):
        """Close the trade in the database with PnL calculation."""
        try:
            exit_price_decimal = Decimal(exit_price) if exit_price != "0" else Decimal("0")
            pnl = await self._calculate_pnl(exit_price_decimal)
            await close_trade(self.trade_id, pnl)
            print(f"Trade {self.trade_id} closed: {exit_type} @ {exit_price}, PnL: {pnl:.2f}")
        except Exception as e:
            print(f"Error closing trade {self.trade_id}: {e}")
            # Still try to close with 0 PnL as fallback
            try:
                await close_trade(self.trade_id, 0.0)
            except:
                pass

    async def run(self):
        print(f"🔄 Starting OCO manager for {self.symbol} (Trade: {self.trade_id})")
        self._running=True
        check_count = 0
        
        while self._running:
            try:
                check_count += 1
                
                # Check if position is closed first
                if await self._check_position_closed():
                    print(f"🔔 OCO: Position closed for {self.symbol} - cancelling all orders")
                    await self.bybit.cancel_all(CATEGORY, self.symbol)
                    await self._close_trade("position_closed")
                    await output.send_message(templates.tp_hit(self.symbol, "?", "position closed", self.channel_name))
                    self._running=False; break

                # Check for TP/SL fills
                tp_filled, sl_filled = await self._check_tp_filled()
                
                if tp_filled:
                    print(f"🔔 OCO: TP orders filled for {self.symbol} - cancelling SL order")
                    await self.bybit.cancel_all(CATEGORY, self.symbol)
                    await self._close_trade("tp_filled")
                    await output.send_message(templates.tp_hit(self.symbol, "?", "filled", self.channel_name))
                    self._running=False; break

                if sl_filled:
                    print(f"🔔 OCO: SL order filled for {self.symbol} - cancelling TP orders")
                    await self.bybit.cancel_all(CATEGORY, self.symbol)
                    await self._close_trade("sl_hit")
                    await output.send_message(templates.sl_hit(self.symbol, "triggered", self.channel_name))
                    self._running=False; break
                
                # Log every 30 checks (1 minute) to show OCO is running
                if check_count % 30 == 0:
                    print(f"🔄 OCO: Still monitoring {self.symbol} ({check_count} checks)")
                    
            except Exception as e:
                print(f"OCO error for {self.symbol}: {e}")
            await asyncio.sleep(2)
        
        print(f"🛑 OCO manager stopped for {self.symbol}")