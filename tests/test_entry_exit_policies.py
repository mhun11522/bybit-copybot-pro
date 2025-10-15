"""
Unit tests for entry and exit order policies.

Tests CLIENT SPEC compliance for:
- Dual entry orders (50/50 split, Post-Only)
- Exit orders (reduce-only enforcement)
- original_entry_price immutability
"""

import pytest
from decimal import Decimal
from app.core.entry_order_policy import (
    EntryOrderPolicy,
    DualEntryConfig,
    create_dual_entry_orders
)
from app.core.exit_order_policy import (
    ExitOrderPolicy,
    ExitOrderConfig,
    TriggerSource,
    ExitOrderValidator,
    create_take_profit_order,
    create_stop_loss_order
)
from app.core.trade_state_v2 import (
    TradeStateV2,
    TradeStatus,
    TradeStateManager,
    get_trade_state_manager
)
from app.core.symbol_registry import SymbolInfo


class MockSymbolInfo:
    """Mock SymbolInfo for testing."""
    
    def __init__(self):
        self.min_qty = Decimal("1")
        self.max_qty = Decimal("100000")
        self.step_size = Decimal("1")
        self.tick_size = Decimal("0.01")
        self.min_notional = Decimal("5")
    
    def quantize_qty(self, qty: Decimal) -> Decimal:
        """Quantize quantity to step size."""
        return (qty // self.step_size) * self.step_size
    
    def quantize_price(self, price: Decimal) -> Decimal:
        """Quantize price to tick size."""
        return (price // self.tick_size) * self.tick_size
    
    def validate_qty(self, qty: Decimal) -> bool:
        """Validate quantity."""
        return self.min_qty <= qty <= self.max_qty
    
    def validate_notional(self, notional: Decimal) -> bool:
        """Validate notional."""
        return notional >= self.min_notional


class TestEntryOrderPolicy:
    """Test entry order policy compliance."""
    
    def test_create_dual_entry_orders_with_single_price(self):
        """Test creating two orders from single price."""
        policy = EntryOrderPolicy()
        symbol_info = MockSymbolInfo()
        
        orders = policy.create_dual_entry_orders(
            symbol="BTCUSDT",
            direction="LONG",
            total_qty=Decimal("100"),
            entry_prices=[Decimal("50000")],
            symbol_info=symbol_info,
            order_link_id_prefix="test123"
        )
        
        # Should create two orders
        assert len(orders) == 2
        
        # Check first order
        order1 = orders[0]
        assert order1["symbol"] == "BTCUSDT"
        assert order1["side"] == "Buy"
        assert order1["orderType"] == "Limit"
        assert order1["timeInForce"] == "PostOnly"
        assert order1["reduceOnly"] is False
        assert order1["orderLinkId"] == "test123_entry1"
        
        # Check second order
        order2 = orders[1]
        assert order2["symbol"] == "BTCUSDT"
        assert order2["side"] == "Buy"
        assert order2["timeInForce"] == "PostOnly"
        assert order2["reduceOnly"] is False
        assert order2["orderLinkId"] == "test123_entry2"
        
        # Check quantities (50/50 split)
        qty1 = Decimal(order1["qty"])
        qty2 = Decimal(order2["qty"])
        assert qty1 == Decimal("50")
        assert qty2 == Decimal("50")
        
        # Check prices are different (offset applied)
        price1 = Decimal(order1["price"])
        price2 = Decimal(order2["price"])
        assert price1 != price2
    
    def test_create_dual_entry_orders_with_two_prices(self):
        """Test creating two orders from two prices."""
        policy = EntryOrderPolicy()
        symbol_info = MockSymbolInfo()
        
        orders = policy.create_dual_entry_orders(
            symbol="ETHUSDT",
            direction="SHORT",
            total_qty=Decimal("200"),
            entry_prices=[Decimal("3000"), Decimal("3010")],
            symbol_info=symbol_info,
            order_link_id_prefix="test456"
        )
        
        assert len(orders) == 2
        
        # Check side for SHORT
        assert orders[0]["side"] == "Sell"
        assert orders[1]["side"] == "Sell"
        
        # Check prices match input
        assert Decimal(orders[0]["price"]) == Decimal("3000.00")
        assert Decimal(orders[1]["price"]) == Decimal("3010.00")
    
    def test_entry_order_post_only_enforcement(self):
        """Test that Post-Only is enforced."""
        policy = EntryOrderPolicy()
        symbol_info = MockSymbolInfo()
        
        orders = policy.create_dual_entry_orders(
            symbol="DOGEUSDT",
            direction="LONG",
            total_qty=Decimal("1000"),
            entry_prices=[Decimal("0.10")],
            symbol_info=symbol_info,
            order_link_id_prefix="doge"
        )
        
        # Both orders must have Post-Only
        for order in orders:
            assert order["timeInForce"] == "PostOnly"
    
    def test_entry_order_reduce_only_forbidden(self):
        """Test that reduceOnly is always False for entries."""
        policy = EntryOrderPolicy()
        symbol_info = MockSymbolInfo()
        
        orders = policy.create_dual_entry_orders(
            symbol="SOLUSDT",
            direction="LONG",
            total_qty=Decimal("50"),
            entry_prices=[Decimal("100")],
            symbol_info=symbol_info,
            order_link_id_prefix="sol"
        )
        
        # Both orders must have reduceOnly=False
        for order in orders:
            assert order["reduceOnly"] is False
    
    def test_invalid_direction_raises_error(self):
        """Test that invalid direction raises error."""
        policy = EntryOrderPolicy()
        symbol_info = MockSymbolInfo()
        
        with pytest.raises(ValueError, match="Invalid direction"):
            policy.create_dual_entry_orders(
                symbol="BTCUSDT",
                direction="INVALID",
                total_qty=Decimal("100"),
                entry_prices=[Decimal("50000")],
                symbol_info=symbol_info,
                order_link_id_prefix="test"
            )
    
    def test_zero_quantity_raises_error(self):
        """Test that zero quantity raises error."""
        policy = EntryOrderPolicy()
        symbol_info = MockSymbolInfo()
        
        with pytest.raises(ValueError, match="Total quantity must be positive"):
            policy.create_dual_entry_orders(
                symbol="BTCUSDT",
                direction="LONG",
                total_qty=Decimal("0"),
                entry_prices=[Decimal("50000")],
                symbol_info=symbol_info,
                order_link_id_prefix="test"
            )


class TestExitOrderPolicy:
    """Test exit order policy compliance."""
    
    def test_create_take_profit_order(self):
        """Test TP order creation."""
        policy = ExitOrderPolicy()
        
        order = policy.create_take_profit_order(
            symbol="BTCUSDT",
            side="Sell",
            qty=Decimal("10"),
            price=Decimal("52000"),
            order_link_id="tp1"
        )
        
        # Check required fields
        assert order["symbol"] == "BTCUSDT"
        assert order["side"] == "Sell"
        assert order["orderType"] == "Limit"
        assert order["qty"] == "10"
        assert order["price"] == "52000"
        assert order["reduceOnly"] is True  # CRITICAL
        assert order["timeInForce"] == "GTC"
        assert order["orderLinkId"] == "tp1"
    
    def test_create_stop_loss_order(self):
        """Test SL order creation."""
        policy = ExitOrderPolicy()
        
        order = policy.create_stop_loss_order(
            symbol="ETHUSDT",
            side="Buy",
            qty=Decimal("5"),
            trigger_price=Decimal("2900"),
            order_link_id="sl1"
        )
        
        # Check required fields
        assert order["symbol"] == "ETHUSDT"
        assert order["side"] == "Buy"
        assert order["orderType"] == "Market"
        assert order["qty"] == "5"
        assert order["triggerPrice"] == "2900"
        assert order["reduceOnly"] is True  # CRITICAL
        assert order["closeOnTrigger"] is True
        assert order["orderLinkId"] == "sl1"
        
        # Check trigger source
        assert order["triggerBy"] in ["LastPrice", "IndexPrice", "MarkPrice"]
    
    def test_exit_order_reduce_only_enforcement(self):
        """Test that reduceOnly=True is enforced for exits."""
        policy = ExitOrderPolicy()
        
        # TP order
        tp_order = policy.create_take_profit_order(
            symbol="BTCUSDT",
            side="Sell",
            qty=Decimal("10"),
            price=Decimal("52000"),
            order_link_id="tp1"
        )
        assert tp_order["reduceOnly"] is True
        
        # SL order
        sl_order = policy.create_stop_loss_order(
            symbol="BTCUSDT",
            side="Buy",
            qty=Decimal("10"),
            trigger_price=Decimal("48000"),
            order_link_id="sl1"
        )
        assert sl_order["reduceOnly"] is True
    
    def test_validate_order_flags_for_entry(self):
        """Test validation of entry order flags."""
        policy = ExitOrderPolicy()
        
        # Valid entry order
        valid_entry = {
            "symbol": "BTCUSDT",
            "reduceOnly": False
        }
        result = policy.validate_order_flags(valid_entry, is_exit=False)
        assert result["valid"] is True
        
        # Invalid entry order (has reduceOnly=True)
        invalid_entry = {
            "symbol": "BTCUSDT",
            "reduceOnly": True
        }
        with pytest.raises(ValueError, match="CLIENT SPEC VIOLATION"):
            policy.validate_order_flags(invalid_entry, is_exit=False)
    
    def test_validate_order_flags_for_exit(self):
        """Test validation of exit order flags."""
        policy = ExitOrderPolicy()
        
        # Valid exit order
        valid_exit = {
            "symbol": "BTCUSDT",
            "reduceOnly": True
        }
        result = policy.validate_order_flags(valid_exit, is_exit=True)
        assert result["valid"] is True
        
        # Invalid exit order (missing reduceOnly)
        invalid_exit = {
            "symbol": "BTCUSDT",
            "reduceOnly": False
        }
        with pytest.raises(ValueError, match="CLIENT SPEC VIOLATION"):
            policy.validate_order_flags(invalid_exit, is_exit=True)
    
    def test_trigger_source_consistency(self):
        """Test that trigger source is consistent."""
        config = ExitOrderConfig(trigger_source=TriggerSource.MARK_PRICE)
        policy = ExitOrderPolicy(config)
        
        # Create two SL orders
        sl1 = policy.create_stop_loss_order(
            symbol="BTCUSDT",
            side="Buy",
            qty=Decimal("10"),
            trigger_price=Decimal("48000"),
            order_link_id="sl1"
        )
        
        sl2 = policy.create_stop_loss_order(
            symbol="ETHUSDT",
            side="Sell",
            qty=Decimal("5"),
            trigger_price=Decimal("3100"),
            order_link_id="sl2"
        )
        
        # Both should use same trigger source
        assert sl1["triggerBy"] == "MarkPrice"
        assert sl2["triggerBy"] == "MarkPrice"


class TestExitOrderValidator:
    """Test exit order validator."""
    
    def test_validate_reduce_only_flag_for_entry(self):
        """Test reduce-only validation for entry orders."""
        # Valid entry
        valid_entry = {"reduceOnly": False, "orderLinkId": "entry1"}
        assert ExitOrderValidator.validate_reduce_only_flag(valid_entry, is_exit=False)
        
        # Invalid entry
        invalid_entry = {"reduceOnly": True, "orderLinkId": "entry1"}
        assert not ExitOrderValidator.validate_reduce_only_flag(invalid_entry, is_exit=False)
    
    def test_validate_reduce_only_flag_for_exit(self):
        """Test reduce-only validation for exit orders."""
        # Valid exit
        valid_exit = {"reduceOnly": True, "orderLinkId": "tp1"}
        assert ExitOrderValidator.validate_reduce_only_flag(valid_exit, is_exit=True)
        
        # Invalid exit
        invalid_exit = {"reduceOnly": False, "orderLinkId": "tp1"}
        assert not ExitOrderValidator.validate_reduce_only_flag(invalid_exit, is_exit=True)
    
    def test_scan_order_body_for_violations(self):
        """Test scanning multiple orders for violations."""
        orders = [
            {"orderLinkId": "entry1", "reduceOnly": False},  # Valid entry
            {"orderLinkId": "tp1", "reduceOnly": True},  # Valid TP
            {"orderLinkId": "entry2", "reduceOnly": True},  # INVALID entry
            {"orderLinkId": "sl1", "reduceOnly": False},  # INVALID SL
        ]
        
        violations = ExitOrderValidator.scan_order_body_for_violations(orders)
        
        # Should find 2 violations
        assert len(violations) == 2
        
        # Check violation details
        assert violations[0]["order_link_id"] == "entry2"
        assert "FORBIDDEN" in violations[0]["violation"]
        
        assert violations[1]["order_link_id"] == "sl1"
        assert "missing reduceOnly" in violations[1]["violation"]


class TestTradeStateV2:
    """Test enhanced trade state with original_entry_price."""
    
    def test_set_original_entry_price_once(self):
        """Test that original_entry_price can only be set once."""
        state = TradeStateV2(
            trade_id="test123",
            symbol="BTCUSDT",
            direction="LONG"
        )
        
        # First set should work
        state.set_original_entry_price(Decimal("50000"))
        assert state.original_entry_price == Decimal("50000")
        assert state._original_entry_locked is True
        
        # Second set should raise error
        with pytest.raises(ValueError, match="IMMUTABLE"):
            state.set_original_entry_price(Decimal("51000"))
    
    def test_calculate_pnl_from_original_entry_long(self):
        """Test PnL calculation from original entry for LONG."""
        state = TradeStateV2(
            trade_id="test123",
            symbol="BTCUSDT",
            direction="LONG",
            leverage=Decimal("10"),
            initial_margin=Decimal("100")
        )
        
        state.set_original_entry_price(Decimal("50000"))
        
        # Calculate PnL at 52000 (4% gain)
        pnl = state.calculate_pnl_from_original_entry(Decimal("52000"))
        
        assert pnl["pnl_pct"] == Decimal("4")  # 4% price gain
        assert pnl["pnl_pct_leveraged"] == Decimal("40")  # 40% with 10x leverage
        assert pnl["pnl_usdt"] == Decimal("40")  # 40 USDT profit
    
    def test_calculate_pnl_from_original_entry_short(self):
        """Test PnL calculation from original entry for SHORT."""
        state = TradeStateV2(
            trade_id="test456",
            symbol="ETHUSDT",
            direction="SHORT",
            leverage=Decimal("5"),
            initial_margin=Decimal("200")
        )
        
        state.set_original_entry_price(Decimal("3000"))
        
        # Calculate PnL at 2900 (3.33% gain)
        pnl = state.calculate_pnl_from_original_entry(Decimal("2900"))
        
        # 3.33% price movement * 5x leverage = 16.65% leveraged
        # 200 USDT * 16.65% = ~33.3 USDT
        assert pnl["pnl_pct"] > Decimal("3")
        assert pnl["pnl_pct"] < Decimal("4")
        assert pnl["pnl_pct_leveraged"] > Decimal("16")
        assert pnl["pnl_usdt"] > Decimal("30")
    
    def test_calculate_target_price_from_original_long(self):
        """Test target price calculation for LONG."""
        state = TradeStateV2(
            trade_id="test123",
            symbol="BTCUSDT",
            direction="LONG"
        )
        
        state.set_original_entry_price(Decimal("50000"))
        
        # Calculate TP at +2.3%
        tp_price = state.calculate_target_price_from_original(Decimal("2.3"))
        expected = Decimal("50000") * Decimal("1.023")
        assert tp_price == expected
    
    def test_calculate_target_price_from_original_short(self):
        """Test target price calculation for SHORT."""
        state = TradeStateV2(
            trade_id="test456",
            symbol="ETHUSDT",
            direction="SHORT"
        )
        
        state.set_original_entry_price(Decimal("3000"))
        
        # Calculate TP at +2.3%
        tp_price = state.calculate_target_price_from_original(Decimal("2.3"))
        expected = Decimal("3000") * Decimal("0.977")
        assert tp_price == expected
    
    def test_update_avg_entry_price_does_not_affect_original(self):
        """Test that updating avg_entry_price doesn't affect original."""
        state = TradeStateV2(
            trade_id="test123",
            symbol="BTCUSDT",
            direction="LONG"
        )
        
        # Set original entry
        state.set_original_entry_price(Decimal("50000"))
        original = state.original_entry_price
        
        # Update avg_entry_price (simulating pyramid)
        state.update_avg_entry_price(Decimal("51000"), Decimal("10"))
        
        # Original should be unchanged
        assert state.original_entry_price == original
        assert state.avg_entry_price != original
    
    def test_get_current_gain_pct_from_original(self):
        """Test current gain percentage calculation."""
        state = TradeStateV2(
            trade_id="test123",
            symbol="BTCUSDT",
            direction="LONG"
        )
        
        state.set_original_entry_price(Decimal("50000"))
        
        # Test various prices
        gain_at_51000 = state.get_current_gain_pct_from_original(Decimal("51000"))
        assert gain_at_51000 == Decimal("2")  # 2% gain
        
        gain_at_49000 = state.get_current_gain_pct_from_original(Decimal("49000"))
        assert gain_at_49000 == Decimal("-2")  # 2% loss


class TestTradeStateManager:
    """Test trade state manager."""
    
    def test_create_and_get_state(self):
        """Test creating and retrieving trade state."""
        manager = TradeStateManager()
        
        state = manager.create_trade_state(
            trade_id="test123",
            symbol="BTCUSDT",
            direction="LONG",
            leverage=Decimal("10"),
            initial_margin=Decimal("100"),
            signal_data={"mode": "SWING"},
            channel_name="CRYPTORAKETEN"
        )
        
        # Should be able to retrieve it
        retrieved = manager.get_state("test123")
        assert retrieved is not None
        assert retrieved.trade_id == "test123"
        assert retrieved.symbol == "BTCUSDT"
    
    def test_duplicate_trade_id_raises_error(self):
        """Test that duplicate trade ID raises error."""
        manager = TradeStateManager()
        
        manager.create_trade_state(
            trade_id="test123",
            symbol="BTCUSDT",
            direction="LONG",
            leverage=Decimal("10"),
            initial_margin=Decimal("100"),
            signal_data={},
            channel_name="TEST"
        )
        
        # Second create with same ID should fail
        with pytest.raises(ValueError, match="already exists"):
            manager.create_trade_state(
                trade_id="test123",
                symbol="ETHUSDT",
                direction="SHORT",
                leverage=Decimal("5"),
                initial_margin=Decimal("50"),
                signal_data={},
                channel_name="TEST"
            )
    
    def test_get_states_by_symbol(self):
        """Test getting states by symbol."""
        manager = TradeStateManager()
        
        # Create multiple states
        manager.create_trade_state(
            trade_id="btc1",
            symbol="BTCUSDT",
            direction="LONG",
            leverage=Decimal("10"),
            initial_margin=Decimal("100"),
            signal_data={},
            channel_name="TEST"
        )
        
        manager.create_trade_state(
            trade_id="eth1",
            symbol="ETHUSDT",
            direction="SHORT",
            leverage=Decimal("5"),
            initial_margin=Decimal("50"),
            signal_data={},
            channel_name="TEST"
        )
        
        manager.create_trade_state(
            trade_id="btc2",
            symbol="BTCUSDT",
            direction="SHORT",
            leverage=Decimal("8"),
            initial_margin=Decimal("80"),
            signal_data={},
            channel_name="TEST"
        )
        
        # Get BTC states
        btc_states = manager.get_states_by_symbol("BTCUSDT")
        assert len(btc_states) == 2
        
        # Get ETH states
        eth_states = manager.get_states_by_symbol("ETHUSDT")
        assert len(eth_states) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

