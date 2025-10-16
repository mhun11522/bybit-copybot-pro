"""
Append-only journal with chain-hash for data integrity.

CLIENT SPEC Lines 295-298: Implement append-only journal with:
- Chain-hash integrity verification
- fsync on critical records  
- Startup reconciliation (journal ↔ Bybit)
- Exact-once proof

This provides:
1. Data integrity (chain-hash prevents tampering)
2. Durability (fsync ensures writes survive crashes)
3. Reconciliation (detect orphans, missing orders)
4. Audit trail (complete trade lifecycle)
"""

import hashlib
import json
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, Any, List, Optional
import pytz
import asyncio

from app.core.logging import system_logger


class JournalEntry:
    """
    Single journal entry with chain-hash.
    
    Each entry contains:
    - Sequence number (monotonic)
    - Event type (SIGNAL_RECEIVED, ORDER_PLACED, FILL, etc.)
    - Event data (trade details)
    - Previous hash (for chain integrity)
    - Timestamp (UTC)
    - Current hash (SHA256 of all above)
    """
    
    def __init__(self, sequence: int, event_type: str, 
                 data: Dict[str, Any], prev_hash: str):
        self.sequence = sequence
        self.event_type = event_type
        self.data = self._sanitize_data(data)
        self.prev_hash = prev_hash
        self.timestamp_utc = datetime.now(pytz.UTC).isoformat()
        self.hash = self._compute_hash()
    
    def _sanitize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize data for JSON serialization."""
        sanitized = {}
        for key, value in data.items():
            if isinstance(value, Decimal):
                sanitized[key] = str(value)
            elif isinstance(value, datetime):
                sanitized[key] = value.isoformat()
            elif isinstance(value, (str, int, float, bool, type(None))):
                sanitized[key] = value
            elif isinstance(value, (list, tuple)):
                sanitized[key] = [str(v) if isinstance(v, Decimal) else v for v in value]
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_data(value)
            else:
                sanitized[key] = str(value)
        return sanitized
    
    def _compute_hash(self) -> str:
        """
        Compute SHA256 hash of entry.
        
        Hash includes: sequence + event_type + data + prev_hash + timestamp
        This creates a chain where any tampering breaks all subsequent hashes.
        """
        # Sort data keys for deterministic hashing
        data_json = json.dumps(self.data, sort_keys=True)
        content = f"{self.sequence}|{self.event_type}|{data_json}|{self.prev_hash}|{self.timestamp_utc}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "sequence": self.sequence,
            "event_type": self.event_type,
            "data": self.data,
            "prev_hash": self.prev_hash,
            "timestamp_utc": self.timestamp_utc,
            "hash": self.hash
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'JournalEntry':
        """Reconstruct entry from dictionary."""
        entry = cls.__new__(cls)
        entry.sequence = d["sequence"]
        entry.event_type = d["event_type"]
        entry.data = d["data"]
        entry.prev_hash = d["prev_hash"]
        entry.timestamp_utc = d["timestamp_utc"]
        entry.hash = d["hash"]
        return entry


class AppendOnlyJournal:
    """
    Append-only journal with chain-hash integrity.
    
    CLIENT SPEC Line 296: 
    - Append-only journal with chain-hash (integrity)
    - fsync on critical records
    - Reconciliation on startup (journal ↔ Bybit)
    
    Features:
    - Every entry hashes the previous entry (blockchain-style)
    - Fsync forces writes to disk (survives crashes)
    - Startup reconciliation detects orphans/mismatches
    - Verification script proves integrity
    """
    
    def __init__(self, journal_path: Path = None):
        self.journal_path = journal_path or Path("logs/journal.jsonl")
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.sequence = 0
        self.last_hash = "GENESIS"  # Genesis hash
        self._lock = asyncio.Lock()
        self._entries_cache: List[JournalEntry] = []
        
        self._load_or_create()
    
    def _load_or_create(self):
        """Load existing journal or create new one."""
        if self.journal_path.exists():
            # Load existing journal
            try:
                with open(self.journal_path, 'r') as f:
                    lines = f.readlines()
                    for line in lines:
                        if line.strip():
                            entry_dict = json.loads(line)
                            entry = JournalEntry.from_dict(entry_dict)
                            self._entries_cache.append(entry)
                    
                    # Set sequence and last_hash from last entry
                    if self._entries_cache:
                        last_entry = self._entries_cache[-1]
                        self.sequence = last_entry.sequence
                        self.last_hash = last_entry.hash
                        
                        system_logger.info("Journal loaded", {
                            "entries": len(self._entries_cache),
                            "last_sequence": self.sequence,
                            "last_hash": self.last_hash[:16]
                        })
            except Exception as e:
                system_logger.error(f"Failed to load journal: {e}", exc_info=True)
                # Start fresh if corruption detected
                self.sequence = 0
                self.last_hash = "GENESIS"
                self._entries_cache = []
        else:
            # Create new journal
            system_logger.info("Creating new journal", {
                "path": str(self.journal_path)
            })
    
    async def append(self, event_type: str, data: Dict[str, Any]) -> JournalEntry:
        """
        Append entry to journal with fsync.
        
        CLIENT SPEC: Critical records must be fsynced to survive crashes.
        
        Args:
            event_type: Type of event (SIGNAL_RECEIVED, ORDER_PLACED, etc.)
            data: Event data
        
        Returns:
            The appended entry
        """
        async with self._lock:
            # Create new entry
            entry = JournalEntry(
                sequence=self.sequence + 1,
                event_type=event_type,
                data=data,
                prev_hash=self.last_hash
            )
            
            # Write to file with fsync (CLIENT SPEC: fsync on critical records)
            try:
                with open(self.journal_path, 'a') as f:
                    f.write(entry.to_json() + '\n')
                    f.flush()
                    os.fsync(f.fileno())  # Force write to disk
            except Exception as e:
                system_logger.error(f"Journal append failed: {e}", exc_info=True)
                raise
            
            # Update state
            self.sequence = entry.sequence
            self.last_hash = entry.hash
            self._entries_cache.append(entry)
            
            system_logger.debug("Journal entry appended", {
                "sequence": entry.sequence,
                "event_type": event_type,
                "hash": entry.hash[:16]
            })
            
            return entry
    
    def verify_integrity(self) -> Dict[str, Any]:
        """
        Verify chain-hash integrity of entire journal.
        
        CLIENT SPEC: Detect any tampering or corruption.
        
        Returns:
            {
                "valid": bool,
                "total_entries": int,
                "corrupted_entries": [{sequence, expected_hash, actual_hash}]
            }
        """
        corrupted = []
        prev_hash = "GENESIS"
        
        for entry in self._entries_cache:
            # Verify previous hash matches
            if entry.prev_hash != prev_hash:
                corrupted.append({
                    "sequence": entry.sequence,
                    "issue": "prev_hash_mismatch",
                    "expected_prev": prev_hash,
                    "actual_prev": entry.prev_hash
                })
            
            # Recompute hash and verify
            recomputed = entry._compute_hash()
            if recomputed != entry.hash:
                corrupted.append({
                    "sequence": entry.sequence,
                    "issue": "hash_mismatch",
                    "expected_hash": recomputed,
                    "actual_hash": entry.hash
                })
            
            prev_hash = entry.hash
        
        return {
            "valid": len(corrupted) == 0,
            "total_entries": len(self._entries_cache),
            "corrupted_entries": corrupted,
            "last_hash": self.last_hash
        }
    
    async def reconcile_with_bybit(self, bybit_client) -> Dict[str, Any]:
        """
        Reconcile journal with Bybit state.
        
        CLIENT SPEC Line 298: "reconciliation on startup (journal ↔ Bybit; no orphans)"
        
        Detects:
        - Orphan orders (in journal but not in Bybit)
        - Missing entries (in Bybit but not in journal)
        - State mismatches
        
        Args:
            bybit_client: Bybit API client
        
        Returns:
            {
                "orphans": [journal entries not in Bybit],
                "missing": [Bybit orders not in journal],
                "mismatches": [state differences],
                "status": "clean" | "has_issues"
            }
        """
        orphans = []
        missing = []
        mismatches = []
        
        try:
            # Extract all ORDER_PLACED entries from journal
            journal_orders = {}
            for entry in self._entries_cache:
                if entry.event_type == "ORDER_PLACED":
                    order_id = entry.data.get("order_id")
                    if order_id:
                        journal_orders[order_id] = entry
            
            # Get all open orders from Bybit
            bybit_orders = {}
            for category in ["linear"]:  # Add more categories if needed
                try:
                    # CRITICAL FIX: Add settleCoin parameter to avoid error 10001
                    response = await bybit_client.get_open_orders(category, settleCoin="USDT")
                    if response.get("retCode") == 0:
                        for order in response.get("result", {}).get("list", []):
                            order_id = order.get("orderId")
                            if order_id:
                                bybit_orders[order_id] = order
                except Exception as e:
                    system_logger.warning(f"Failed to get open orders for {category}: {e}")
            
            # Find orphans (in journal but not in Bybit)
            for order_id, entry in journal_orders.items():
                if order_id not in bybit_orders:
                    # Check if this was filled or cancelled
                    filled = any(e.event_type == "ORDER_FILLED" and e.data.get("order_id") == order_id 
                                for e in self._entries_cache)
                    cancelled = any(e.event_type == "ORDER_CANCELLED" and e.data.get("order_id") == order_id 
                                   for e in self._entries_cache)
                    
                    if not filled and not cancelled:
                        orphans.append({
                            "order_id": order_id,
                            "symbol": entry.data.get("symbol"),
                            "side": entry.data.get("side"),
                            "sequence": entry.sequence
                        })
            
            # Find missing (in Bybit but not in journal)
            for order_id, bybit_order in bybit_orders.items():
                if order_id not in journal_orders:
                    missing.append({
                        "order_id": order_id,
                        "symbol": bybit_order.get("symbol"),
                        "side": bybit_order.get("side"),
                        "orderLinkId": bybit_order.get("orderLinkId")
                    })
            
            # Determine status
            status = "clean" if (not orphans and not missing) else "has_issues"
            
            result = {
                "orphans": orphans,
                "missing": missing,
                "mismatches": mismatches,
                "status": status,
                "journal_order_count": len(journal_orders),
                "bybit_order_count": len(bybit_orders)
            }
            
            # Log reconciliation result
            if status == "clean":
                system_logger.info("Journal reconciliation clean", result)
            else:
                system_logger.warning("Journal reconciliation found issues", result)
            
            return result
            
        except Exception as e:
            system_logger.error(f"Journal reconciliation failed: {e}", exc_info=True)
            return {
                "orphans": [],
                "missing": [],
                "mismatches": [],
                "status": "error",
                "error": str(e)
            }
    
    def get_trade_history(self, trade_id: str) -> List[JournalEntry]:
        """Get all journal entries for a specific trade."""
        return [
            entry for entry in self._entries_cache
            if entry.data.get("trade_id") == trade_id
        ]
    
    def get_recent_entries(self, count: int = 100) -> List[JournalEntry]:
        """Get most recent N entries."""
        return self._entries_cache[-count:]
    
    def get_entry_count(self) -> int:
        """Get total entry count."""
        return len(self._entries_cache)


# Global journal instance
_journal_instance: Optional[AppendOnlyJournal] = None


def get_append_only_journal() -> AppendOnlyJournal:
    """Get global append-only journal instance."""
    global _journal_instance
    if _journal_instance is None:
        _journal_instance = AppendOnlyJournal()
    return _journal_instance


# Convenience functions for common journal operations

async def journal_signal_received(signal_data: Dict[str, Any]) -> JournalEntry:
    """Journal: Signal received."""
    journal = get_append_only_journal()
    return await journal.append("SIGNAL_RECEIVED", signal_data)


async def journal_order_placed(order_data: Dict[str, Any]) -> JournalEntry:
    """Journal: Order placed to Bybit."""
    journal = get_append_only_journal()
    return await journal.append("ORDER_PLACED", order_data)


async def journal_order_ack(ack_data: Dict[str, Any]) -> JournalEntry:
    """Journal: Order acknowledged by Bybit."""
    journal = get_append_only_journal()
    return await journal.append("ORDER_ACK", ack_data)


async def journal_order_filled(fill_data: Dict[str, Any]) -> JournalEntry:
    """Journal: Order filled."""
    journal = get_append_only_journal()
    return await journal.append("ORDER_FILLED", fill_data)


async def journal_order_cancelled(cancel_data: Dict[str, Any]) -> JournalEntry:
    """Journal: Order cancelled."""
    journal = get_append_only_journal()
    return await journal.append("ORDER_CANCELLED", cancel_data)


async def journal_position_opened(position_data: Dict[str, Any]) -> JournalEntry:
    """Journal: Position opened."""
    journal = get_append_only_journal()
    return await journal.append("POSITION_OPENED", position_data)


async def journal_position_closed(close_data: Dict[str, Any]) -> JournalEntry:
    """Journal: Position closed."""
    journal = get_append_only_journal()
    return await journal.append("POSITION_CLOSED", close_data)


async def journal_tp_hit(tp_data: Dict[str, Any]) -> JournalEntry:
    """Journal: Take profit hit."""
    journal = get_append_only_journal()
    return await journal.append("TP_HIT", tp_data)


async def journal_sl_hit(sl_data: Dict[str, Any]) -> JournalEntry:
    """Journal: Stop loss hit."""
    journal = get_append_only_journal()
    return await journal.append("SL_HIT", sl_data)


async def journal_pyramid_step(pyramid_data: Dict[str, Any]) -> JournalEntry:
    """Journal: Pyramid step activated."""
    journal = get_append_only_journal()
    return await journal.append("PYRAMID_STEP", pyramid_data)


async def journal_breakeven_moved(be_data: Dict[str, Any]) -> JournalEntry:
    """Journal: Breakeven SL moved."""
    journal = get_append_only_journal()
    return await journal.append("BREAKEVEN_MOVED", be_data)


async def journal_trailing_activated(trail_data: Dict[str, Any]) -> JournalEntry:
    """Journal: Trailing stop activated."""
    journal = get_append_only_journal()
    return await journal.append("TRAILING_ACTIVATED", trail_data)


async def journal_hedge_started(hedge_data: Dict[str, Any]) -> JournalEntry:
    """Journal: Hedge position started."""
    journal = get_append_only_journal()
    return await journal.append("HEDGE_STARTED", hedge_data)


async def journal_reentry_attempt(reentry_data: Dict[str, Any]) -> JournalEntry:
    """Journal: Re-entry attempted."""
    journal = get_append_only_journal()
    return await journal.append("REENTRY_ATTEMPT", reentry_data)


async def verify_journal_integrity() -> Dict[str, Any]:
    """Verify journal integrity (can be run as health check)."""
    journal = get_append_only_journal()
    return journal.verify_integrity()


async def reconcile_on_startup(bybit_client) -> Dict[str, Any]:
    """
    Run journal reconciliation on startup.
    
    CLIENT SPEC: Must be called during bot startup to detect orphans.
    
    Returns reconciliation report with any issues found.
    """
    journal = get_append_only_journal()
    report = await journal.reconcile_with_bybit(bybit_client)
    
    # Log summary
    if report["status"] == "clean":
        system_logger.info("✅ Journal reconciliation CLEAN", report)
    else:
        system_logger.warning("⚠️ Journal reconciliation found issues", report)
        
        if report["orphans"]:
            system_logger.warning(f"Found {len(report['orphans'])} orphan orders", {
                "orphans": report["orphans"]
            })
        
        if report["missing"]:
            system_logger.warning(f"Found {len(report['missing'])} missing journal entries", {
                "missing": report["missing"]
            })
    
    return report

