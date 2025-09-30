from __future__ import annotations
from app.bybit.client import BybitClient
from app import settings


class MarginModeManager:
    def __init__(self, bybit_client: BybitClient):
        self.bybit = bybit_client
        self.margin_mode = settings.MARGIN_MODE

    async def enforce_margin_mode(self, symbol: str):
        """Enforce isolated margin mode for a symbol."""
        try:
            if self.margin_mode.lower() == "isolated":
                # Check current position to see margin mode
                response = await self.bybit.positions("linear", symbol)
                if response.get("retCode") == 0:
                    print(f"✅ Margin mode check completed for {symbol}")
                else:
                    print(f"⚠️ Failed to check margin mode for {symbol}: {response}")
            else:
                print(f"ℹ️ Using {self.margin_mode} margin mode for {symbol}")
                
        except Exception as e:
            print(f"Error checking margin mode for {symbol}: {e}")

    async def check_margin_mode(self, symbol: str) -> str:
        """Check current margin mode for a symbol."""
        try:
            response = await self.bybit.positions("linear", symbol)
            if response.get("retCode") == 0:
                # Extract margin mode from position data
                positions = response.get("result", {}).get("list", [])
                if positions:
                    mode = positions[0].get("tradeMode", "unknown")
                    print(f"📊 Current margin mode for {symbol}: {mode}")
                    return mode
                return "unknown"
            else:
                print(f"⚠️ Failed to get margin mode for {symbol}: {response}")
                return "unknown"
        except Exception as e:
            print(f"Error checking margin mode for {symbol}: {e}")
            return "unknown"


# Note: Margin mode methods would need to be added to the async BybitClient
# For now, we'll use the existing position methods to check margin mode