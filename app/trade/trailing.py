import asyncio
from decimal import Decimal
from app.telegram.output import send_message
from app.telegram import templates
from app.core.precision import q_price


class TrailingStopManager:
    def __init__(self, bybit_client, trade_id: str, symbol: str, direction: str, sl_price, activation_pct: Decimal = Decimal("0.061")):
        self.bybit = bybit_client
        self.trade_id = trade_id
        self.symbol = symbol
        self.direction = direction  # "BUY" or "SELL"
        self.initial_sl = Decimal(str(sl_price)) if sl_price is not None else None
        self.activation_pct = activation_pct
        self.active = False
        self.last_sl = self.initial_sl

    async def monitor(self, entry_price, qty: str):
        side = "Sell" if self.direction == "BUY" else "Buy"
        print("📈 Starting trailing stop manager...")

        entry_d = Decimal(str(entry_price))

        for _ in range(50):  # ~2-3 minutes depending on sleep
            try:
                ticker = self.bybit.get_ticker(self.symbol) or {}
                last_price_str = ((ticker.get("result", {}).get("list") or [{}])[0].get("lastPrice"))
                if not last_price_str:
                    await asyncio.sleep(5)
                    continue
                last = Decimal(str(last_price_str))

                # Calculate gain percentage relative to entry
                if self.direction == "BUY":
                    change = (last - entry_d) / entry_d
                else:
                    change = (entry_d - last) / entry_d

                if change >= self.activation_pct:
                    # Trail 1% behind current price for demo; in production, make configurable
                    new_sl = last * (Decimal("0.99") if self.direction == "BUY" else Decimal("1.01"))
                    new_sl = q_price(self.symbol, new_sl)
                    # Move only in favorable direction or if not active yet
                    if (not self.active) or (self.direction == "BUY" and (self.last_sl is None or new_sl > self.last_sl)) or (self.direction == "SELL" and (self.last_sl is None or new_sl < self.last_sl)):
                        print(f"🔄 Moving SL to {new_sl}")
                        self.bybit.create_sl_order(
                            symbol=self.symbol,
                            side=side,
                            qty=qty,
                            trigger_price=str(new_sl),
                            trade_id=f"{self.trade_id}-TRL",
                        )
                        self.last_sl = new_sl
                        self.active = True
                        try:
                            await send_message(templates.trailing_moved(self.symbol, str(last)))
                        except Exception:
                            pass
                await asyncio.sleep(5)
            except Exception as e:
                print("Trailing stop error:", e)
                await asyncio.sleep(5)

