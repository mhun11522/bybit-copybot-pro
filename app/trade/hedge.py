import asyncio
from decimal import Decimal
from app.telegram.output import send_message
from app.telegram import templates
from app.core.precision import q_price


class HedgeReentryManager:
    def __init__(self, bybit_client, trade_id: str, symbol: str, direction: str, leverage: int, sl_pct: Decimal = Decimal("0.02"), max_reentries: int = 3):
        self.bybit = bybit_client
        self.trade_id = trade_id
        self.symbol = symbol
        self.direction = direction  # "BUY" or "SELL"
        self.leverage = leverage
        self.sl_pct = sl_pct
        self.max_reentries = max_reentries
        self.count = 0

    async def monitor(self, entry_price, qty: str):
        print("🛡 Starting hedge/re-entry manager...")
        entry_d = Decimal(str(entry_price))

        while self.count < self.max_reentries:
            try:
                ticker = self.bybit.get_ticker(self.symbol) or {}
                last_price_str = ((ticker.get("result", {}).get("list") or [{}])[0].get("lastPrice"))
                if not last_price_str:
                    await asyncio.sleep(5)
                    continue
                last = Decimal(str(last_price_str))

                if self.direction == "BUY":
                    change = (entry_d - last) / entry_d  # loss %
                else:
                    change = (last - entry_d) / entry_d  # loss % for shorts

                if change >= self.sl_pct:
                    print(f"⚠️ Hedge triggered at {last}, reversing position")
                    try:
                        await send_message(templates.hedge_triggered(self.symbol))
                    except Exception:
                        pass
                    await self._reverse_position(last, qty)
                    self.count += 1
                    # flip direction and reset entry
                    self.direction = "SELL" if self.direction == "BUY" else "BUY"
                    entry_d = last

                await asyncio.sleep(5)
            except Exception as e:
                print("Hedge monitor error:", e)
                await asyncio.sleep(5)

    async def _reverse_position(self, price: Decimal, qty: str):
        side_close = "Sell" if self.direction == "BUY" else "Buy"
        side_open = "Buy" if self.direction == "BUY" else "Sell"

        print("❌ Closing losing position...")
        # Use immediate-trigger conditional market to close
        self.bybit.create_sl_order(
            symbol=self.symbol,
            side=side_close,
            qty=qty,
            trigger_price=str(q_price(self.symbol, price)),
            trade_id=f"{self.trade_id}-CLOSE{self.count+1}",
        )

        print("🔄 Opening reverse position...")
        self.bybit.create_entry_order(
            symbol=self.symbol,
            side=side_open,
            qty=qty,
            price=str(q_price(self.symbol, price)),
            trade_id=f"{self.trade_id}-REV{self.count+1}",
            entry_no=1,
        )

