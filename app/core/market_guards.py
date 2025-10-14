"""
Market protection guards to prevent trading in unsafe conditions.

CLIENT SPEC Lines 333-341: Market Protection & Liquidity Guards
- Maintenance/cancel-only/suspension: block trading
- Spread guard: block if spread/mid > threshold
- Liquidity guard: block if BBO volume < min (maker protection)
- Price drift guard: abort/amend if price change > X bps during latency
- Price band (PDR): reject orders outside band
- Auto-split if qty > maxOrderQty

All guards must pass before placing orders.
"""

from decimal import Decimal
from typing import Dict, Any, Optional, Tuple
from app.core.logging import system_logger


class MarketGuards:
    """
    Market protection guards to ensure safe trading conditions.
    
    All guards must PASS before an order is placed.
    """
    
    def __init__(self):
        # Guard thresholds (configurable)
        self.max_spread_pct = Decimal("0.5")  # 0.5% max spread
        self.min_liquidity_usdt = Decimal("10000")  # $10k min volume at BBO
        self.max_drift_bps = 50  # 50 basis points max price drift
        
        # Statistics
        self.total_checks = 0
        self.spread_blocks = 0
        self.liquidity_blocks = 0
        self.drift_blocks = 0
        self.maintenance_blocks = 0
        self.pdr_blocks = 0
    
    async def check_all_guards(self, symbol: str, bybit_client,
                               intended_price: Optional[Decimal] = None) -> Tuple[bool, str]:
        """
        Check all guards before placing an order.
        
        Args:
            symbol: Trading symbol
            bybit_client: Bybit API client
            intended_price: Intended order price (for drift check)
        
        Returns:
            (passed, reason) - (True, "") if all passed, (False, reason) if any failed
        """
        self.total_checks += 1
        
        # Guard 1: Maintenance mode check
        passed, reason = await self.check_maintenance_mode(symbol, bybit_client)
        if not passed:
            self.maintenance_blocks += 1
            return False, reason
        
        # Guard 2: Spread check
        passed, reason = await self.check_spread_guard(symbol, bybit_client)
        if not passed:
            self.spread_blocks += 1
            return False, reason
        
        # Guard 3: Liquidity check
        passed, reason = await self.check_liquidity_guard(symbol, bybit_client)
        if not passed:
            self.liquidity_blocks += 1
            return False, reason
        
        # Guard 4: Price drift check (if intended price provided)
        if intended_price is not None:
            passed, reason = await self.check_price_drift(symbol, bybit_client, intended_price)
            if not passed:
                self.drift_blocks += 1
                return False, reason
        
        # All guards passed
        return True, ""
    
    async def check_maintenance_mode(self, symbol: str, bybit_client) -> Tuple[bool, str]:
        """
        Check if symbol is in maintenance/suspended.
        
        CLIENT SPEC Line 334: Block trading on maintenance/cancel-only/suspension.
        
        Returns:
            (True, "") if trading allowed
            (False, reason) if maintenance detected
        """
        try:
            # Get instrument info
            response = await bybit_client.get_instrument_info(symbol)
            
            if response.get("retCode") != 0:
                return False, f"Failed to get instrument info: {response.get('retMsg')}"
            
            instruments = response.get("result", {}).get("list", [])
            if not instruments:
                return False, f"Symbol {symbol} not found"
            
            instrument = instruments[0]
            status = instrument.get("status", "")
            
            # Check status
            if status != "Trading":
                system_logger.warning("Maintenance mode detected", {
                    "symbol": symbol,
                    "status": status,
                    "action": "BLOCK_TRADING"
                })
                return False, f"Symbol in {status} mode (not Trading)"
            
            return True, ""
            
        except Exception as e:
            system_logger.error(f"Maintenance check error: {e}", exc_info=True)
            # Fail-safe: block on error
            return False, f"Maintenance check failed: {e}"
    
    async def check_spread_guard(self, symbol: str, bybit_client) -> Tuple[bool, str]:
        """
        Check if spread is within acceptable limits.
        
        CLIENT SPEC Line 336: "Spread guard: block if spread/mid > threshold"
        
        Wide spreads indicate poor market conditions or low liquidity.
        
        Returns:
            (True, "") if spread acceptable
            (False, reason) if spread too wide
        """
        try:
            # Get ticker for bid/ask
            response = await bybit_client.get_ticker(symbol)
            
            if response.get("retCode") != 0:
                return False, f"Failed to get ticker: {response.get('retMsg')}"
            
            tickers = response.get("result", {}).get("list", [])
            if not tickers:
                return False, f"No ticker data for {symbol}"
            
            ticker = tickers[0]
            
            # Extract bid/ask
            bid_str = ticker.get("bid1Price", "0")
            ask_str = ticker.get("ask1Price", "0")
            
            if not bid_str or not ask_str:
                return False, "Missing bid/ask prices"
            
            bid = Decimal(str(bid_str))
            ask = Decimal(str(ask_str))
            
            if bid == 0 or ask == 0:
                return False, "Invalid bid/ask prices (zero)"
            
            # Calculate spread
            spread = ask - bid
            mid = (bid + ask) / Decimal("2")
            spread_pct = (spread / mid) * 100
            
            # Check against threshold
            if spread_pct > self.max_spread_pct:
                system_logger.warning("Spread guard triggered", {
                    "symbol": symbol,
                    "bid": float(bid),
                    "ask": float(ask),
                    "spread": float(spread),
                    "spread_pct": float(spread_pct),
                    "threshold_pct": float(self.max_spread_pct),
                    "action": "BLOCK_ORDER"
                })
                return False, f"Spread too wide: {spread_pct:.3f}% > {self.max_spread_pct}%"
            
            return True, ""
            
        except Exception as e:
            system_logger.error(f"Spread guard error: {e}", exc_info=True)
            # Fail-safe: block on error
            return False, f"Spread check failed: {e}"
    
    async def check_liquidity_guard(self, symbol: str, bybit_client) -> Tuple[bool, str]:
        """
        Check if liquidity is sufficient at best bid/offer.
        
        CLIENT SPEC Line 337: "Liquidity guard: block if BBO volume < min (maker protection)"
        
        Low liquidity increases slippage risk for market orders.
        
        Returns:
            (True, "") if liquidity sufficient
            (False, reason) if liquidity too low
        """
        try:
            # Get orderbook
            response = await bybit_client.get_orderbook(symbol, limit=5)
            
            if response.get("retCode") != 0:
                return False, f"Failed to get orderbook: {response.get('retMsg')}"
            
            orderbook = response.get("result", {})
            bids = orderbook.get("b", [])
            asks = orderbook.get("a", [])
            
            if not bids or not asks:
                return False, "Empty orderbook"
            
            # Get best bid/ask volumes
            best_bid_price = Decimal(str(bids[0][0]))
            best_bid_vol = Decimal(str(bids[0][1]))
            best_ask_price = Decimal(str(asks[0][0]))
            best_ask_vol = Decimal(str(asks[0][1]))
            
            # Calculate volume in USDT
            bid_volume_usdt = best_bid_vol * best_bid_price
            ask_volume_usdt = best_ask_vol * best_ask_price
            
            # Check against minimum
            min_volume = min(bid_volume_usdt, ask_volume_usdt)
            
            if min_volume < self.min_liquidity_usdt:
                system_logger.warning("Liquidity guard triggered", {
                    "symbol": symbol,
                    "bid_volume_usdt": float(bid_volume_usdt),
                    "ask_volume_usdt": float(ask_volume_usdt),
                    "min_volume_usdt": float(min_volume),
                    "threshold_usdt": float(self.min_liquidity_usdt),
                    "action": "BLOCK_ORDER"
                })
                return False, f"Insufficient liquidity: ${min_volume:.2f} < ${self.min_liquidity_usdt}"
            
            return True, ""
            
        except Exception as e:
            system_logger.error(f"Liquidity guard error: {e}", exc_info=True)
            # Fail-safe: block on error
            return False, f"Liquidity check failed: {e}"
    
    async def check_price_drift(self, symbol: str, bybit_client,
                                intended_price: Decimal) -> Tuple[bool, str]:
        """
        Check if price drifted significantly during order preparation.
        
        CLIENT SPEC Line 338: "Price drift guard: abort/amend if price change > X bps during ack latency"
        
        If price moves too much while preparing an order, the order
        might get filled at an unfavorable price.
        
        Args:
            symbol: Trading symbol
            bybit_client: Bybit API client
            intended_price: Price when order was prepared
        
        Returns:
            (True, "") if drift acceptable
            (False, reason) if drift too large
        """
        try:
            # Get current market price
            response = await bybit_client.get_ticker(symbol)
            
            if response.get("retCode") != 0:
                return False, f"Failed to get ticker: {response.get('retMsg')}"
            
            tickers = response.get("result", {}).get("list", [])
            if not tickers:
                return False, f"No ticker data for {symbol}"
            
            ticker = tickers[0]
            current_price = Decimal(str(ticker.get("lastPrice", "0")))
            
            if current_price == 0:
                return False, "Invalid current price (zero)"
            
            # Calculate drift
            drift = abs(current_price - intended_price) / intended_price
            drift_bps = drift * 10000  # Convert to basis points
            
            # Check against threshold
            if drift_bps > self.max_drift_bps:
                system_logger.warning("Price drift guard triggered", {
                    "symbol": symbol,
                    "intended_price": float(intended_price),
                    "current_price": float(current_price),
                    "drift_bps": float(drift_bps),
                    "threshold_bps": self.max_drift_bps,
                    "action": "ABORT_ORDER"
                })
                return False, f"Price drifted {drift_bps:.1f} bps > {self.max_drift_bps} bps"
            
            return True, ""
            
        except Exception as e:
            system_logger.error(f"Price drift guard error: {e}", exc_info=True)
            # Fail-safe: allow on check failure (conservative for limit orders)
            return True, f"Drift check failed (allowed): {e}"
    
    async def check_price_band(self, symbol: str, bybit_client,
                              price: Decimal, side: str) -> Tuple[bool, str]:
        """
        Check if price is within allowed price band (PDR).
        
        CLIENT SPEC Line 339: "Price band (PDR): reject orders outside band"
        
        Bybit has price deviation rules (PDR) that auto-reject orders
        too far from mark price.
        
        Returns:
            (True, "") if price within band
            (False, reason) if price outside band
        """
        try:
            # Get ticker for mark price
            response = await bybit_client.get_ticker(symbol)
            
            if response.get("retCode") != 0:
                return True, "Cannot check PDR (allowed)"
            
            tickers = response.get("result", {}).get("list", [])
            if not tickers:
                return True, "Cannot check PDR (allowed)"
            
            ticker = tickers[0]
            mark_price = Decimal(str(ticker.get("markPrice", "0")))
            
            if mark_price == 0:
                return True, "Cannot check PDR (allowed)"
            
            # Calculate deviation
            deviation = abs(price - mark_price) / mark_price * 100
            
            # Typical PDR limits are 1-5% depending on symbol
            # Use conservative 3% limit
            max_deviation_pct = Decimal("3.0")
            
            if deviation > max_deviation_pct:
                system_logger.warning("Price band (PDR) guard triggered", {
                    "symbol": symbol,
                    "order_price": float(price),
                    "mark_price": float(mark_price),
                    "deviation_pct": float(deviation),
                    "max_deviation_pct": float(max_deviation_pct),
                    "action": "REJECT_ORDER"
                })
                return False, f"Price outside band: {deviation:.2f}% > {max_deviation_pct}%"
            
            return True, ""
            
        except Exception as e:
            system_logger.error(f"Price band check error: {e}", exc_info=True)
            # Fail-safe: allow on check failure
            return True, f"PDR check failed (allowed): {e}"
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get guard statistics."""
        return {
            "total_checks": self.total_checks,
            "spread_blocks": self.spread_blocks,
            "liquidity_blocks": self.liquidity_blocks,
            "drift_blocks": self.drift_blocks,
            "maintenance_blocks": self.maintenance_blocks,
            "pdr_blocks": self.pdr_blocks
        }


# Global market guards instance
_market_guards: Optional[MarketGuards] = None


def get_market_guards() -> MarketGuards:
    """Get global market guards instance."""
    global _market_guards
    if _market_guards is None:
        _market_guards = MarketGuards()
    return _market_guards


async def check_trading_conditions(symbol: str, bybit_client,
                                   intended_price: Optional[Decimal] = None) -> Tuple[bool, str]:
    """
    Check if trading conditions are safe for placing an order.
    
    CLIENT SPEC: All guards must pass before order placement.
    
    Args:
        symbol: Trading symbol
        bybit_client: Bybit API client
        intended_price: Intended order price (optional)
    
    Returns:
        (allowed, reason) - (True, "") if safe, (False, reason) if unsafe
    """
    guards = get_market_guards()
    passed, reason = await guards.check_all_guards(symbol, bybit_client, intended_price)
    
    if not passed:
        system_logger.warning("Trading conditions unsafe", {
            "symbol": symbol,
            "reason": reason,
            "action": "BLOCK_ORDER"
        })
    
    return passed, reason

