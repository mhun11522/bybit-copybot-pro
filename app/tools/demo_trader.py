"""
Demo Trading Tool for Bybit Copybot Testing

This tool helps you create and manage demo positions for testing the bot's
TP/SL automation without risking real money.
"""

import asyncio
import httpx
from decimal import Decimal, ROUND_DOWN
from typing import Dict, Any, List, Optional
from app.core.logging import system_logger
from app.bybit.client import get_bybit_client
from app.core.strict_config import STRICT_CONFIG


class DemoTradingTool:
    """Tool for creating and managing demo positions for testing."""
    
    def __init__(self):
        self.client = get_bybit_client()
        self.config = STRICT_CONFIG
        
    async def create_demo_position(
        self, 
        symbol: str, 
        side: str, 
        im_usdt: Decimal = Decimal("10"),
        leverage: Decimal = Decimal("10"),
        entry_price: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """
        Create a demo position for testing.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            side: "Buy" or "Sell"
            im_usdt: Initial margin in USDT
            leverage: Leverage multiplier
            entry_price: Optional specific entry price (uses market if None)
        
        Returns:
            Dict with position creation result
        """
        try:
            # Validate symbol exists
            symbol_exists = await self.client.symbol_exists("linear", symbol)
            if not symbol_exists:
                raise ValueError(f"Symbol {symbol} does not exist or is not tradable")
            
            # Get current market price if not provided
            if entry_price is None:
                ticker_data = await self.client.get_ticker(symbol)
                if ticker_data["retCode"] != 0:
                    raise ValueError(f"Could not get ticker for {symbol}")
                
                market_price = Decimal(str(ticker_data["result"]["list"][0]["lastPrice"]))
                entry_price = market_price
                system_logger.info(f"Using market price for {symbol}: {entry_price}")
            
            # Calculate position size
            position_value = float(im_usdt) * float(leverage)
            qty = Decimal(str(position_value / float(entry_price)))
            
            # Normalize quantity to symbol's step size
            qty = self._normalize_quantity(qty, symbol)
            
            # Set leverage first
            try:
                await self.client.set_leverage("linear", symbol, float(leverage), float(leverage))
                system_logger.info(f"Set leverage to {leverage}x for {symbol}")
            except Exception as e:
                system_logger.warning(f"Could not set leverage for {symbol}: {e}")
            
            # Create market order for immediate fill
            order_body = {
                "category": "linear",
                "symbol": symbol,
                "side": side,
                "orderType": "Market",
                "qty": str(qty),
                "timeInForce": "IOC",
                "reduceOnly": False,
                "positionIdx": 0,
                "orderLinkId": f"demo_entry_{symbol}_{side.lower()}"
            }
            
            result = await self.client.place_order(order_body)
            
            if result["retCode"] == 0:
                order_id = result["result"]["orderId"]
                system_logger.info(f"✅ Demo position created: {symbol} {side} {qty} @ ~{entry_price}")
                system_logger.info(f"   Order ID: {order_id}")
                system_logger.info(f"   Initial Margin: {im_usdt} USDT")
                system_logger.info(f"   Leverage: {leverage}x")
                system_logger.info(f"   Position Value: {position_value} USDT")
                
                return {
                    "success": True,
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,
                    "entry_price": entry_price,
                    "order_id": order_id,
                    "initial_margin": im_usdt,
                    "leverage": leverage,
                    "position_value": position_value
                }
            else:
                error_msg = result.get("retMsg", "Unknown error")
                system_logger.error(f"❌ Failed to create demo position: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "symbol": symbol
                }
                
        except Exception as e:
            system_logger.error(f"❌ Error creating demo position for {symbol}: {e}")
            return {
                "success": False,
                "error": str(e),
                "symbol": symbol
            }
    
    def _normalize_quantity(self, qty: Decimal, symbol: str) -> Decimal:
        """Normalize quantity to symbol's step size."""
        # Common step sizes for major symbols
        step_sizes = {
            "BTCUSDT": Decimal("0.001"),
            "ETHUSDT": Decimal("0.01"),
            "DOGEUSDT": Decimal("1"),
            "ADAUSDT": Decimal("1"),
            "SOLUSDT": Decimal("0.1"),
            "XRPUSDT": Decimal("1"),
            "DOTUSDT": Decimal("0.1"),
            "LINKUSDT": Decimal("0.1"),
            "UNIUSDT": Decimal("0.1"),
            "LTCUSDT": Decimal("0.01"),
            "BCHUSDT": Decimal("0.001"),
            "FXSUSDT": Decimal("0.1"),
            "AVAXUSDT": Decimal("0.1"),
            "MATICUSDT": Decimal("1"),
            "ATOMUSDT": Decimal("0.1"),
            "FTMUSDT": Decimal("1"),
            "NEARUSDT": Decimal("0.1"),
            "ALGOUSDT": Decimal("1"),
            "VETUSDT": Decimal("1"),
            "FILUSDT": Decimal("0.1"),
            "TRXUSDT": Decimal("1"),
            "ETCUSDT": Decimal("0.01"),
            "XLMUSDT": Decimal("1"),
            "LDOUSDT": Decimal("0.1"),
            "APTUSDT": Decimal("0.1"),
            "ARBUSDT": Decimal("0.1"),
            "OPUSDT": Decimal("0.1"),
            "INJUSDT": Decimal("0.1"),
            "TIAUSDT": Decimal("0.1"),
            "SEIUSDT": Decimal("1"),
            "SUIUSDT": Decimal("0.1"),
            "WLDUSDT": Decimal("0.1"),
            "ORDIUSDT": Decimal("0.01"),
            "PENDLEUSDT": Decimal("0.1"),
            "WIFUSDT": Decimal("1"),
            "JUPUSDT": Decimal("1"),
            "BOMEUSDT": Decimal("100"),
            "FLOKIUSDT": Decimal("1000"),
            "PEPEUSDT": Decimal("1000000"),
            "SHIBUSDT": Decimal("1000"),
            "BONKUSDT": Decimal("1000"),
        }
        
        step_size = step_sizes.get(symbol, Decimal("0.001"))  # Default fallback
        
        # Round down to nearest step
        normalized = (qty // step_size) * step_size
        
        # Ensure minimum quantity
        if normalized < step_size:
            normalized = step_size
            
        return normalized
    
    async def create_multiple_demo_positions(
        self, 
        symbols: List[str], 
        im_per_position: Decimal = Decimal("5"),
        leverage: Decimal = Decimal("10")
    ) -> List[Dict[str, Any]]:
        """Create multiple demo positions for comprehensive testing."""
        results = []
        
        for symbol in symbols:
            # Alternate between buy and sell
            side = "Buy" if len(results) % 2 == 0 else "Sell"
            
            system_logger.info(f"Creating demo position: {symbol} {side}")
            result = await self.create_demo_position(
                symbol=symbol,
                side=side,
                im_usdt=im_per_position,
                leverage=leverage
            )
            results.append(result)
            
            # Small delay between orders
            await asyncio.sleep(1)
        
        return results
    
    async def get_demo_positions(self) -> List[Dict[str, Any]]:
        """Get all current demo positions."""
        try:
            # Get positions for linear category
            result = await self.client.positions("linear", "")
            
            if result["retCode"] == 0:
                positions = result["result"]["list"]
                active_positions = [pos for pos in positions if Decimal(pos["size"]) > 0]
                
                system_logger.info(f"Found {len(active_positions)} active demo positions")
                for pos in active_positions:
                    symbol = pos["symbol"]
                    side = pos["side"]
                    size = pos["size"]
                    avg_price = pos["avgPrice"]
                    unrealized_pnl = pos["unrealisedPnl"]
                    
                    system_logger.info(f"  {symbol}: {side} {size} @ {avg_price} (PnL: {unrealized_pnl})")
                
                return active_positions
            else:
                system_logger.error(f"Failed to get positions: {result.get('retMsg')}")
                return []
                
        except Exception as e:
            system_logger.error(f"Error getting demo positions: {e}")
            return []
    
    async def close_all_demo_positions(self) -> Dict[str, Any]:
        """Close all demo positions."""
        try:
            positions = await self.get_demo_positions()
            
            if not positions:
                system_logger.info("No positions to close")
                return {"success": True, "closed": 0}
            
            closed_count = 0
            for pos in positions:
                symbol = pos["symbol"]
                side = pos["side"]
                size = pos["size"]
                
                # Create opposite order to close position
                close_side = "Sell" if side == "Buy" else "Buy"
                
                close_body = {
                    "category": "linear",
                    "symbol": symbol,
                    "side": close_side,
                    "orderType": "Market",
                    "qty": size,
                    "timeInForce": "IOC",
                    "reduceOnly": True,
                    "positionIdx": 0,
                    "orderLinkId": f"demo_close_{symbol}"
                }
                
                result = await self.client.place_order(close_body)
                
                if result["retCode"] == 0:
                    system_logger.info(f"✅ Closed position: {symbol} {close_side} {size}")
                    closed_count += 1
                else:
                    system_logger.error(f"❌ Failed to close {symbol}: {result.get('retMsg')}")
                
                await asyncio.sleep(0.5)  # Small delay between closes
            
            system_logger.info(f"Closed {closed_count}/{len(positions)} demo positions")
            return {"success": True, "closed": closed_count}
            
        except Exception as e:
            system_logger.error(f"Error closing demo positions: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_demo_wallet_balance(self) -> Dict[str, Any]:
        """Get demo wallet balance."""
        try:
            result = await self.client.get_wallet_balance()
            
            if result["retCode"] == 0:
                accounts = result["result"]["list"]
                if accounts:
                    account = accounts[0]  # Unified account
                    coins = account.get("coin", [])
                    
                    for coin in coins:
                        if coin["coin"] == "USDT":
                            balance = coin["walletBalance"]
                            system_logger.info(f"Demo wallet balance: {balance} USDT")
                            return {"success": True, "balance": balance, "coin": "USDT"}
                
                system_logger.warning("No USDT balance found in demo account")
                return {"success": False, "error": "No USDT balance found"}
            else:
                system_logger.error(f"Failed to get wallet balance: {result.get('retMsg')}")
                return {"success": False, "error": result.get('retMsg')}
                
        except Exception as e:
            system_logger.error(f"Error getting demo wallet balance: {e}")
            return {"success": False, "error": str(e)}


# Convenience functions for easy usage
async def create_demo_position(symbol: str, side: str = "Buy", im_usdt: float = 10.0, leverage: float = 10.0):
    """Quick function to create a single demo position."""
    tool = DemoTradingTool()
    return await tool.create_demo_position(
        symbol=symbol,
        side=side,
        im_usdt=Decimal(str(im_usdt)),
        leverage=Decimal(str(leverage))
    )

async def create_multiple_demo_positions(symbols: List[str], im_per_position: float = 5.0, leverage: float = 10.0):
    """Quick function to create multiple demo positions."""
    tool = DemoTradingTool()
    return await tool.create_multiple_demo_positions(
        symbols=symbols,
        im_per_position=Decimal(str(im_per_position)),
        leverage=Decimal(str(leverage))
    )

async def get_demo_positions():
    """Quick function to get all demo positions."""
    tool = DemoTradingTool()
    return await tool.get_demo_positions()

async def close_all_demo_positions():
    """Quick function to close all demo positions."""
    tool = DemoTradingTool()
    return await tool.close_all_demo_positions()

async def get_demo_wallet_balance():
    """Quick function to get demo wallet balance."""
    tool = DemoTradingTool()
    return await tool.get_demo_wallet_balance()


if __name__ == "__main__":
    """Demo testing script - run this to test the demo trading functionality."""
    
    async def main():
        print("🚀 Starting Bybit Demo Trading Test")
        print("=" * 50)
        
        # Initialize tool
        tool = DemoTradingTool()
        
        # Check wallet balance
        print("\n📊 Checking demo wallet balance...")
        balance_result = await tool.get_demo_wallet_balance()
        if balance_result["success"]:
            print(f"✅ Demo wallet balance: {balance_result['balance']} USDT")
        else:
            print(f"❌ Failed to get balance: {balance_result['error']}")
            return
        
        # Create test positions
        test_symbols = ["BTCUSDT", "ETHUSDT", "DOGEUSDT"]
        print(f"\n🎯 Creating demo positions for: {', '.join(test_symbols)}")
        
        results = await tool.create_multiple_demo_positions(
            symbols=test_symbols,
            im_per_position=Decimal("5"),
            leverage=Decimal("10")
        )
        
        # Show results
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]
        
        print(f"\n📈 Results: {len(successful)} successful, {len(failed)} failed")
        
        if successful:
            print("\n✅ Successfully created positions:")
            for result in successful:
                print(f"   {result['symbol']}: {result['side']} {result['qty']} @ ~{result['entry_price']}")
        
        if failed:
            print("\n❌ Failed to create positions:")
            for result in failed:
                print(f"   {result['symbol']}: {result['error']}")
        
        # Show current positions
        print("\n📋 Current demo positions:")
        positions = await tool.get_demo_positions()
        
        if positions:
            print("✅ Your bot should now detect these positions and add TP/SL automatically!")
            print("\n🔍 Monitor your bot logs for TP/SL automation messages")
        else:
            print("❌ No positions found - check your demo account setup")
        
        print("\n🎉 Demo testing setup complete!")
        print("💡 Next steps:")
        print("   1. Start your main bot (main_strict.py)")
        print("   2. Watch for TP/SL automation in bot logs")
        print("   3. Check Bybit Testnet dashboard for TP/SL orders")
    
    # Run the demo
    asyncio.run(main())
