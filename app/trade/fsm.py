import asyncio
from enum import Enum, auto


class TradeState(Enum):
    RECEIVED = auto()
    LEVERAGE_SET = auto()
    ENTRIES_PLACED = auto()
    POSITION_CONFIRMED = auto()
    TPSL_PLACED = auto()
    DONE = auto()
    ERROR = auto()


class TradeFSM:
    def __init__(self, signal: dict, bybit_client, telegram_client):
        self.signal = signal
        self.bybit = bybit_client
        self.tg = telegram_client
        self.state = TradeState.RECEIVED
        self.trade_id = f"TRD-{signal['symbol']}-{signal['direction']}"

    async def run(self):
        try:
            await self.set_leverage()
            await self.place_entries()
            await self.confirm_position()
            await self.place_tpsl()
            self.state = TradeState.DONE
            print(f"✅ Trade finished: {self.trade_id}")
        except Exception as e:
            self.state = TradeState.ERROR
            print(f"❌ Error in trade {self.trade_id}: {e}")

    async def set_leverage(self):
        print(f"🔧 Setting leverage for {self.signal['symbol']}")
        await asyncio.sleep(1)  # later: call Bybit
        self.state = TradeState.LEVERAGE_SET

    async def place_entries(self):
        print(f"📥 Placing entry orders: {self.signal['entries']}")
        await asyncio.sleep(1)  # later: Bybit create_order
        self.state = TradeState.ENTRIES_PLACED

    async def confirm_position(self):
        print("🔍 Waiting for position confirmation...")
        await asyncio.sleep(1)  # later: poll get_positions
        self.state = TradeState.POSITION_CONFIRMED

    async def place_tpsl(self):
        print(f"🎯 Placing TP/SL orders: TP={self.signal['tps']}, SL={self.signal['sl']}")
        await asyncio.sleep(1)  # later: Bybit tp/sl orders
        self.state = TradeState.TPSL_PLACED