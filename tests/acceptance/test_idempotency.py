import asyncio
import pytest
from app.signals.idempotency import is_new_signal


@pytest.mark.asyncio
async def test_duplicate_message_ignored(tmp_path, monkeypatch):
    # Use a temp DB by monkeypatching DB_PATH
    from app import storage
    from app.storage import db as db_mod

    monkeypatch.setattr(db_mod, "DB_PATH", str(tmp_path / "t.sqlite"))

    ok1 = await is_new_signal(123, "hello world")
    ok2 = await is_new_signal(123, "hello world")
    assert ok1 is True
    assert ok2 is False
