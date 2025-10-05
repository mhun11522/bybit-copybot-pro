"""Position size calculator with proper Bybit contract-based sizing."""

from decimal import Decimal, ROUND_DOWN
from typing import Dict, Any, Optional, Tuple
from app.core.logging import system_logger
from app.core.symbol_registry import SymbolInfo

class PositionCalculator:
    """Calculate position sizes using proper Bybit contract-based logic."""
    
    @staticmethod
    def calculate_contract_qty_simple(
        symbol: str, 
        im_usdt: Decimal, 
        leverage: Decimal, 
        entry_price: Decimal, 
        symbol_info: SymbolInfo
    ) -> Decimal:
        """
        Calculate a valid contract quantity for Bybit USDT perpetuals.
        Drop-in helper function as provided by client.

        Args:
            symbol (str): Symbol, e.g., "DOGEUSDT"
            im_usdt (Decimal): Initial margin allocated in USDT (e.g., 20)
            leverage (Decimal): Leverage factor (e.g., 14.67)
            entry_price (Decimal): Planned entry price
            symbol_info (SymbolInfo): Symbol metadata

        Returns:
            Decimal: A valid contract quantity, quantized to stepSize.
        """
        from decimal import ROUND_DOWN
        
        # Extract symbol constraints
        min_qty = symbol_info.min_qty
        max_qty = symbol_info.max_qty
        step_size = symbol_info.step_size
        min_notional = symbol_info.min_notional

        # Raw contracts (1 contract = 1 base coin, e.g., 1 DOGE)
        contracts = (im_usdt * leverage) / entry_price

        # Quantize to step size (round down)
        contracts = (contracts // step_size) * step_size

        # Ensure within min/max
        if contracts < min_qty:
            raise ValueError(f"{symbol} qty {contracts} < min {min_qty}")
        if contracts > max_qty:
            contracts = max_qty

        # Ensure notional is valid
        notional = contracts * entry_price
        if notional < min_notional:
            raise ValueError(f"{symbol} notional {notional} < minNotional {min_notional}")
        
        # Apply demo environment specific limits
        from app.core.demo_config import DemoConfig
        if DemoConfig.is_demo_environment():
            contracts = DemoConfig.apply_demo_quantity_limit(contracts, symbol)
            contracts = (contracts // step_size) * step_size
            notional = contracts * entry_price
            
            # Ensure demo environment still meets minimum notional
            if notional < min_notional:
                system_logger.warning(f"Demo environment: Notional {notional} below min {min_notional}, adjusting")
                # Calculate minimum contracts needed for min_notional
                min_contracts = min_notional / entry_price
                from decimal import ROUND_UP
                contracts = min_contracts.quantize(step_size, rounding=ROUND_UP)
                notional = contracts * entry_price
                system_logger.info(f"Demo environment: Adjusted to meet min_notional, contracts: {contracts}, notional: {notional}")
            
            system_logger.info(f"Demo environment: Applied demo quantity limits, final contracts: {contracts}")
        
        # Ensure final notional is still valid after any adjustments
        if notional < min_notional:
            raise ValueError(f"{symbol} adjusted notional {notional} < minNotional {min_notional}")

        return contracts

    @staticmethod
    async def calculate_contract_qty(
        symbol: str,
        wallet_balance: Decimal,
        risk_pct: Decimal,
        leverage: Decimal,
        entry_price: Decimal,
        symbol_info: SymbolInfo,
        channel_risk_multiplier: Decimal = Decimal("1.0")
    ) -> Tuple[Decimal, Dict[str, Any]]:
        """
        Calculate proper contract quantity for Bybit orders.
        
        Args:
            symbol: Trading symbol (e.g., "DOGEUSDT")
            wallet_balance: Total wallet balance in USDT
            risk_pct: Risk percentage (e.g., 0.02 for 2%)
            leverage: Leverage multiplier (e.g., 14.67)
            entry_price: Entry price in USDT
            symbol_info: Symbol metadata from Bybit
            channel_risk_multiplier: Channel-specific risk multiplier
            
        Returns:
            Tuple of (contract_qty, debug_info)
        """
        try:
            # Step 1: Calculate IM (Initial Margin) based on risk
            # IM = risk% * wallet_balance * channel_multiplier
            base_im = wallet_balance * risk_pct * channel_risk_multiplier
            
            # DEMO ENVIRONMENT: Use very conservative position sizing
            # For demo environment, use much smaller positions to avoid "ab not enough" errors
            from app.core.demo_config import DemoConfig
            if DemoConfig.is_demo_environment():
                # Demo environment: Use very conservative sizing
                conservative_multiplier = Decimal("0.01")  # 1% of calculated IM
                min_im = Decimal("5.0")   # 5 USDT minimum for demo
                price_tier = "DEMO_CONSERVATIVE"
            else:
                # Live environment: Dynamic position sizing based on token price range
                if entry_price < Decimal("0.001"):
                    conservative_multiplier = Decimal("10.0")
                    min_im = Decimal("200.0")
                    price_tier = "EXTREME_ULTRA_LOW"
                elif entry_price < Decimal("0.01"):
                    conservative_multiplier = Decimal("8.0")
                    min_im = Decimal("150.0")
                    price_tier = "ULTRA_LOW"
                elif entry_price < Decimal("0.1"):
                    conservative_multiplier = Decimal("5.0")
                    min_im = Decimal("100.0")
                    price_tier = "LOW"
                elif entry_price < Decimal("1.0"):
                    conservative_multiplier = Decimal("3.0")
                    min_im = Decimal("75.0")
                    price_tier = "MEDIUM"
                else:
                    conservative_multiplier = Decimal("1.0")
                    min_im = Decimal("25.0")
                    price_tier = "HIGH"
            
            im = base_im * conservative_multiplier
            im = max(im, min_im)
            
            # Use the client's exact formula for contract calculation
            try:
                final_contracts = PositionCalculator.calculate_contract_qty_simple(
                    symbol=symbol,
                    im_usdt=im,
                    leverage=leverage,
                    entry_price=entry_price,
                    symbol_info=symbol_info
                )
                final_notional = final_contracts * entry_price
                
                # Fallback: If notional is still too small, use maximum allowed quantity
                if final_notional < Decimal("5.0"):
                    system_logger.warning(f"Notional {final_notional} still too small, using maximum quantity")
                    # Use 90% of max quantity to ensure we don't exceed limits
                    max_safe_qty = symbol_info.max_qty * Decimal("0.9")
                    final_contracts = max_safe_qty
                    final_notional = final_contracts * entry_price
                    system_logger.info(f"Using maximum safe quantity: {final_contracts} contracts, notional: {final_notional}")
                    
            except ValueError as e:
                system_logger.error(f"Contract calculation failed: {e}")
                # Fallback to maximum safe quantity
                max_safe_qty = symbol_info.max_qty * Decimal("0.9")
                final_contracts = max_safe_qty
                final_notional = final_contracts * entry_price
                system_logger.info(f"Using maximum safe quantity as fallback: {final_contracts} contracts, notional: {final_notional}")
            
            # Step 7: Final validation
            if not symbol_info.validate_qty(final_contracts):
                raise ValueError(f"Final contracts {final_contracts} failed quantity validation")
            
            if not symbol_info.validate_notional(final_notional):
                raise ValueError(f"Final notional {final_notional} failed notional validation")
            
            # Debug information
            debug_info = {
                'wallet_balance': float(wallet_balance),
                'risk_pct': float(risk_pct),
                'channel_risk_multiplier': float(channel_risk_multiplier),
                'base_im': float(base_im),
                'final_im': float(im),
                'leverage': float(leverage),
                'entry_price': float(entry_price),
                'price_tier': price_tier,
                'conservative_multiplier': float(conservative_multiplier),
                'min_im': float(min_im),
                'final_contracts': float(final_contracts),
                'final_notional': float(final_notional),
                'min_qty': float(symbol_info.min_qty),
                'max_qty': float(symbol_info.max_qty),
                'min_notional': float(symbol_info.min_notional),
                'step_size': float(symbol_info.step_size)
            }
            
            system_logger.info(f"Position calculated for {symbol}: {final_contracts} contracts", debug_info)
            
            return final_contracts, debug_info
            
        except Exception as e:
            system_logger.error(f"Position calculation failed for {symbol}: {e}", exc_info=True)
            raise
    
    @staticmethod
    def calculate_dual_entry_qty(
        total_contracts: Decimal,
        symbol_info: SymbolInfo,
        entries_count: int = 2
    ) -> Decimal:
        """
        Calculate quantity per entry for dual entry strategy with proper per-leg quantization.
        
        Args:
            total_contracts: Total contracts to split
            symbol_info: Symbol metadata
            entries_count: Number of entries (default 2)
            
        Returns:
            Contracts per entry (properly quantized per leg)
        """
        try:
            # Split total contracts across entries
            qty_per_entry = total_contracts / entries_count
            
            # CRITICAL: Quantize each leg individually to ensure proper step size compliance
            qty_per_entry = symbol_info.quantize_qty(qty_per_entry)
            
            # Ensure each entry meets minimum quantity
            if qty_per_entry < symbol_info.min_qty:
                system_logger.warning(f"Entry qty {qty_per_entry} below min {symbol_info.min_qty}, using minimum")
                qty_per_entry = symbol_info.min_qty
            
            # Ensure total doesn't exceed maximum
            total_after_split = qty_per_entry * entries_count
            if total_after_split > symbol_info.max_qty:
                system_logger.warning(f"Total after split {total_after_split} exceeds max {symbol_info.max_qty}")
                # Reduce per-entry quantity
                qty_per_entry = symbol_info.max_qty / entries_count
                qty_per_entry = symbol_info.quantize_qty(qty_per_entry)
            
            # Calculate notional value per entry for validation
            entry_price = Decimal("1.0")  # Placeholder - will be set by caller
            notional_per_entry = qty_per_entry * entry_price
            
            system_logger.info(f"Dual entry qty: {qty_per_entry} contracts per entry (total: {qty_per_entry * entries_count}, notional per entry: {notional_per_entry} USDT)")
            
            return qty_per_entry
            
        except Exception as e:
            system_logger.error(f"Dual entry calculation failed: {e}", exc_info=True)
            raise
