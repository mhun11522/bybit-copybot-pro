from __future__ import annotations
from app.bybit_client import BybitClient
from app import settings


class MarginModeManager:
    def __init__(self, bybit_client: BybitClient):
        self.bybit = bybit_client
        self.margin_mode = settings.MARGIN_MODE

    async def enforce_margin_mode(self, symbol: str):
        """Enforce isolated margin mode for a symbol."""
        try:
            if self.margin_mode.lower() == "isolated":
                # Set margin mode to isolated
                response = await self.bybit.set_margin_mode(symbol, "isolated")
                if response.get("retCode") == 0:
                    print(f"✅ Set margin mode to isolated for {symbol}")
                else:
                    print(f"⚠️ Failed to set margin mode for {symbol}: {response}")
            else:
                print(f"ℹ️ Using {self.margin_mode} margin mode for {symbol}")
                
        except Exception as e:
            print(f"Error setting margin mode for {symbol}: {e}")

    async def check_margin_mode(self, symbol: str) -> str:
        """Check current margin mode for a symbol."""
        try:
            response = await self.bybit.get_margin_mode(symbol)
            if response.get("retCode") == 0:
                mode = response.get("result", {}).get("marginMode", "unknown")
                print(f"📊 Current margin mode for {symbol}: {mode}")
                return mode
            else:
                print(f"⚠️ Failed to get margin mode for {symbol}: {response}")
                return "unknown"
        except Exception as e:
            print(f"Error checking margin mode for {symbol}: {e}")
            return "unknown"


# Add margin mode methods to BybitClient
async def set_margin_mode(self, symbol: str, margin_mode: str):
    """Set margin mode for a symbol."""
    body = {
        "category": "linear",
        "symbol": symbol,
        "tradeMode": 1,  # 1 = isolated, 0 = cross
    }
    return self._post("/v5/position/set-trading-stop", body)

async def get_margin_mode(self, symbol: str):
    """Get current margin mode for a symbol."""
    params = {
        "category": "linear",
        "symbol": symbol,
    }
    return self._get("/v5/position/list", params, auth=True)

# Add methods to BybitClient class
BybitClient.set_margin_mode = set_margin_mode
BybitClient.get_margin_mode = get_margin_mode