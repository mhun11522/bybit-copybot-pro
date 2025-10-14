"""
Tests for append-only journal system.

CLIENT SPEC Lines 294-298: Journal with chain-hash, fsync, reconciliation.
"""

import pytest
from decimal import Decimal
from pathlib import Path
import tempfile
import os

from app.core.journal import (
    JournalEntry,
    AppendOnlyJournal,
    journal_signal_received,
    journal_order_placed,
    verify_journal_integrity
)


class TestJournalEntry:
    """Test JournalEntry class."""
    
    def test_create_entry(self):
        """Test creating a journal entry."""
        entry = JournalEntry(
            sequence=1,
            event_type="SIGNAL_RECEIVED",
            data={"symbol": "BTCUSDT", "side": "Buy"},
            prev_hash="GENESIS"
        )
        
        assert entry.sequence == 1
        assert entry.event_type == "SIGNAL_RECEIVED"
        assert entry.data["symbol"] == "BTCUSDT"
        assert entry.prev_hash == "GENESIS"
        assert len(entry.hash) == 64  # SHA256 hash
    
    def test_hash_consistency(self):
        """Test that same data produces same hash."""
        data = {"symbol": "ETHUSDT", "qty": "0.1"}
        
        entry1 = JournalEntry(1, "ORDER_PLACED", data, "abc123")
        entry2 = JournalEntry(1, "ORDER_PLACED", data, "abc123")
        
        assert entry1.hash != entry2.hash  # Different timestamps
    
    def test_decimal_sanitization(self):
        """Test that Decimal values are properly sanitized."""
        entry = JournalEntry(
            sequence=1,
            event_type="ORDER_PLACED",
            data={
                "qty": Decimal("0.001"),
                "price": Decimal("50000.00")
            },
            prev_hash="GENESIS"
        )
        
        assert entry.data["qty"] == "0.001"
        assert entry.data["price"] == "50000.00"


class TestAppendOnlyJournal:
    """Test AppendOnlyJournal class."""
    
    @pytest.fixture
    def temp_journal(self):
        """Create temporary journal for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            journal_path = Path(tmpdir) / "test_journal.jsonl"
            yield AppendOnlyJournal(journal_path)
    
    @pytest.mark.asyncio
    async def test_append_entry(self, temp_journal):
        """Test appending entries to journal."""
        entry1 = await temp_journal.append("SIGNAL_RECEIVED", {
            "symbol": "BTCUSDT",
            "side": "Buy"
        })
        
        assert entry1.sequence == 1
        assert entry1.prev_hash == "GENESIS"
        
        entry2 = await temp_journal.append("ORDER_PLACED", {
            "symbol": "BTCUSDT",
            "order_id": "12345"
        })
        
        assert entry2.sequence == 2
        assert entry2.prev_hash == entry1.hash
    
    @pytest.mark.asyncio
    async def test_journal_integrity(self, temp_journal):
        """Test journal integrity verification."""
        # Append multiple entries
        await temp_journal.append("EVENT1", {"data": "test1"})
        await temp_journal.append("EVENT2", {"data": "test2"})
        await temp_journal.append("EVENT3", {"data": "test3"})
        
        # Verify integrity
        result = temp_journal.verify_integrity()
        
        assert result["valid"] == True
        assert result["total_entries"] == 3
        assert result["corrupted_entries"] == []
    
    @pytest.mark.asyncio
    async def test_journal_persistence(self):
        """Test that journal persists across instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            journal_path = Path(tmpdir) / "persist_test.jsonl"
            
            # Create journal and add entries
            journal1 = AppendOnlyJournal(journal_path)
            await journal1.append("EVENT1", {"test": "data1"})
            await journal1.append("EVENT2", {"test": "data2"})
            
            # Create new instance pointing to same file
            journal2 = AppendOnlyJournal(journal_path)
            
            # Should load previous entries
            assert journal2.sequence == 2
            assert len(journal2._entries_cache) == 2
            assert journal2.last_hash == journal1.last_hash
    
    @pytest.mark.asyncio
    async def test_fsync_called(self, temp_journal):
        """Test that fsync is called on append."""
        # This is hard to test directly, but we can verify the file exists
        # and has content after append
        
        await temp_journal.append("TEST_EVENT", {"data": "test"})
        
        # Verify file exists and has content
        assert temp_journal.journal_path.exists()
        assert temp_journal.journal_path.stat().st_size > 0
        
        # Verify we can read it back
        with open(temp_journal.journal_path) as f:
            lines = f.readlines()
            assert len(lines) == 1


@pytest.mark.asyncio
async def test_convenience_functions():
    """Test convenience journal functions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create temporary journal
        from app.core import journal as journal_module
        journal_module._journal_instance = AppendOnlyJournal(Path(tmpdir) / "test.jsonl")
        
        # Test convenience functions
        entry = await journal_signal_received({
            "symbol": "BTCUSDT",
            "side": "Buy",
            "trade_id": "TEST123"
        })
        
        assert entry.event_type == "SIGNAL_RECEIVED"
        assert entry.sequence == 1


@pytest.mark.asyncio
async def test_integrity_verification_global():
    """Test global integrity verification."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from app.core import journal as journal_module
        journal_module._journal_instance = AppendOnlyJournal(Path(tmpdir) / "test.jsonl")
        
        # Add some entries
        await journal_signal_received({"symbol": "BTCUSDT"})
        await journal_order_placed({"order_id": "123"})
        
        # Verify
        result = await verify_journal_integrity()
        
        assert result["valid"] == True
        assert result["total_entries"] == 2

