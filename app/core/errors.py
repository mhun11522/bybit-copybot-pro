"""Error handling with circuit breaker and retry logic."""

import functools
import asyncio
import time
import traceback
from app.core.retcodes import MAP, TRANSIENT

_BREAKER = {"open": False, "until": 0.0, "fail_count": 0}
_PAUSE_S = 120
_MAX_FAILS = 3

def _extract_retcode(exc: Exception):
    """Extract Bybit retCode from exception message."""
    s = str(exc)
    for tok in s.replace(",", " ").replace(":", " ").split():
        if tok.isdigit():
            try:
                return int(tok)
            except:
                pass
    return None

def safe_step(step_name: str):
    """Decorator for safe execution with circuit breaker and retry."""
    def deco(fn):
        @functools.wraps(fn)
        async def wrap(*a, **kw):
            if _BREAKER["open"] and time.time() < _BREAKER["until"]:
                print("⛔ Paus aktiverad / Trading paused (circuit breaker)")
                raise RuntimeError("Circuit breaker open")
            
            try:
                return await fn(*a, **kw)
            except Exception as e:
                code = _extract_retcode(e)
                print(MAP.get(code, f"❌ Okänt fel / Unknown error in {step_name}"))
                
                if code in TRANSIENT:
                    # Retry transient errors with exponential backoff
                    delay = 1.0
                    for _ in range(2):
                        await asyncio.sleep(delay)
                        try:
                            return await fn(*a, **kw)
                        except Exception:
                            delay *= 2
                
                _BREAKER["fail_count"] += 1
                if _BREAKER["fail_count"] >= _MAX_FAILS:
                    _BREAKER["open"] = True
                    _BREAKER["until"] = time.time() + _PAUSE_S
                    _BREAKER["fail_count"] = 0
                    print("⛔ Trading pausad i 2 min / Trading paused for 2 minutes")
                
                traceback.print_exc()
                raise
        return wrap
    return deco

def breaker_reset():
    """Reset circuit breaker if time has passed."""
    if _BREAKER["open"] and time.time() >= _BREAKER["until"]:
        _BREAKER["open"] = False
    if _BREAKER["fail_count"] > 0:
        _BREAKER["fail_count"] -= 1