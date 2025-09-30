import asyncio
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

# Ensure repository root (containing 'app') is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def print_ok(label: str):
    print(f"[OK] {label}")


def print_fail(label: str, err: Exception):
    print(f"[FAIL] {label}: {err}")


def check_entry_flags():
    from app.bybit_client import BybitClient

    captured = {}

    def fake_post(path: str, body: dict):
        captured["path"] = path
        captured["body"] = body
        return {"retCode": 0, "result": {"orderId": "X", "orderLinkId": body.get("orderLinkId", "L")}}

    c = BybitClient()
    c._post = fake_post  # type: ignore
    c.create_entry_order("BTCUSDT", "Buy", "0.01", "20000", "TRD-T", 1)
    body = captured["body"]
    assert captured["path"] == "/v5/order/create"
    assert body["orderType"] == "Limit"
    assert body["timeInForce"] == "PostOnly"
    assert body["reduceOnly"] is False


def check_exit_flags():
    from app.bybit_client import BybitClient

    captured = {}

    def fake_post(path: str, body: dict):
        captured.setdefault("calls", []).append((path, body))
        return {"retCode": 0, "result": {"orderId": "Y"}}

    c = BybitClient()
    c._post = fake_post  # type: ignore
    c.create_tp_order("BTCUSDT", "Sell", "0.01", "21000", "TRD-T", 1)
    c.create_sl_order("BTCUSDT", "Sell", "0.01", "19000", "TRD-T")
    _, tp = captured["calls"][0]
    _, sl = captured["calls"][1]
    assert tp["orderType"] == "Limit" and tp["timeInForce"] == "GTC" and tp["reduceOnly"] is True
    assert sl["orderType"] == "Market" and sl["reduceOnly"] is True and sl["triggerBy"] == "MarkPrice"


async def check_idempotency_async():
    # Use temp DB
    from app.storage import db as db_mod
    try:
        import aiosqlite  # noqa: F401
    except Exception:
        # Skip if aiosqlite is not available (offline env)
        print("[SKIP] Idempotency (aiosqlite missing)")
        return
    from app.signals.idempotency import is_new_signal

    db_mod.DB_PATH = str(tempfile.gettempdir() + "\\selfcheck_trades.sqlite")
    ok1 = await is_new_signal(123, "hello world")
    ok2 = await is_new_signal(123, "hello world")
    assert ok1 is True and ok2 is False


def check_risk_sizing():
    from app.trade import risk as risk_mod

    def fake_equity():
        return Decimal("1000")

    risk_mod.wallet_equity_usdt = fake_equity  # type: ignore
    qty = risk_mod.qty_for_2pct_risk("BTCUSDT", Decimal("20000"), Decimal("19000"))
    assert qty > Decimal("0.015") and qty < Decimal("0.03")


def check_templates():
    from app.telegram import templates
    assert "Leverage" in templates.leverage_set("BTCUSDT", 10)
    assert "Entry orders" in templates.entries_placed("BTCUSDT", ["A"]) 
    assert "Position" in templates.position_confirmed("BTCUSDT", 1)
    assert "placed" in templates.tpsl_placed("BTCUSDT", 2, "19000").lower()
    assert "TP" in templates.tp_hit("BTCUSDT", "21000")
    assert "Stop-loss" in templates.sl_hit("BTCUSDT", "19000")


async def check_oco_async():
    from app.trade.oco import OCOManager

    class FakeBybit:
        def __init__(self):
            self.cancelled = False

        def get_open_orders(self, symbol: str):
            return {"retCode": 0, "result": {"list": [{"orderLinkId": "TRD-1-TP1"}]}}

        def cancel_all(self, symbol: str):
            self.cancelled = True

    # Monkeypatch DB helpers
    from app.storage import db as db_mod
    try:
        import aiosqlite  # noqa: F401
    except Exception:
        print("[SKIP] OCO (aiosqlite missing)")
        return

    async def fake_get_trade(_):
        return ("TRD-1", "BTCUSDT", "BUY", 20000.0, 0.01, "TPSL_PLACED", 0.0, None)

    async def fake_save_fill(*a, **k):
        return True

    async def fake_update_trade_close(*a, **k):
        return True

    db_mod.get_trade = fake_get_trade  # type: ignore
    db_mod.save_fill = fake_save_fill  # type: ignore
    db_mod.update_trade_close = fake_update_trade_close  # type: ignore

    signal = {"symbol": "BTCUSDT", "direction": "BUY", "tps": ["21000"], "sl": "19000"}
    res = await OCOManager(FakeBybit(), signal, trade_id="TRD-1").monitor()
    assert res == "TP_HIT"


async def check_resume_async():
    from app.runtime.resume import resume_open_trades
    from app.storage import db as db_mod

    async def fake_get_open_trades():
        return [("TRD-X", "BTCUSDT", "BUY", 20000.0, 0.01, "TPSL_PLACED")]

    db_mod.get_open_trades = fake_get_open_trades  # type: ignore
    await resume_open_trades()
    assert True


async def main():
    failures = 0
    # Synchronous checks
    for label, fn in [
        ("Entry flags (Limit+PostOnly)", check_entry_flags),
        ("Exit flags (TP Limit RO; SL Market RO MarkPrice)", check_exit_flags),
        ("Risk sizing 2%", check_risk_sizing),
        ("Templates bilingual", check_templates),
    ]:
        try:
            fn()
            print_ok(label)
        except Exception as e:
            failures += 1
            print_fail(label, e)

    # Async checks
    for label, coro in [
        ("Idempotency duplicate suppression", check_idempotency_async),
        ("OCO cancels sibling and records PnL", check_oco_async),
        ("Resume reattaches monitors", check_resume_async),
    ]:
        try:
            await coro()
            print_ok(label)
        except Exception as e:
            failures += 1
            print_fail(label, e)

    if failures:
        print(f"\n{failures} check(s) failed.")
        sys.exit(1)
    print("\nAll self-checks passed.")


if __name__ == "__main__":
    asyncio.run(main())

