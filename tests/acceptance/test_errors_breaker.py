import pytest
import asyncio
from app.core.errors import safe_step


@pytest.mark.asyncio
async def test_transient_backoff_and_breaker(monkeypatch):
    calls = {"n": 0}

    class Boom(Exception):
        def __str__(self):
            # Include a transient retCode 10006 on first two calls
            return "10006 Rate limit"

    @safe_step("unit_test_step")
    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise Boom()
        return "ok"

    # Fast sleep to avoid real delays
    async def fast_sleep(_):
        return None

    monkeypatch.setattr("asyncio.sleep", fast_sleep)

    out = await flaky()
    assert out == "ok"
