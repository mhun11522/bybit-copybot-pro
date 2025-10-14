"""
Tests for timeline logger (ACK-Gate compliance proof).

CLIENT SPEC Line 293: Timeline logs prove Telegram after Bybit ack.
"""

import pytest
from pathlib import Path
import tempfile

from app.core.timeline_logger import (
    TimelineEvent,
    TimelineLogger,
    get_timeline_logger,
    verify_ack_gate_compliance
)


class TestTimelineEvent:
    """Test TimelineEvent class."""
    
    def test_create_event(self):
        """Test creating a timeline event."""
        event = TimelineEvent(
            operation_id="test_op_123",
            event_type="BYBIT_REQUEST",
            data={"symbol": "BTCUSDT", "side": "Buy"}
        )
        
        assert event.operation_id == "test_op_123"
        assert event.event_type == "BYBIT_REQUEST"
        assert event.data["symbol"] == "BTCUSDT"
        assert event.timestamp_utc is not None
    
    def test_to_dict(self):
        """Test converting event to dictionary."""
        event = TimelineEvent("op1", "TEST", {"key": "value"})
        d = event.to_dict()
        
        assert d["operation_id"] == "op1"
        assert d["event_type"] == "TEST"
        assert d["data"] == {"key": "value"}
        assert "timestamp_utc" in d


class TestTimelineLogger:
    """Test TimelineLogger class."""
    
    @pytest.fixture
    def temp_logger(self):
        """Create temporary timeline logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            timeline_file = Path(tmpdir) / "timeline.jsonl"
            yield TimelineLogger(timeline_file)
    
    @pytest.mark.asyncio
    async def test_log_bybit_request(self, temp_logger):
        """Test logging Bybit request."""
        await temp_logger.log_bybit_request(
            "op1",
            "place_order",
            {"symbol": "BTCUSDT", "side": "Buy", "qty": "0.001"}
        )
        
        assert "op1" in temp_logger._events
        assert len(temp_logger._events["op1"]) == 1
        assert temp_logger._events["op1"][0].event_type == "BYBIT_REQUEST"
    
    @pytest.mark.asyncio
    async def test_log_bybit_ack(self, temp_logger):
        """Test logging Bybit acknowledgment."""
        await temp_logger.log_bybit_ack(
            "op1",
            0,  # retCode
            {"retMsg": "OK", "result": {"orderId": "12345"}}
        )
        
        assert "op1" in temp_logger._events
        events = temp_logger._events["op1"]
        assert events[0].event_type == "BYBIT_ACK"
        assert events[0].data["retCode"] == 0
    
    @pytest.mark.asyncio
    async def test_log_telegram_send(self, temp_logger):
        """Test logging Telegram send."""
        await temp_logger.log_telegram_send(
            "op1",
            987654,  # message_id
            "ORDER_PLACED",
            "BTCUSDT"
        )
        
        events = temp_logger._events["op1"]
        assert events[0].event_type == "TELEGRAM_SEND"
        assert events[0].data["message_id"] == 987654
    
    @pytest.mark.asyncio
    async def test_verify_correct_sequence(self, temp_logger):
        """Test verification of correct sequence: REQUEST → ACK → TELEGRAM."""
        # Log events in correct order
        await temp_logger.log_bybit_request("op1", "place_order", {"symbol": "BTCUSDT"})
        await temp_logger.log_bybit_ack("op1", 0, {"retMsg": "OK"})
        await temp_logger.log_telegram_send("op1", 123, "ORDER_PLACED", "BTCUSDT")
        
        # Verify sequence
        result = await temp_logger.verify_sequence("op1")
        
        assert result["valid"] == True
        assert result["sequence"] == ["BYBIT_REQUEST", "BYBIT_ACK", "TELEGRAM_SEND"]
        assert result["violations"] == []
    
    @pytest.mark.asyncio
    async def test_verify_wrong_sequence(self, temp_logger):
        """Test detection of wrong sequence (Telegram before Bybit)."""
        # Log events in WRONG order (Telegram before Bybit ack)
        await temp_logger.log_bybit_request("op2", "place_order", {"symbol": "ETHUSDT"})
        await temp_logger.log_telegram_send("op2", 456, "ORDER_PLACED", "ETHUSDT")
        await temp_logger.log_bybit_ack("op2", 0, {"retMsg": "OK"})
        
        # Verify sequence
        result = await temp_logger.verify_sequence("op2")
        
        assert result["valid"] == False
        assert len(result["violations"]) > 0
    
    @pytest.mark.asyncio
    async def test_verify_telegram_without_success(self, temp_logger):
        """Test detection of Telegram sent despite Bybit failure."""
        # Log Bybit failure but Telegram still sent (violation!)
        await temp_logger.log_bybit_request("op3", "place_order", {"symbol": "BTCUSDT"})
        await temp_logger.log_bybit_ack("op3", -1, {"retMsg": "Error"})  # retCode=-1 (failure)
        await temp_logger.log_telegram_send("op3", 789, "ORDER_PLACED", "BTCUSDT")
        
        # Verify sequence
        result = await temp_logger.verify_sequence("op3")
        
        assert result["valid"] == False
        assert any("Bybit failure" in v for v in result["violations"])
    
    @pytest.mark.asyncio
    async def test_compliance_report(self, temp_logger):
        """Test generating compliance report."""
        # Add correct sequence
        await temp_logger.log_bybit_request("op1", "order", {})
        await temp_logger.log_bybit_ack("op1", 0, {})
        await temp_logger.log_telegram_send("op1", 1, "TEMPLATE", "BTCUSDT")
        
        # Add incorrect sequence
        await temp_logger.log_bybit_request("op2", "order", {})
        await temp_logger.log_telegram_send("op2", 2, "TEMPLATE", "ETHUSDT")
        await temp_logger.log_bybit_ack("op2", 0, {})
        
        # Generate report
        report = await temp_logger.generate_compliance_report()
        
        assert report["total_operations"] == 2
        assert report["valid_sequences"] == 1
        assert len(report["violations"]) == 1
        assert report["compliance_rate"] == 50.0
        assert report["status"] == "FAIL"


@pytest.mark.asyncio
async def test_timeline_file_persistence():
    """Test that timeline is written to file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        timeline_file = Path(tmpdir) / "timeline_test.jsonl"
        logger = TimelineLogger(timeline_file)
        
        # Log an event
        await logger.log_bybit_request("op1", "test", {"data": "test"})
        
        # Verify file exists and has content
        assert timeline_file.exists()
        
        with open(timeline_file) as f:
            lines = f.readlines()
            assert len(lines) == 1
            assert "BYBIT_REQUEST" in lines[0]

